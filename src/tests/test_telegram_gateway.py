import pytest
from unittest.mock import AsyncMock, MagicMock
from src.settings import Settings
from src.telegram_gateway import validate_text_limits, send_draft_for_approval

def test_validate_text_limits(monkeypatch):
    mock_settings = Settings(
        gemini_key="mock",
        bluesky_limit=300,
        mastodon_limit=500,
        threads_limit=500,
        max_thread_parts=2
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)
    
    # 1. Short text fits everywhere (subtracting safety buffers: bsky=290, mastodon=485, threads=490)
    assert validate_text_limits("Short text") is None
    
    # 2. Medium text triggers thread warning for Bluesky but fits Mastodon/Threads
    # Bluesky limit is 290. 350 chars should trigger splitting warning.
    medium_text = "a" * 350
    res = validate_text_limits(medium_text)
    assert res is not None
    assert "split into a thread" in res
    assert "Bluesky" in res
    assert "Mastodon" not in res
    
    # 3. Very long text triggers truncation warning
    # Bluesky max thread length is 290 * 2 = 580. 600 chars should trigger truncation.
    long_text = "a" * 600
    res2 = validate_text_limits(long_text)
    assert res2 is not None
    assert "truncation" in res2 or "truncated" in res2
    assert "Bluesky" in res2

from src.telegram_gateway import process_authorized_command
from datetime import datetime, timezone

def test_process_authorized_command_watch_flow(mocker):
    mocker.patch("src.utils.load_seen_articles", return_value={"watch_topics": []})
    mock_save = mocker.patch("src.utils.save_seen_articles")
    
    # 1. Add valid topic
    res_add = process_authorized_command("/watch Llama 4")
    assert res_add is not None
    assert res_add["action"] == "watch_added"
    assert "Added *Llama 4*" in res_add["response"]
    mock_save.assert_called_once()
    
    # 2. List watches
    mocker.patch("src.utils.load_seen_articles", return_value={
        "watch_topics": [{"topic": "llama 4", "display_name": "Llama 4", "created": "2026-08-04T00:00:00Z"}]
    })
    res_list = process_authorized_command("/watches")
    assert res_list["action"] == "watches_list"
    assert "Llama 4" in res_list["response"]
    
    # 3. Unwatch topic
    mocker.patch("src.utils.load_seen_articles", return_value={
        "watch_topics": [{"topic": "llama 4", "display_name": "Llama 4", "created": "2026-08-04T00:00:00Z"}]
    })
    res_unwatch = process_authorized_command("/unwatch Llama 4")
    assert res_unwatch["action"] == "unwatch_removed"
    assert "Removed *llama 4*" in res_unwatch["response"]

def test_process_authorized_command_brief():
    # 1. Valid brief command
    res_brief = process_authorized_command("/brief Quantum Computing")
    assert res_brief is not None
    assert res_brief["action"] == "brief"
    assert res_brief["topic"] == "Quantum Computing"
    assert "Quantum Computing" in res_brief["response"]
    
    # 2. Invalid empty brief command
    res_invalid = process_authorized_command("/brief")
    assert res_invalid is None

def test_watchlist_boost_scoring_cap():
    from src.curator import calculate_relevance_score
    now_utc = datetime.now(timezone.utc)
    item = {
        "title": "Meta Launches Llama 4 Open Source",
        "summary": "Full release details of Llama 4 model",
        "source_id": "unknown"
    }
    watch_topics = [{"topic": "llama 4", "keywords": ["llama", "4"]}]
    
    # Score with watch topics
    score_watch = calculate_relevance_score(item, now_utc, now_utc, watch_topics=watch_topics)
    debug = item.get("_score_debug", {})
    
    # +8 boost for exact title phrase match, capped at +8
    assert debug.get("watchlist") == 8
    assert debug.get("matched_watch") == "llama 4"

@pytest.mark.asyncio
async def test_send_draft_for_approval_approve(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)
    
    # Mock the Bot
    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = AsyncMock()
    mock_bot_instance.send_photo = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot_instance)
    
    # Mock Updates polling - Approve case
    mock_update = MagicMock()
    mock_update.update_id = 1000
    mock_update.message = None
    mock_update.callback_query = MagicMock()
    mock_update.callback_query.from_user.id = "98765"
    mock_update.callback_query.data = "approve"
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.message = MagicMock()
    
    # Configure send_message/send_photo return to match update's message id
    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot_instance.send_message.return_value = sent_msg
    mock_update.callback_query.message.message_id = 999
    
    # Prevent infinite loop by returning updates once then empty lists
    updates_queue = [
        [], # First call in clear-up
        [mock_update], # Second call in loop
    ]
    async def mock_get_updates(*args, **kwargs):
        if updates_queue:
            return updates_queue.pop(0)
        return []
    mock_bot_instance.get_updates = AsyncMock(side_effect=mock_get_updates)
    
    text, media = await send_draft_for_approval("Original draft text")
    assert text == "Original draft text"
    assert media is None
    mock_bot_instance.send_message.assert_called()

