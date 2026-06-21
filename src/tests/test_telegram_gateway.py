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
    
    # 1. Short text fits everywhere
    assert validate_text_limits("Short text") is None
    
    # 2. Medium text triggers thread warning for Bluesky but fits Mastodon/Threads
    # Bluesky limit is 300. 350 chars should trigger splitting warning.
    medium_text = "a" * 350
    res = validate_text_limits(medium_text)
    assert res is not None
    assert "split into a thread" in res
    assert "Bluesky" in res
    assert "Mastodon" not in res
    
    # 3. Very long text triggers truncation warning
    # Bluesky max thread length is (300-10)*2 = 580. 600 chars should trigger truncation.
    long_text = "a" * 600
    res2 = validate_text_limits(long_text)
    assert res2 is not None
    assert "truncation" in res2 or "truncated" in res2
    assert "Bluesky" in res2

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
    
    res = await send_draft_for_approval("Original draft text")
    assert res == "Original draft text"
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
    
    res = await send_draft_for_approval("Original draft text")
    assert res is None

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
    
    res = await send_draft_for_approval("Original draft text")
    assert res == "Edited draft text"
    mock_bot_instance.edit_message_text.assert_called_with(
        chat_id="98765",
        message_id=999,
        text="📝 **DRAFT POST**:\n\nEdited draft text",
        reply_markup=mocker.ANY,
        parse_mode="Markdown"
    )
