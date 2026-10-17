"""Unit tests for Friday roundup detection, decision table, text synthesis, and execution."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot
from bot import (
    build_roundup_text,
    get_current_iso_week,
    is_roundup_reserved_or_published,
    roundup_stage,
    select_eligible_roundup_stories,
    validate_roundup_urls_preserved,
)
from src.settings import Settings


def test_get_current_iso_week():
    dt = datetime(2026, 10, 16, 18, 17, tzinfo=timezone.utc)
    assert get_current_iso_week(dt) == "2026-W42"


def test_is_roundup_reserved_or_published():
    iso_week = "2026-W42"
    canonical_key = f"generated:roundup:{iso_week}"

    # Clean state
    assert not is_roundup_reserved_or_published({}, iso_week)

    # Pending story match
    state_pending = {"pending_stories": [{"url": canonical_key, "stage": "pending"}]}
    assert is_roundup_reserved_or_published(state_pending, iso_week)

    # Uncertain story match
    state_uncertain = {"pending_stories": [{"url": canonical_key, "stage": "uncertain"}]}
    assert is_roundup_reserved_or_published(state_uncertain, iso_week)

    # Published post match by week
    state_pub_week = {"published_posts": [{"kind": "roundup", "week": iso_week, "url": "any"}]}
    assert is_roundup_reserved_or_published(state_pub_week, iso_week)

    # Published post match by canonical url
    state_pub_url = {"published_posts": [{"kind": "roundup", "url": canonical_key}]}
    assert is_roundup_reserved_or_published(state_pub_url, iso_week)

    # Unrelated entries
    state_other = {
        "pending_stories": [{"url": "https://example.com/other"}],
        "published_posts": [{"kind": "post", "url": "https://example.com/p1"}],
    }
    assert not is_roundup_reserved_or_published(state_other, iso_week)


def test_select_eligible_roundup_stories():
    iso_week = "2026-W42"
    state = {
        "published_posts": [
            # Eligible (2026-10-14 is W42)
            {"title": "Story 1\nwith newline and @mention", "url": "https://example.com/1", "published_at": "2026-10-14T10:00:00Z", "kind": "post"},
            # Eligible (2026-10-16 is W42)
            {"title": "Story 2", "url": "https://example.com/2", "published_at": "2026-10-16T12:00:00Z"},
            # Ineligible: linkless generated key
            {"title": "Generated Story", "url": "generated:12345abc", "published_at": "2026-10-16T12:00:00Z", "kind": "post"},
            # Ineligible: unsafe URL (local IP)
            {"title": "Local Story", "url": "http://127.0.0.1/story", "published_at": "2026-10-16T12:00:00Z", "kind": "post"},
            # Ineligible: earlier week (2026-10-05 is W41)
            {"title": "Story 3", "url": "https://example.com/3", "published_at": "2026-10-05T12:00:00Z", "kind": "post"},
            # Ineligible: kind is roundup
            {"title": "Story 4", "url": f"generated:roundup:{iso_week}", "published_at": "2026-10-16T18:00:00Z", "kind": "roundup"},
            # Ineligible: missing date
            {"title": "Story 5", "url": "https://example.com/5", "kind": "post"},
        ]
    }
    eligible = select_eligible_roundup_stories(state, iso_week)
    assert len(eligible) == 2
    assert {e["url"] for e in eligible} == {"https://example.com/1", "https://example.com/2"}
    # Verify title normalization (no newlines, no @)
    s1 = next(e for e in eligible if e["url"] == "https://example.com/1")
    assert "\n" not in s1["title"]
    assert "@" not in s1["title"]
    assert s1["title"] == "Story 1 with newline and mention"


def test_build_roundup_text():
    iso_week = "2026-W42"
    stories = [
        {"title": "Alpha Research", "url": "https://example.com/alpha"},
        {"title": "Beta Launch", "url": "https://example.com/beta"},
    ]
    text = build_roundup_text(iso_week, stories)
    expected = (
        "This week in AI (2026-W42)\n\n"
        "1. Alpha Research\nhttps://example.com/alpha\n\n"
        "2. Beta Launch\nhttps://example.com/beta"
    )
    assert text == expected


def test_validate_roundup_urls_preserved():
    iso_week = "2026-W42"
    stories = [
        {"title": f"Story {i}", "url": f"https://example.com/{i}"}
        for i in range(1, 6)
    ]
    text = build_roundup_text(iso_week, stories)
    # 1 header + 5 stories = 6 parts
    assert validate_roundup_urls_preserved(text, stories, max_parts=6) is True
    # If capped to 2 parts, later stories will be truncated and URLs lost
    assert validate_roundup_urls_preserved(text, stories, max_parts=2) is False


def test_settings_is_scheduled_run():
    s_ci_sched = Settings(gemini_key="test", is_ci=True, github_event="schedule")
    assert s_ci_sched.is_scheduled_run is True

    s_local_sched = Settings(gemini_key="test", is_ci=False, github_event="schedule")
    assert s_local_sched.is_scheduled_run is False

    s_ci_dispatch = Settings(gemini_key="test", is_ci=True, github_event="workflow_dispatch")
    assert s_ci_dispatch.is_scheduled_run is False


@pytest.mark.asyncio
async def test_roundup_stage_decision_table_already_published(mocker):
    iso_week = "2026-W42"
    state = {
        "published_posts": [{"kind": "roundup", "week": iso_week, "url": f"generated:roundup:{iso_week}"}]
    }
    mocker.patch("bot.load_seen_articles", return_value=state)
    mock_client = AsyncMock()
    now = datetime(2026, 10, 16, 18, 17, tzinfo=timezone.utc)
    handled = await roundup_stage(mock_client, None, now=now)
    assert handled is True


@pytest.mark.asyncio
async def test_roundup_stage_decision_table_zero_eligible_stories_falls_back(mocker):
    iso_week = "2026-W42"
    state = {"published_posts": []}
    mocker.patch("bot.load_seen_articles", return_value=state)
    mock_client = AsyncMock()
    now = datetime(2026, 10, 16, 18, 17, tzinfo=timezone.utc)
    handled = await roundup_stage(mock_client, None, now=now)
    assert handled is False


@pytest.mark.asyncio
async def test_roundup_stage_successful_execution(mocker):
    iso_week = "2026-W42"
    state = {
        "published_posts": [
            {
                "title": f"Model {i}",
                "url": f"https://example.com/model-{i}",
                "published_at": "2026-10-15T12:00:00Z",
                "kind": "post",
                "posts": {"bluesky": {"uri": f"at://did:plc:123/app.bsky.feed.post/{i}"}},
            }
            for i in range(1, 4)
        ]
    }
    mocker.patch("bot.load_seen_articles", return_value=state)
    saved_states = []

    def mock_save(st, is_reservation=False):
        saved_states.append((dict(st), is_reservation))
        return True, st

    mocker.patch("bot.save_seen_articles", side_effect=mock_save)
    mocker.patch("bot.update_status_dashboard", new_callable=AsyncMock)

    mock_metrics = {
        "at://did:plc:123/app.bsky.feed.post/1": {"likes": 10, "reposts": 2, "replies": 1, "quotes": 0},
        "at://did:plc:123/app.bsky.feed.post/2": {"likes": 50, "reposts": 5, "replies": 3, "quotes": 1},
    }
    mocker.patch("src.engagement.fetch_bluesky_metrics", new_callable=AsyncMock, return_value=mock_metrics)

    # Mock broadcast
    mocker.patch(
        "bot.broadcast_stage",
        new_callable=AsyncMock,
        return_value=([bot.BroadcastResult("Bluesky", True, post_id="at://did:plc:123/app.bsky.feed.post/roundup")], None),
    )

    mock_client = AsyncMock()
    now = datetime(2026, 10, 16, 18, 17, tzinfo=timezone.utc)
    handled = await roundup_stage(mock_client, None, now=now)
    assert handled is True

    # Verify reservation then settlement happened
    assert len(saved_states) >= 2
    res_state, is_res = saved_states[0]
    assert is_res is True
    assert any(ps.get("url") == f"generated:roundup:{iso_week}" for ps in res_state.get("pending_stories", []))

    final_state, is_final = saved_states[-1]
    assert is_final is False
    assert any(
        e.get("kind") == "roundup" and e.get("week") == iso_week
        for e in final_state.get("published_posts", [])
    )


@pytest.mark.asyncio
async def test_roundup_stage_validation_failure_aborts_safely(mocker):
    iso_week = "2026-W42"
    state = {
        "published_posts": [
            {"title": "Story 1", "url": "https://example.com/1", "published_at": "2026-10-15T12:00:00Z", "kind": "post"}
        ]
    }
    mocker.patch("bot.load_seen_articles", return_value=state)
    mocker.patch("src.engagement.fetch_bluesky_metrics", new_callable=AsyncMock, return_value={})
    # Force validate_roundup_urls_preserved to fail
    mocker.patch("bot.validate_roundup_urls_preserved", return_value=False)
    mock_client = AsyncMock()
    now = datetime(2026, 10, 16, 18, 17, tzinfo=timezone.utc)
    handled = await roundup_stage(mock_client, None, now=now)
    # Must abort safely and return True (handled) so it does NOT fall back to normal news
    assert handled is True


@pytest.mark.asyncio
async def test_roundup_stage_post_approval_edit_validation(mocker):
    from src.models import PlatformDrafts
    iso_week = "2026-W42"
    state = {
        "published_posts": [
            {"title": "Story 1", "url": "https://example.com/1", "published_at": "2026-10-15T12:00:00Z", "kind": "post"}
        ]
    }
    mocker.patch("bot.load_seen_articles", return_value=state)
    mocker.patch("src.engagement.fetch_bluesky_metrics", new_callable=AsyncMock, return_value={})
    
    # First validation succeeds (pre-approval)
    # Second validation fails (post-approval edit stripped the URL)
    val_mock = mocker.patch("bot.validate_roundup_urls_preserved", side_effect=[True, False])
    
    object.__setattr__(bot.settings, "enable_telegram_approval", True)
    object.__setattr__(bot.settings, "is_dry_run", False)
    
    # Edited draft with URL stripped
    edited_drafts = PlatformDrafts(bluesky="No URL in here", threads="No URL", mastodon="No URL")
    mocker.patch("bot.send_draft_for_approval", new_callable=AsyncMock, return_value=(edited_drafts, None))

    mock_client = AsyncMock()
    now = datetime(2026, 10, 16, 18, 17, tzinfo=timezone.utc)
    handled = await roundup_stage(mock_client, None, now=now)
    assert handled is True
    assert val_mock.call_count == 2


@pytest.mark.asyncio
async def test_topic_command_bypasses_scheduled_roundup(mocker):
    """When a topic command is pending on Friday 18:17, roundup must not consume/discard it."""
    # Set up Friday 18:17 scheduled run in settings
    object.__setattr__(bot.settings, "is_dry_run", True)
    object.__setattr__(bot.settings, "is_ci", True)
    object.__setattr__(bot.settings, "github_event", "schedule")
    object.__setattr__(bot.settings, "force_roundup", False)
    object.__setattr__(bot.settings, "gemini_key", "test-key")

    friday_time = datetime(2026, 10, 16, 18, 17, tzinfo=timezone.utc)
    mock_dt = mocker.patch("bot.datetime")
    mock_dt.now.return_value = friday_time
    mock_dt.fromisoformat = datetime.fromisoformat

    mocker.patch("bot.check_for_telegram_topic", new_callable=AsyncMock, return_value=("topic", "quantum-ai"))
    mock_roundup = mocker.patch("bot.roundup_stage", new_callable=AsyncMock)
    mock_curate = mocker.patch("bot.curation_stage", new_callable=AsyncMock, return_value=MagicMock(top_articles=[]))
    mocker.patch("bot.prune_gemini_model_priority_async", new_callable=AsyncMock)
    mocker.patch("bot.synthesis_stage", new_callable=AsyncMock, return_value=(MagicMock(content=""), MagicMock()))

    # Run bot.main()
    await bot.main()

    # Roundup must NOT have been called because cmd_type was 'topic'
    mock_roundup.assert_not_called()
    # Curation must have received the requested topic
    mock_curate.assert_called_once_with(mocker.ANY, telegram_topic="quantum-ai")