@pytest.mark.asyncio
async def test_send_draft_for_approval_reject(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)
    
    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot_instance)
    
    mock_update = MagicMock()
    mock_update.update_id = 1000
    mock_update.message = None
    mock_update.callback_query = MagicMock()
    mock_update.callback_query.from_user.id = "98765"
    mock_update.callback_query.data = "reject"
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.message = MagicMock()
    
    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot_instance.send_message.return_value = sent_msg
    mock_update.callback_query.message.message_id = 999
    
    updates_queue = [
        [],
        [mock_update],
    ]
    async def mock_get_updates(*args, **kwargs):
        if updates_queue:
            return updates_queue.pop(0)
        return []
    mock_bot_instance.get_updates = AsyncMock(side_effect=mock_get_updates)
    
    text, media = await send_draft_for_approval("Original draft text")
    assert text is None
    assert media is None

@pytest.mark.asyncio
async def test_send_draft_for_approval_edit_by_reply(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)
    
    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = AsyncMock()
    mock_bot_instance.edit_message_text = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot_instance)
    
    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot_instance.send_message.return_value = sent_msg
    
    # We simulate two updates:
    # 1. User replies to the draft with "Edited draft text"
    mock_update_edit = MagicMock()
    mock_update_edit.update_id = 1000
    mock_update_edit.callback_query = None
    mock_update_edit.message = MagicMock()
    mock_update_edit.message.from_user.id = "98765"
    mock_update_edit.message.text = "Edited draft text"
    mock_update_edit.message.reply_to_message = MagicMock()
    mock_update_edit.message.reply_to_message.message_id = 999
    mock_update_edit.message.message_id = 1001
    
    # 2. User approves the edited text
    mock_update_approve = MagicMock()
    mock_update_approve.update_id = 1001
    mock_update_approve.message = None
    mock_update_approve.callback_query = MagicMock()
    mock_update_approve.callback_query.from_user.id = "98765"
    mock_update_approve.callback_query.data = "approve"
    mock_update_approve.callback_query.answer = AsyncMock()
    mock_update_approve.callback_query.message = MagicMock()
    mock_update_approve.callback_query.message.message_id = 999
    
    updates_queue = [
        [],
        [mock_update_edit],
        [mock_update_approve]
    ]
    async def mock_get_updates(*args, **kwargs):
        if updates_queue:
            return updates_queue.pop(0)
        return []
    mock_bot_instance.get_updates = AsyncMock(side_effect=mock_get_updates)
    
    text, media = await send_draft_for_approval("Original draft text")
    assert text == "Edited draft text"
    assert media is None
    mock_bot_instance.edit_message_text.assert_called_with(
        chat_id="98765",
        message_id=999,
        text="📝 **DRAFT POST (🔵 Bluesky View)**:\n\nEdited draft text\n\n`[17/290 chars]`",
        reply_markup=mocker.ANY,
        parse_mode="Markdown"
    )

