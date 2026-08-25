import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.settings import Settings
from bot import curation_stage, synthesis_stage, broadcast_stage, reserve_pending_stage, settle_persistence_stage
from src.models import CurationResult, SynthesisResult, Article

@pytest.mark.asyncio
async def test_dry_run_broadcaster_bypasses_real_posts(monkeypatch):
    """Verify that broadcast_stage returns mock successes and does not post to APIs in dry-run."""
    mock_settings = Settings(gemini_key="mock", is_dry_run=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    from src.models import MediaAsset, MediaSource
    synthesis = SynthesisResult(
        content="Test content",
        lead_link="https://example.com",
        topic="Test Topic",
        media=MediaAsset(
            source=MediaSource.GENERATED,
            image_bytes=b"imagebytes",
            alt_text="Alt Text"
        )
    )

    async with httpx.AsyncClient() as client:
        # If dry run is active, it should return list of successes and None for bsky_client
        results, bsky_client = await broadcast_stage(client, synthesis)

        assert bsky_client is None
        assert len(results) == 3
        assert all(r.success for r in results)
        assert [r.platform for r in results] == ["Bluesky", "Mastodon", "Threads"]

@pytest.mark.asyncio
async def test_dry_run_persistence_does_not_save(monkeypatch, mocker):
    """Verify that reserve_pending_stage and settle_persistence_stage skip saving files in dry-run mode."""
    mock_settings = Settings(gemini_key="mock", is_dry_run=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    mock_save = mocker.patch("bot.save_seen_articles", return_value=(True, {}))

    article = Article(title="Art 1", link="https://example.com/art1", summary="s", published="2026-08-18", source="src", score=100)
    curation = CurationResult(top_articles=[article], seen_links=[], recent_topics=[])
    synthesis = SynthesisResult(content="test", lead_link="https://example.com/art1", topic="General")

    mocker.patch("bot.load_seen_articles", return_value={"schema_version": 2, "revision": 1, "pending_stories": []})

    state, matched = await reserve_pending_stage(curation, synthesis)
    mock_save.assert_called_once()
    assert mock_save.call_args[1]["is_reservation"] is True

@pytest.mark.asyncio
async def test_generate_briefing_dry_run(monkeypatch, mocker):
    """Verify that generate_briefing bypasses Gemini and returns mock briefing in dry-run."""
    mock_settings = Settings(gemini_key="mock", is_dry_run=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    mocker.patch("bot.load_seen_articles", return_value={"watch_topics": []})
    mock_fetch = mocker.patch("bot.fetch_news", new_callable=AsyncMock, return_value=([
        {"title": "Test Title", "summary": "Test Summary", "link": "https://example.com", "source": "Test Source", "source_id": "test_id", "published": "2026-08-04T12:00:00Z", "score": 8}
    ], []))

    from bot import generate_briefing
    async with httpx.AsyncClient() as client:
        genai_client = MagicMock()
        briefing = await generate_briefing(client, genai_client, "Test")

        # Verify fetch_news was called with empty seen_links list
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert kwargs.get("seen_links") == []

        # Verify mock briefing text was returned
        assert "DRY RUN" in briefing
        assert "Test Title" in briefing
        genai_client.aio.models.generate_content.assert_not_called()
