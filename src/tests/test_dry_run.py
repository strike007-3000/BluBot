import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.settings import Settings
from bot import curation_stage, synthesis_stage, broadcast_stage, persistence_stage
from src.models import CurationResult, SynthesisResult, Article

@pytest.mark.asyncio
async def test_dry_run_broadcaster_bypasses_real_posts(monkeypatch):
    """Verify that broadcast_stage returns mock successes and does not post to APIs in dry-run."""
    monkeypatch.setattr("src.settings.settings", Settings(gemini_key="mock", is_dry_run=True))
    
    synthesis = SynthesisResult(
        content="Test content",
        lead_link="https://example.com",
        topic="Test Topic",
        image_data=b"imagebytes",
        image_alt_text="Alt Text"
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
    """Verify that persistence_stage skips saving files in dry-run mode."""
    monkeypatch.setattr("src.settings.settings", Settings(gemini_key="mock", is_dry_run=True))
    
    mock_save = mocker.patch("bot.save_seen_articles")
    mock_dashboard = mocker.patch("bot.update_status_dashboard")
    mock_profile = mocker.patch("bot.update_social_profiles")
    
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])
    synthesis = SynthesisResult(content="test", lead_link=None, topic="General")
    
    await persistence_stage(curation, synthesis)
    
    mock_save.assert_not_called()
    mock_dashboard.assert_not_called()
    mock_profile.assert_not_called()