@pytest.mark.asyncio
async def test_send_draft_for_approval_regenerate_text(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)
    
    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = AsyncMock()
    mock_bot_instance.edit_message_text = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot_instance)
    
    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot_instance.send_message.return_value = sent_msg
    
    # 1. User clicks regenerate text callback
    mock_update_regen = MagicMock()
    mock_update_regen.update_id = 1000
    mock_update_regen.message = None
    mock_update_regen.callback_query = MagicMock()
    mock_update_regen.callback_query.from_user.id = "98765"
    mock_update_regen.callback_query.data = "regenerate_text"
    mock_update_regen.callback_query.answer = AsyncMock()
    mock_update_regen.callback_query.message = MagicMock()
    mock_update_regen.callback_query.message.message_id = 999
    
    # 2. User sends hint text reply
    mock_update_hint = MagicMock()
    mock_update_hint.update_id = 1001
    mock_update_hint.callback_query = None
    mock_update_hint.message = MagicMock()
    mock_update_hint.message.from_user.id = "98765"
    mock_update_hint.message.text = "make it shorter"
    mock_update_hint.message.reply_to_message = MagicMock()
    # Let the prompt message ID be 888
    mock_update_hint.message.reply_to_message.message_id = 888
    mock_update_hint.message.message_id = 1002
    
    # Configure the prompt send_message to return ID 888
    prompt_msg = MagicMock()
    prompt_msg.message_id = 888
    
    # Set up bot send_message sequence: first returns sent_msg, second returns prompt_msg, subsequent return mock_msg
    mock_bot_instance.send_message.side_effect = [sent_msg, prompt_msg, MagicMock(), MagicMock(), MagicMock()]
    
    # 3. User approves
    mock_update_approve = MagicMock()
    mock_update_approve.update_id = 1003
    mock_update_approve.message = None
    mock_update_approve.callback_query = MagicMock()
    mock_update_approve.callback_query.from_user.id = "98765"
    mock_update_approve.callback_query.data = "approve"
    mock_update_approve.callback_query.answer = AsyncMock()
    mock_update_approve.callback_query.message = MagicMock()
    mock_update_approve.callback_query.message.message_id = 999
    
    updates_queue = [
        [],
        [mock_update_regen],
        [mock_update_hint],
        [mock_update_approve]
    ]
    async def mock_get_updates(*args, **kwargs):
        if updates_queue:
            return updates_queue.pop(0)
        return []
    mock_bot_instance.get_updates = AsyncMock(side_effect=mock_get_updates)
    
    # Mock Gemini Client
    mock_genai = MagicMock()
    mock_genai.aio = MagicMock()
    mock_genai.aio.models = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Mocked regenerated short text draft"
    mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    text, media = await send_draft_for_approval(
        text="Original draft text",
        genai_client=mock_genai
    )
    
    assert text == "Mocked regenerated short text draft"
    assert media is None
    mock_genai.aio.models.generate_content.assert_called()

@pytest.mark.asyncio
async def test_send_draft_for_approval_regenerate_image_success(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)
    
    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = AsyncMock()
    mock_bot_instance.send_photo = AsyncMock()
    mock_bot_instance.edit_message_media = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot_instance)
    
    sent_msg = MagicMock()
    sent_msg.message_id = 999
    # Add photo attribute to sent message mock to simulate a photo draft message
    sent_msg.photo = [MagicMock()]
    mock_bot_instance.send_photo.return_value = sent_msg
    
    # 1. User clicks regenerate image callback
    mock_update_regen = MagicMock()
    mock_update_regen.update_id = 1000
    mock_update_regen.message = None
    mock_update_regen.callback_query = MagicMock()
    mock_update_regen.callback_query.from_user.id = "98765"
    mock_update_regen.callback_query.data = "regenerate_image"
    mock_update_regen.callback_query.answer = AsyncMock()
    mock_update_regen.callback_query.message = MagicMock()
    mock_update_regen.callback_query.message.message_id = 999
    
    # 2. User approves
    mock_update_approve = MagicMock()
    mock_update_approve.update_id = 1001
    mock_update_approve.message = None
    mock_update_approve.callback_query = MagicMock()
    mock_update_approve.callback_query.from_user.id = "98765"
    mock_update_approve.callback_query.data = "approve"
    mock_update_approve.callback_query.answer = AsyncMock()
    mock_update_approve.callback_query.message = MagicMock()
    mock_update_approve.callback_query.message.message_id = 999
    
    updates_queue = [
        [],
        [mock_update_regen],
        [mock_update_approve]
    ]
    async def mock_get_updates(*args, **kwargs):
        if updates_queue:
            return updates_queue.pop(0)
        return []
    mock_bot_instance.get_updates = AsyncMock(side_effect=mock_get_updates)
    
    # Mock curator functions
    mocker.patch("src.curator.generate_visual_prompt", return_value="Visual Prompt")
    
    # Generate minimal valid PNG bytes so validate_image_bytes returns True
    from PIL import Image
    import io
    out = io.BytesIO()
    im = Image.new("RGBA", (10, 10), "blue")
    im.save(out, format="PNG")
    valid_bytes = out.getvalue()
    
    mocker.patch("src.curator.generate_ai_image", return_value=valid_bytes)
    mocker.patch("src.curator.generate_image_alt_text", return_value="New Alt Text")
    
    mock_client = MagicMock()
    mock_genai = MagicMock()
    
    from src.models import MediaAsset, MediaSource
    media_asset = MediaAsset(
        source=MediaSource.GENERATED,
        image_bytes=b"OldImageBytes",
        alt_text="Old Alt"
    )
    
    text, media = await send_draft_for_approval(
        text="Original draft text",
        media=media_asset,
        client=mock_client,
        genai_client=mock_genai
    )
    
    assert text == "Original draft text"
    assert media.image_bytes == valid_bytes
    assert media.alt_text == "New Alt Text"
    mock_bot_instance.edit_message_media.assert_called()

