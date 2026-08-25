import pytest
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import Article, CurationResult, InteractionNote, SynthesisResult
from src.settings import settings


@pytest.mark.asyncio
async def test_bluesky_interaction_reply_is_truncated_before_send(mocker):
    """Generated replies must be bounded before reaching Bluesky."""
    import bot

    mention = InteractionNote(
        platform="bluesky",
        id="mention-1",
        author="example.test",
        text="Hello",
        timestamp="2026-08-25T00:00:00Z",
        uri="at://did:example/post/1",
        cid="cid-1",
    )
    bsky_client = MagicMock()
    bsky_client.send_post = AsyncMock()

    mocker.patch("bot.load_seen_interactions", return_value=[])
    mocker.patch("bot.save_seen_interactions")
    mocker.patch("bot.fetch_bluesky_mentions", new_callable=AsyncMock, return_value=[mention])
    mocker.patch("bot.fetch_mastodon_mentions", new_callable=AsyncMock, return_value=[])
    mocker.patch("bot.generate_interactive_reply", new_callable=AsyncMock, return_value="e\u0301" * 180)
    mocker.patch("bot.human_delay", new_callable=AsyncMock)
    mocker.patch("random.random", return_value=0)
    mocker.patch.object(bot, "AUTO_LIKE_INTERACTIONS", False)

    await bot.interaction_stage(
        bsky_client,
        AsyncMock(),
        {"session": "Morning Intelligence", "day": "Monday"},
    )

    sent = bsky_client.send_post.call_args.kwargs["text"]
    assert len(sent) <= 280
    assert sent.endswith("...")


@pytest.mark.asyncio
async def test_message_less_interaction_error_does_not_abort_later_mentions(mocker):
    """A message-less platform error must not escape the interaction loop."""
    import bot

    mentions = [
        InteractionNote(
            platform="bluesky",
            id=f"mention-{index}",
            author=f"example-{index}.test",
            text="Hello",
            timestamp="2026-08-25T00:00:00Z",
            uri=f"at://did:example/post/{index}",
            cid=f"cid-{index}",
        )
        for index in (1, 2)
    ]
    bsky_client = MagicMock()
    bsky_client.send_post = AsyncMock(side_effect=[TimeoutError(), None])

    mocker.patch("bot.load_seen_interactions", return_value=[])
    save_seen = mocker.patch("bot.save_seen_interactions")
    mocker.patch("bot.fetch_bluesky_mentions", new_callable=AsyncMock, return_value=mentions)
    mocker.patch("bot.fetch_mastodon_mentions", new_callable=AsyncMock, return_value=[])
    mocker.patch("bot.generate_interactive_reply", new_callable=AsyncMock, return_value="A useful reply")
    mocker.patch("bot.human_delay", new_callable=AsyncMock)
    mocker.patch("random.random", return_value=0)
    mocker.patch.object(bot, "AUTO_LIKE_INTERACTIONS", False)

    result = await bot.interaction_stage(
        bsky_client,
        AsyncMock(),
        {"session": "Morning Intelligence", "day": "Monday"},
    )

    assert bsky_client.send_post.await_count == 2
    assert result.replied_ids == ["mention-2"]
    assert result.errors == ["TimeoutError: no message"]
    save_seen.assert_called_once()

@pytest.mark.asyncio
async def test_linkless_fallback_synthesis_creates_reservation_key(mocker):
    """Verify linkless synthesis (lead_link=None) generates a deterministic reservation key and proceeds."""
    import bot
    from bot import reserve_pending_stage

    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])
    synthesis = SynthesisResult(content="Linkless Mentor Insight", lead_link=None, topic="General")

    mocker.patch("bot.load_seen_articles", return_value={"pending_stories": []})
    mocker.patch("bot.save_seen_articles", side_effect=lambda data, **kw: (True, data))
    state, matched = await reserve_pending_stage(curation, synthesis)

    assert matched.link.startswith("generated:")
    assert len(state["pending_stories"]) == 1
    assert state["pending_stories"][0]["url"].startswith("generated:")

@pytest.mark.asyncio
async def test_reservation_failure_aborts_broadcast(mocker):
    """Verify that if Gist reservation fails, broadcast is aborted and sys.exit(1) is called."""
    import bot

    curation = CurationResult(
        top_articles=[Article(title="Art 1", link="https://example.com/art1", summary="s", published="2026-08-18", source="src", score=100)],
        seen_links=[],
        recent_topics=[],
        session_name="test_session"
    )
    synthesis = SynthesisResult(
        content="Test content",
        lead_link="https://example.com/art1",
        topic="AI"
    )

    try:
        object.__setattr__(settings, "gist_id", "test_id")
        object.__setattr__(settings, "gist_token", "test_token")
        object.__setattr__(settings, "is_dry_run", False)

        mocker.patch("sys.exit", side_effect=SystemExit(1))
        mocker.patch("bot.check_for_telegram_topic", return_value=(None, None))
        mocker.patch("bot.curation_stage", return_value=curation)
        mocker.patch("bot.synthesis_stage", return_value=(synthesis, curation))
        mocker.patch("bot.media_strategy_stage", return_value=None)
        mocker.patch("bot.load_seen_articles", return_value={"revision": 1, "pending_stories": []})
        mocker.patch("bot.save_seen_articles", return_value=(False, {}))

        mock_broadcast = mocker.patch("bot.broadcast_stage", new_callable=AsyncMock)

        with pytest.raises(SystemExit) as exc_info:
            await bot.main()

        assert exc_info.value.code == 1
        mock_broadcast.assert_not_called()
    finally:
        object.__setattr__(settings, "gist_id", None)
        object.__setattr__(settings, "gist_token", None)
        object.__setattr__(settings, "is_dry_run", True)

