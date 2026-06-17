import pytest
from bot import article_matches_topic, curation_stage, synthesis_stage
from src.models import Article, CurationResult
from src.settings import Settings
import httpx
from unittest.mock import AsyncMock, MagicMock

def test_article_matches_topic():
    # Test simple match
    assert article_matches_topic(
        title="SpaceX acquires AI coding assistant Cursor in a $60B deal",
        summary="Cursor, developed by Anysphere, is acquired.",
        topic="Why Cursor acquisition could be concerning"
    ) is True

    # Test case insensitivity
    assert article_matches_topic(
        title="spacex acquires cursor",
        summary="some text",
        topic="CURSOR"
    ) is True

    # Test no match
    assert article_matches_topic(
        title="Microsoft announces new updates to VS Code",
        summary="GitHub updates Copilot features.",
        topic="Cursor acquisition"
    ) is False

    # Test stopword ignoring (only stopword in topic)
    assert article_matches_topic(
        title="Microsoft announces new updates to VS Code",
        summary="GitHub updates Copilot features.",
        topic="why did it happen"
    ) is False

    # Test brand name / word boundary matching (should not truncate OpenAI to open and match open source)
    assert article_matches_topic(
        title="Microsoft announces new open source model",
        summary="This is an open source AI project.",
        topic="OpenAI"
    ) is False

    assert article_matches_topic(
        title="OpenAI releases new model",
        summary="Details on OpenAI's release.",
        topic="OpenAI"
    ) is True

@pytest.mark.asyncio
async def test_curation_stage_with_matching_telegram_topic(monkeypatch, mocker):
    # Mock settings to avoid dry run issues
    monkeypatch.setattr("src.settings.settings", Settings(gemini_key="mock", is_dry_run=False))
    
    # Mock fetch_news to return specific items
    mock_items = [
        {
            "title": "SpaceX acquires Cursor",
            "link": "https://example.com/cursor",
            "summary": "Acquisition details",
            "published": "2026-06-17T00:00:00Z",
            "source": "TechCrunch",
            "score": 80
        },
        {
            "title": "Unrelated AI News",
            "link": "https://example.com/unrelated",
            "summary": "Random summary",
            "published": "2026-06-17T00:00:00Z",
            "source": "VentureBeat",
            "score": 50
        }
    ]
    
    mocker.patch("bot.load_seen_articles", return_value={"links": [], "recent_topics": []})
    mocker.patch("bot.fetch_news", return_value=mock_items)
    
    # Mock VanguardManager to avoid live audit/networking
    mock_vanguard = MagicMock()
    mock_vanguard.get_active_feeds = MagicMock(return_value=[])
    mock_vanguard.audit_and_update = AsyncMock()
    mocker.patch("src.feed_vanguard.VanguardManager", return_value=mock_vanguard)
    
    async with httpx.AsyncClient() as client:
        res = await curation_stage(client, telegram_topic="Cursor acquisition")
        
        # Should only contain the matching article
        assert len(res.top_articles) == 1
        assert res.top_articles[0].title == "SpaceX acquires Cursor"
        assert res.top_articles[0].source == "TechCrunch"

@pytest.mark.asyncio
async def test_curation_stage_fallback_when_no_match(monkeypatch, mocker):
    monkeypatch.setattr("src.settings.settings", Settings(gemini_key="mock", is_dry_run=False))
    
    mock_items = [
        {
            "title": "Unrelated AI News",
            "link": "https://example.com/unrelated",
            "summary": "Random summary",
            "published": "2026-06-17T00:00:00Z",
            "source": "VentureBeat",
            "score": 50
        }
    ]
    
    mocker.patch("bot.load_seen_articles", return_value={"links": [], "recent_topics": []})
    mocker.patch("bot.fetch_news", return_value=mock_items)
    
    mock_vanguard = MagicMock()
    mock_vanguard.get_active_feeds = MagicMock(return_value=[])
    mock_vanguard.audit_and_update = AsyncMock()
    mocker.patch("src.feed_vanguard.VanguardManager", return_value=mock_vanguard)
    
    async with httpx.AsyncClient() as client:
        res = await curation_stage(client, telegram_topic="Cursor acquisition")
        
        # Should fall back to the mock intercept article since no match was found
        assert len(res.top_articles) == 1
        assert res.top_articles[0].source == "Telegram Intercept"
        assert "On-demand topic request" in res.top_articles[0].title