@pytest.mark.asyncio
async def test_send_draft_for_approval_regenerate_image_failure(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)
    
    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = AsyncMock()
    mock_bot_instance.send_photo = AsyncMock()
    mock_bot_instance.edit_message_media = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot_instance)
    
    sent_msg = MagicMock()
    sent_msg.message_id = 999
    sent_msg.photo = [MagicMock()]
    mock_bot_instance.send_photo.return_value = sent_msg
    
    # 1. User clicks regenerate image callback (which will fail)
    mock_update_regen = MagicMock()
    mock_update_regen.update_id = 1000
    mock_update_regen.message = None
    mock_update_regen.callback_query = MagicMock()
    mock_update_regen.callback_query.from_user.id = "98765"
    mock_update_regen.callback_query.data = "regenerate_image"
    mock_update_regen.callback_query.answer = AsyncMock()
    mock_update_regen.callback_query.message = MagicMock()
    mock_update_regen.callback_query.message.message_id = 999
    
    # 2. User approves (after failure)
    mock_update_approve = MagicMock()
    mock_update_approve.update_id = 1001
    mock_update_approve.message = None
    mock_update_approve.callback_query = MagicMock()
    mock_update_approve.callback_query.from_user.id = "98765"
    mock_update_approve.callback_query.data = "approve"
    mock_update_approve.callback_query.answer = AsyncMock()
    mock_update_approve.callback_query.message = MagicMock()
    mock_update_approve.callback_query.message.message_id = 999
    
    updates_queue = [
        [],
        [mock_update_regen],
        [mock_update_approve]
    ]
    async def mock_get_updates(*args, **kwargs):
        if updates_queue:
            return updates_queue.pop(0)
        return []
    mock_bot_instance.get_updates = AsyncMock(side_effect=mock_get_updates)
    
    # Mock curator functions to fail image generation
    mocker.patch("src.curator.generate_visual_prompt", return_value="Visual Prompt")
    mocker.patch("src.curator.generate_ai_image", return_value=None)
    
    mock_client = MagicMock()
    mock_genai = MagicMock()
    
    from src.models import MediaAsset, MediaSource
    media_asset = MediaAsset(
        source=MediaSource.GENERATED,
        image_bytes=b"OldImageBytes",
        alt_text="Old Alt"
    )
    
    text, media = await send_draft_for_approval(
        text="Original draft text",
        media=media_asset,
        client=mock_client,
        genai_client=mock_genai
    )
    
    # Verification:
    # 1. Approval loop was kept active (returned successfully because approve update was processed)
    assert text == "Original draft text"
    # 2. Preview image was preserved (retained original OldImageBytes)
    assert media.image_bytes == b"OldImageBytes"
    # 3. User received a clear failure message
    mock_bot_instance.send_message.assert_any_call(
        chat_id="98765",
        text="Image regeneration failed. The previous image has been preserved and the draft can still be approved.",
        reply_to_message_id=mocker.ANY
    )