@pytest.mark.asyncio
async def test_lead_article_unmatched_aborts_without_fabrication(mocker):
    """Verify bot aborts before broadcast if lead_link cannot be matched (no fabrication)."""
    import bot
    from bot import reserve_pending_stage

    curation = CurationResult(
        top_articles=[Article(title="Art 1", link="https://example.com/art1", summary="s", published="2026-08-18", source="src", score=100)],
        seen_links=[],
        recent_topics=[],
        session_name="test_session"
    )
    synthesis = SynthesisResult(
        content="Test content",
        lead_link="https://example.com/different-unmatched-url", # Unmatched lead
        topic="AI"
    )

    mocker.patch("sys.exit", side_effect=SystemExit(1))

    with pytest.raises(SystemExit) as exc_info:
        await reserve_pending_stage(curation, synthesis)
    assert exc_info.value.code == 1

@pytest.mark.asyncio
async def test_reservation_and_settlement_revision_advancement(mocker, tmp_path):
    """Verify reservation advances revision from N -> N+1, and settlement advances N+1 -> N+2."""
    import src.utils
    from bot import reserve_pending_stage, settle_persistence_stage
    from src.models import BroadcastResult

    test_file = str(tmp_path / "seen_articles.json")
    mocker.patch.object(src.utils, "SEEN_FILE_PATH", test_file)
    object.__setattr__(settings, "is_dry_run", False)

    initial_state = {"schema_version": 2, "revision": 5, "updated_at": "2026-08-18T10:00:00Z", "links": []}
    src.utils.save_json_state(test_file, initial_state)

    article = Article(title="Art 1", link="https://example.com/art1", summary="s", published="2026-08-18", source="src", score=100)
    curation = CurationResult(top_articles=[article], seen_links=[], recent_topics=[])
    synthesis = SynthesisResult(content="Content", lead_link="https://example.com/art1", topic="AI")

    # 1. Reserve Pending (Revision 5 -> 6)
    reserved_state, matched = await reserve_pending_stage(curation, synthesis)
    assert reserved_state["revision"] == 6
    assert len(reserved_state["pending_stories"]) == 1
    assert reserved_state["pending_stories"][0]["url"] == "https://example.com/art1"

    # 2. Settle Partial Broadcast Success (Revision 6 -> 7)
    results = [BroadcastResult("Bluesky", True), BroadcastResult("Mastodon", False)]
    final_state = await settle_persistence_stage(reserved_state, curation, synthesis, matched, results)
    assert final_state["revision"] == 7
    assert len(final_state["pending_stories"]) == 0
    assert len(final_state["recent_stories"]) == 1
    assert final_state["recent_stories"][0]["url"] == "https://example.com/art1"
    assert final_state["recent_stories"][0]["stage"] == "published"

@pytest.mark.asyncio
async def test_all_broadcast_targets_fail_retains_uncertain_reservation(mocker, tmp_path):
    """Verify that if all broadcast targets fail, reservation is retained with stage='uncertain' and sys.exit(1) is called."""
    import src.utils
    from bot import reserve_pending_stage, settle_persistence_stage
    from src.models import BroadcastResult

    test_file = str(tmp_path / "seen_articles.json")
    mocker.patch.object(src.utils, "SEEN_FILE_PATH", test_file)
    object.__setattr__(settings, "is_dry_run", False)

    article = Article(title="Art 1", link="https://example.com/art1", summary="s", published="2026-08-18", source="src", score=100)
    curation = CurationResult(top_articles=[article], seen_links=[], recent_topics=[])
    synthesis = SynthesisResult(content="Content", lead_link="https://example.com/art1", topic="AI")

    reserved_state, matched = await reserve_pending_stage(curation, synthesis)

    mocker.patch("sys.exit", side_effect=SystemExit(1))
    all_failed = [BroadcastResult("Bluesky", False), BroadcastResult("Mastodon", False)]

    with pytest.raises(SystemExit) as exc_info:
        await settle_persistence_stage(reserved_state, curation, synthesis, matched, all_failed)

    assert exc_info.value.code == 1
    assert len(reserved_state["pending_stories"]) == 1
    assert reserved_state["pending_stories"][0]["stage"] == "uncertain"

@pytest.mark.asyncio
async def test_pending_and_uncertain_stories_suppressed_in_curation(mocker, tmp_path):
    """Verify that pending and uncertain story URLs are included in duplicate suppression during curation."""
    import bot
    import src.utils

    test_file = str(tmp_path / "seen_articles.json")
    mocker.patch.object(src.utils, "SEEN_FILE_PATH", test_file)

    pending_state = {
        "schema_version": 2,
        "revision": 1,
        "links": ["https://example.com/old-link"],
        "pending_stories": [
            {"url": "https://example.com/active-pending", "created_at": "2026-08-18T18:00:00Z", "stage": "pending"}
        ]
    }
    src.utils.save_json_state(test_file, pending_state)

    mock_vanguard = mocker.MagicMock()
    mock_vanguard.apply_feed_outcomes = MagicMock(return_value=True)
    mock_vanguard.get_active_feeds.return_value = ["https://feed.com/rss"]
    mocker.patch("src.feed_vanguard.VanguardManager", return_value=mock_vanguard)

    mock_fetch = mocker.patch("bot.fetch_news", new_callable=AsyncMock, return_value=([], []))

    mock_client = AsyncMock()
    await bot.curation_stage(mock_client)

    # Assert fetch_news was called with combined_seen_links containing active-pending
    called_links = mock_fetch.call_args[0][1]
    assert "https://example.com/old-link" in called_links
    assert "https://example.com/active-pending" in called_links
