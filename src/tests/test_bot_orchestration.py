import pytest
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import Article, CurationResult, SynthesisResult
from src.settings import settings

@pytest.mark.asyncio
async def test_lead_article_resolution_missing_lead_aborts(mocker):
    """Verify bot aborts before broadcast if synthesis lead_link is missing."""
    import bot

    curation = CurationResult(
        top_articles=[Article(title="Art 1", link="https://example.com/art1", summary="s", published="2026-08-18", source="src", score=100)],
        seen_links=[],
        recent_topics=[],
        session_name="test_session"
    )
    synthesis = SynthesisResult(
        content="Test content",
        lead_link=None, # Missing lead link
        topic="AI"
    )

    mocker.patch("sys.exit", side_effect=SystemExit(1))
    mocker.patch("bot.check_for_telegram_topic", return_value=(None, None))
    mocker.patch("bot.curation_stage", return_value=curation)
    mocker.patch("bot.synthesis_stage", return_value=(synthesis, curation))
    mocker.patch("bot.media_strategy_stage", return_value=None)

    with pytest.raises(SystemExit) as exc_info:
        await bot.main()
    assert exc_info.value.code == 1

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

    object.__setattr__(settings, "gist_id", "test_id")
    object.__setattr__(settings, "gist_token", "test_token")
    object.__setattr__(settings, "is_dry_run", False)

    mocker.patch("sys.exit", side_effect=SystemExit(1))
    mocker.patch("bot.check_for_telegram_topic", return_value=(None, None))
    mocker.patch("bot.curation_stage", return_value=curation)
    mocker.patch("bot.synthesis_stage", return_value=(synthesis, curation))
    mocker.patch("bot.media_strategy_stage", return_value=None)
    mocker.patch("bot.load_seen_articles", return_value={"revision": 1, "pending_stories": []})
    mocker.patch("bot.save_seen_articles", return_value=False)
    
    mock_broadcast = mocker.patch("bot.broadcast_stage", new_callable=AsyncMock)

    with pytest.raises(SystemExit) as exc_info:
        await bot.main()

    assert exc_info.value.code == 1
    mock_broadcast.assert_not_called()