@pytest.mark.asyncio
async def test_tab_switching_callback_updates_caption(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_photo = AsyncMock()
    mock_bot.edit_message_caption = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot.send_photo.return_value = sent_msg

    # 1. User clicks tab:threads
    update_tab = MagicMock()
    update_tab.update_id = 100
    update_tab.message = None
    update_tab.callback_query = MagicMock()
    update_tab.callback_query.from_user.id = "98765"
    update_tab.callback_query.data = "tab:threads"
    update_tab.callback_query.answer = AsyncMock()
    update_tab.callback_query.message.message_id = 999

    # 2. User clicks approve
    update_app = MagicMock()
    update_app.update_id = 101
    update_app.message = None
    update_app.callback_query = MagicMock()
    update_app.callback_query.from_user.id = "98765"
    update_app.callback_query.data = "approve"
    update_app.callback_query.answer = AsyncMock()
    update_app.callback_query.message.message_id = 999

    updates_queue = [[], [update_tab], [update_app]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    from src.models import PlatformDrafts, MediaAsset, MediaSource
    drafts = PlatformDrafts(
        bluesky="Bsky text",
        threads="Threads customized text",
        mastodon="Masto customized text"
    )
    media = MediaAsset(source=MediaSource.GENERATED, image_bytes=b"png", alt_text="Alt")

    final_drafts, final_media = await send_draft_for_approval(drafts=drafts, media=media)

    assert final_drafts == drafts
    mock_bot.edit_message_caption.assert_called_once()
    caption_arg = mock_bot.edit_message_caption.call_args[1]["caption"]
    assert "Threads View" in caption_arg
    assert "Threads customized text" in caption_arg
    assert len(caption_arg) <= 1024

@pytest.mark.asyncio
async def test_stale_callback_ignored(monkeypatch, mocker):
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot.send_message.return_value = sent_msg

    # Stale callback for older message id 777
    stale_update = MagicMock()
    stale_update.update_id = 100
    stale_update.message = None
    stale_update.callback_query = MagicMock()
    stale_update.callback_query.from_user.id = "98765"
    stale_update.callback_query.data = "approve"
    stale_update.callback_query.answer = AsyncMock()
    stale_update.callback_query.message.message_id = 777

    # Legitimate approve for 999
    valid_update = MagicMock()
    valid_update.update_id = 101
    valid_update.message = None
    valid_update.callback_query = MagicMock()
    valid_update.callback_query.from_user.id = "98765"
    valid_update.callback_query.data = "approve"
    valid_update.callback_query.answer = AsyncMock()
    valid_update.callback_query.message.message_id = 999

    updates_queue = [[], [stale_update], [valid_update]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    await send_draft_for_approval("Draft")
    stale_update.callback_query.answer.assert_called_with("Stale or expired draft session.", show_alert=True)

@pytest.mark.asyncio
async def test_send_draft_for_approval_remix_failure_notifies_user(monkeypatch, mocker):
    """Verify failed remix (quota/network) produces explicit warning notice and preserves drafts."""
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.edit_message_text = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_msg = MagicMock()
    sent_msg.message_id = 999
    prompt_msg = MagicMock()
    prompt_msg.message_id = 888
    mock_bot.send_message.side_effect = [sent_msg, prompt_msg, MagicMock(), MagicMock(), MagicMock()]

    # 1. Trigger remix callback
    update_remix = MagicMock()
    update_remix.update_id = 100
    update_remix.message = None
    update_remix.callback_query = MagicMock()
    update_remix.callback_query.from_user.id = "98765"
    update_remix.callback_query.data = "remix:bluesky"
    update_remix.callback_query.answer = AsyncMock()
    update_remix.callback_query.message.message_id = 999

    # 2. Reply to remix prompt
    update_instruction = MagicMock()
    update_instruction.update_id = 101
    update_instruction.callback_query = None
    update_instruction.message = MagicMock()
    update_instruction.message.from_user.id = "98765"
    update_instruction.message.text = "make it sharper"
    update_instruction.message.reply_to_message = MagicMock()
    update_instruction.message.reply_to_message.message_id = 888
    update_instruction.message.message_id = 1002

    # 3. Approve
    update_approve = MagicMock()
    update_approve.update_id = 102
    update_approve.message = None
    update_approve.callback_query = MagicMock()
    update_approve.callback_query.from_user.id = "98765"
    update_approve.callback_query.data = "approve"
    update_approve.callback_query.answer = AsyncMock()
    update_approve.callback_query.message.message_id = 999

    updates_queue = [[], [update_remix], [update_instruction], [update_approve]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    # Mock remix_platform_draft to return (False, original_text) indicating failure
    mocker.patch("src.curator.remix_platform_draft", new_callable=AsyncMock, return_value=(False, "Original draft text"))

    text, media = await send_draft_for_approval("Original draft text")
    assert text == "Original draft text"

    # Verify explicit failure notice was sent to Telegram
    sent_texts = [call[1].get("text", "") for call in mock_bot.send_message.call_args_list]
    assert any("Remix failed" in t and "Previous draft preserved" in t for t in sent_texts)

@pytest.mark.asyncio
async def test_approval_loop_persists_topic_command(monkeypatch, mocker, tmp_path):
    """Verify /topic command received during approval is persisted to pending_topic.json."""
    from src.config import PENDING_TOPIC_FILE_PATH
    import os
    import json

    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot.send_message.return_value = sent_msg

    # 1. Message with /topic Quantum AI
    update_cmd = MagicMock()
    update_cmd.update_id = 100
    update_cmd.callback_query = None
    update_cmd.message = MagicMock()
    update_cmd.message.from_user.id = "98765"
    update_cmd.message.text = "/topic Quantum AI"
    update_cmd.message.reply_to_message = None
    update_cmd.message.message_id = 1001

    # 2. Approve
    update_approve = MagicMock()
    update_approve.update_id = 101
    update_approve.message = None
    update_approve.callback_query = MagicMock()
    update_approve.callback_query.from_user.id = "98765"
    update_approve.callback_query.data = "approve"
    update_approve.callback_query.answer = AsyncMock()
    update_approve.callback_query.message.message_id = 999

    updates_queue = [[], [update_cmd], [update_approve]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    # Temporary pending_topic file path
    temp_topic_file = str(tmp_path / "pending_topic.json")
    monkeypatch.setattr("src.config.PENDING_TOPIC_FILE_PATH", temp_topic_file)

    await send_draft_for_approval("Original text")

    assert os.path.exists(temp_topic_file)
    with open(temp_topic_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["topic"] == "Quantum AI"

@pytest.mark.asyncio
async def test_remix_all_media_all_in_one_mode_caption_protection(monkeypatch, mocker):
    """Verify Remix All in media + all-in-one mode never exceeds Telegram caption budget and sends follow-up."""
    from src.models import PlatformDrafts, MediaAsset, MediaSource
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_photo = AsyncMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.edit_message_caption = AsyncMock()
    mock_bot.edit_message_reply_markup = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_photo = MagicMock()
    sent_photo.message_id = 999
    mock_bot.send_photo.return_value = sent_photo

    prompt_msg = MagicMock()
    prompt_msg.message_id = 888
    mock_bot.send_message.return_value = prompt_msg

    # Step 1: Switch to all-in-one view
    update_view = MagicMock()
    update_view.update_id = 100
    update_view.message = None
    update_view.callback_query = MagicMock()
    update_view.callback_query.from_user.id = "98765"
    update_view.callback_query.data = "view:all"
    update_view.callback_query.answer = AsyncMock()
    update_view.callback_query.message.message_id = 999

    # Step 2: Trigger remix:all
    update_remix = MagicMock()
    update_remix.update_id = 101
    update_remix.message = None
    update_remix.callback_query = MagicMock()
    update_remix.callback_query.from_user.id = "98765"
    update_remix.callback_query.data = "remix:all"
    update_remix.callback_query.answer = AsyncMock()
    update_remix.callback_query.message.message_id = 999

    # Step 3: Send instruction
    update_instr = MagicMock()
    update_instr.update_id = 102
    update_instr.callback_query = None
    update_instr.message = MagicMock()
    update_instr.message.from_user.id = "98765"
    update_instr.message.text = "make all detailed"
    update_instr.message.reply_to_message = MagicMock()
    update_instr.message.reply_to_message.message_id = 888
    update_instr.message.message_id = 1002

    # Step 4: Approve
    update_approve = MagicMock()
    update_approve.update_id = 103
    update_approve.message = None
    update_approve.callback_query = MagicMock()
    update_approve.callback_query.from_user.id = "98765"
    update_approve.callback_query.data = "approve"
    update_approve.callback_query.answer = AsyncMock()
    update_approve.callback_query.message.message_id = 999

    updates_queue = [[], [update_view], [update_remix], [update_instr], [update_approve]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    # Oversized remixed drafts (> 950 chars total preview)
    large_remixed = PlatformDrafts(
        bluesky="B" * 280,
        threads="T" * 480,
        mastodon="M" * 480
    )
    mocker.patch("src.curator.remix_all_drafts", new_callable=AsyncMock, return_value=(True, large_remixed))

    media = MediaAsset(source=MediaSource.OPENGRAPH, image_bytes=b"fake_image")
    approved_drafts, approved_media = await send_draft_for_approval(
        drafts=PlatformDrafts.from_single("Initial draft"),
        media=media
    )

    assert approved_drafts == large_remixed
    assert approved_media == media

    # Check caption limits across all edit_message_caption calls
    for call in mock_bot.edit_message_caption.call_args_list:
        caption = call[1].get("caption", "")
        assert len(caption) <= 1024, f"Caption exceeded limit: {len(caption)}"

    # Verify a follow-up markdown message was sent containing the full breakdown
    followup_texts = [call[1].get("text", "") for call in mock_bot.send_message.call_args_list]
    assert any("MULTI-PLATFORM DRAFTS" in t for t in followup_texts)

@pytest.mark.asyncio
async def test_tab_view_edit_failure_preserves_state_and_alerts(monkeypatch, mocker):
    """Verify that when Telegram edit fails during tab/view switch, active state is preserved and alert is shown."""
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    # Simulate network error on edit_message_text
    mock_bot.edit_message_text = AsyncMock(side_effect=RuntimeError("Telegram network timeout"))
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_msg = MagicMock()
    sent_msg.message_id = 999
    mock_bot.send_message.return_value = sent_msg

    # Tab switch callback that will fail Telegram edit
    update_tab = MagicMock()
    update_tab.update_id = 100
    update_tab.message = None
    update_tab.callback_query = MagicMock()
    update_tab.callback_query.from_user.id = "98765"
    update_tab.callback_query.data = "tab:threads"
    update_tab.callback_query.answer = AsyncMock()
    update_tab.callback_query.message.message_id = 999

    # View switch callback that will also fail
    update_view = MagicMock()
    update_view.update_id = 101
    update_view.message = None
    update_view.callback_query = MagicMock()
    update_view.callback_query.from_user.id = "98765"
    update_view.callback_query.data = "view:all"
    update_view.callback_query.answer = AsyncMock()
    update_view.callback_query.message.message_id = 999

    # Approve
    update_approve = MagicMock()
    update_approve.update_id = 102
    update_approve.message = None
    update_approve.callback_query = MagicMock()
    update_approve.callback_query.from_user.id = "98765"
    update_approve.callback_query.data = "approve"
    update_approve.callback_query.answer = AsyncMock()
    update_approve.callback_query.message.message_id = 999

    updates_queue = [[], [update_tab], [update_view], [update_approve]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    await send_draft_for_approval("Initial draft")

    # Alert popups should be shown to user informing of failure
    update_tab.callback_query.answer.assert_called_with("Failed to switch tab.", show_alert=True)
    update_view.callback_query.answer.assert_called_with("Failed to switch view.", show_alert=True)

@pytest.mark.asyncio
async def test_media_all_in_one_followup_failure_maintains_authoritative_draft(monkeypatch, mocker):
    """
    Verify that when media + all-in-one mode is active and edit_message_caption succeeds
    but follow-up send_message fails:
    - The new drafts remain authoritative.
    - Approval returns the updated drafts.
    - The user receives an appropriate warning notice.
    """
    from src.models import PlatformDrafts, MediaAsset, MediaSource
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_photo = AsyncMock()
    mock_bot.edit_message_caption = AsyncMock()
    mock_bot.edit_message_reply_markup = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_photo = MagicMock()
    sent_photo.message_id = 999
    mock_bot.send_photo.return_value = sent_photo

    prompt_msg = MagicMock()
    prompt_msg.message_id = 888

    # Define send_message mock behavior:
    # 1st call: prompt_msg (reply instruction prompt)
    # 2nd call: status_msg ("Remixing ... with Gemini...")
    # 3rd call (follow-up markdown breakdown in _render_and_update_preview): FAILS with network error!
    # 4th call: warning notice about follow-up failure
    # 5th call: success notice ("Draft successfully remixed!")
    async def mock_send_message_side_effect(*args, **kwargs):
        text = kwargs.get("text", "")
        # If this is the oversized breakdown follow-up
        if "MULTI-PLATFORM DRAFTS" in text:
            raise RuntimeError("Telegram network failure on follow-up message")
        if "instruction to remix" in text:
            return prompt_msg
        msg = MagicMock()
        msg.message_id = 12345
        return msg

    mock_bot.send_message = AsyncMock(side_effect=mock_send_message_side_effect)

    # 1. Switch to all-in-one view
    update_view = MagicMock()
    update_view.update_id = 100
    update_view.message = None
    update_view.callback_query = MagicMock()
    update_view.callback_query.from_user.id = "98765"
    update_view.callback_query.data = "view:all"
    update_view.callback_query.answer = AsyncMock()
    update_view.callback_query.message.message_id = 999

    # 2. Trigger remix:all
    update_remix = MagicMock()
    update_remix.update_id = 101
    update_remix.message = None
    update_remix.callback_query = MagicMock()
    update_remix.callback_query.from_user.id = "98765"
    update_remix.callback_query.data = "remix:all"
    update_remix.callback_query.answer = AsyncMock()
    update_remix.callback_query.message.message_id = 999

    # 3. Instruction reply
    update_instr = MagicMock()
    update_instr.update_id = 102
    update_instr.callback_query = None
    update_instr.message = MagicMock()
    update_instr.message.from_user.id = "98765"
    update_instr.message.text = "make it punchy"
    update_instr.message.reply_to_message = MagicMock()
    update_instr.message.reply_to_message.message_id = 888
    update_instr.message.message_id = 1002

    # 4. Approve
    update_approve = MagicMock()
    update_approve.update_id = 103
    update_approve.message = None
    update_approve.callback_query = MagicMock()
    update_approve.callback_query.from_user.id = "98765"
    update_approve.callback_query.data = "approve"
    update_approve.callback_query.answer = AsyncMock()
    update_approve.callback_query.message.message_id = 999

    updates_queue = [[], [update_view], [update_remix], [update_instr], [update_approve]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    # Oversized remixed drafts (> 950 chars)
    large_remixed = PlatformDrafts(
        bluesky="Blue " * 60,
        threads="Thread " * 75,
        mastodon="Masto " * 75
    )
    mocker.patch("src.curator.remix_all_drafts", new_callable=AsyncMock, return_value=(True, large_remixed))

    media = MediaAsset(source=MediaSource.OPENGRAPH, image_bytes=b"fake_image")
    approved_drafts, approved_media = await send_draft_for_approval(
        drafts=PlatformDrafts.from_single("Initial draft"),
        media=media
    )

    # edit_message_caption succeeded, so new draft is authoritative and committed
    assert approved_drafts == large_remixed
    assert approved_media == media

    # Verify authoritative photo caption was updated
    assert mock_bot.edit_message_caption.called

    # Verify the user received a warning notice regarding the follow-up message failure
    sent_texts = [call[1].get("text", "") for call in mock_bot.send_message.call_args_list]
    assert any("Full breakdown follow-up message could not be sent" in t for t in sent_texts)

@pytest.mark.asyncio
async def test_regenerated_media_committed_even_if_followup_fails(monkeypatch, mocker):
    """Verify that when image regeneration succeeds in all-in-one mode, new media is committed even if follow-up fails."""
    from src.models import PlatformDrafts, MediaAsset, MediaSource
    mock_settings = Settings(
        gemini_key="mock",
        telegram_bot_token="123:abc",
        telegram_user_id="98765",
        telegram_timeout_minutes=1,
        is_dry_run=False
    )
    monkeypatch.setattr("src.telegram_gateway.settings", mock_settings)

    mock_bot = MagicMock()
    mock_bot.send_photo = AsyncMock()
    mock_bot.edit_message_media = AsyncMock()
    mocker.patch("src.telegram_gateway.Bot", return_value=mock_bot)

    sent_photo = MagicMock()
    sent_photo.message_id = 999
    mock_bot.send_photo.return_value = sent_photo

    status_msg = MagicMock()
    status_msg.message_id = 888

    # Fail follow-up send_message specifically
    async def mock_send_message_side_effect(*args, **kwargs):
        text = kwargs.get("text", "")
        if "MULTI-PLATFORM DRAFTS" in text:
            raise RuntimeError("Network failure on follow-up")
        msg = MagicMock()
        msg.message_id = 12345
        return msg

    mock_bot.send_message = AsyncMock(side_effect=mock_send_message_side_effect)

    # 1. Switch to view:all
    update_view = MagicMock()
    update_view.update_id = 100
    update_view.message = None
    update_view.callback_query = MagicMock()
    update_view.callback_query.from_user.id = "98765"
    update_view.callback_query.data = "view:all"
    update_view.callback_query.answer = AsyncMock()
    update_view.callback_query.message.message_id = 999

    # 2. Trigger regenerate_image
    update_regen = MagicMock()
    update_regen.update_id = 101
    update_regen.message = None
    update_regen.callback_query = MagicMock()
    update_regen.callback_query.from_user.id = "98765"
    update_regen.callback_query.data = "regenerate_image"
    update_regen.callback_query.answer = AsyncMock()
    update_regen.callback_query.message.message_id = 999

    # 3. Approve
    update_approve = MagicMock()
    update_approve.update_id = 102
    update_approve.message = None
    update_approve.callback_query = MagicMock()
    update_approve.callback_query.from_user.id = "98765"
    update_approve.callback_query.data = "approve"
    update_approve.callback_query.answer = AsyncMock()
    update_approve.callback_query.message.message_id = 999

    updates_queue = [[], [update_view], [update_regen], [update_approve]]
    mock_bot.get_updates = AsyncMock(side_effect=lambda *args, **kwargs: updates_queue.pop(0) if updates_queue else [])

    new_img_bytes = b"new_regenerated_valid_image_bytes"
    mocker.patch("src.curator.generate_visual_prompt", new_callable=AsyncMock, return_value="Tech visual")
    mocker.patch("src.curator.generate_ai_image", new_callable=AsyncMock, return_value=new_img_bytes)
    mocker.patch("src.curator.validate_image_bytes", return_value=True)
    mocker.patch("src.curator.generate_image_alt_text", new_callable=AsyncMock, return_value="Alt text")

    # Large drafts to trigger follow-up in all-in-one mode
    drafts = PlatformDrafts(
        bluesky="Blue " * 60,
        threads="Thread " * 75,
        mastodon="Masto " * 75
    )
    initial_media = MediaAsset(source=MediaSource.OPENGRAPH, image_bytes=b"old_image")

    approved_drafts, approved_media = await send_draft_for_approval(
        drafts=drafts,
        media=initial_media,
        client=MagicMock(),
        genai_client=MagicMock()
    )

    # edit_message_media succeeded, so approved media MUST be the newly regenerated media!
    assert approved_media is not None
    assert approved_media.image_bytes == new_img_bytes
    assert mock_bot.edit_message_media.called
