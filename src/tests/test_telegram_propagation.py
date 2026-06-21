import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from bot import main
from src.settings import Settings
from src.models import CurationResult, SynthesisResult

@pytest.mark.asyncio
async def test_telegram_approval_image_url_propagation_changed(monkeypatch, mocker):
    """Test that image_url is set to None if image bytes are changed/regenerated."""
    mock_settings = Settings(
        gemini_key="mock",
        nvidia_key="mock",
        enable_telegram_approval=True,
        is_dry_run=False,  # Set to False so approval logic is entered
        telegram_bot_token="mock_token",
        telegram_user_id="mock_user",
        bsky_handle="mock",
        bsky_password="mock",
        github_event="push"
    )
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    # Mock top-level functions in bot.py to isolate Telegram approval logic
    mocker.patch("bot.prune_gemini_model_priority_async", new_callable=AsyncMock)
    mocker.patch("bot.check_for_telegram_topic", new_callable=AsyncMock, return_value=None)
    
    curation_mock = CurationResult(top_articles=[], seen_links=[], recent_topics=[])
    mocker.patch("bot.curation_stage", new_callable=AsyncMock, return_value=curation_mock)

    original_synthesis = SynthesisResult(
        content="Original Content",
        lead_link="https://example.com",
        topic="General",
        image_data=b"original_image_bytes",
        image_url="https://example.com/image.png",
        image_alt_text="Original Alt"
    )
    mocker.patch("bot.synthesis_stage", new_callable=AsyncMock, return_value=(original_synthesis, curation_mock))
    
    # Mock send_draft_for_approval to return DIFFERENT image bytes
    mocker.patch(
        "bot.send_draft_for_approval",
        new_callable=AsyncMock,
        return_value=("Approved Content", b"regenerated_image_bytes", "New Alt")
    )

    # Mock stage after approval to capture the synthesis passed to it
    broadcast_mock = mocker.patch("bot.broadcast_stage", new_callable=AsyncMock, return_value=([], None))
    mocker.patch("bot.persistence_stage", new_callable=AsyncMock)

    # Mock client and genai
    mocker.patch("google.genai.Client")

    await main()

    # Verify that the synthesis object passed to broadcast_stage has image_url cleared (None)
    assert broadcast_mock.called
    called_synthesis = broadcast_mock.call_args[0][1]
    assert called_synthesis.image_url is None
    assert called_synthesis.image_data == b"regenerated_image_bytes"
    assert called_synthesis.content == "Approved Content"
    assert called_synthesis.image_alt_text == "New Alt"

@pytest.mark.asyncio
async def test_telegram_approval_image_url_propagation_unchanged(monkeypatch, mocker):
    """Test that image_url is preserved if image bytes remain the same."""
    mock_settings = Settings(
        gemini_key="mock",
        nvidia_key="mock",
        enable_telegram_approval=True,
        is_dry_run=False,
        telegram_bot_token="mock_token",
        telegram_user_id="mock_user",
        bsky_handle="mock",
        bsky_password="mock",
        github_event="push"
    )
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    mocker.patch("bot.prune_gemini_model_priority_async", new_callable=AsyncMock)
    mocker.patch("bot.check_for_telegram_topic", new_callable=AsyncMock, return_value=None)
    
    curation_mock = CurationResult(top_articles=[], seen_links=[], recent_topics=[])
    mocker.patch("bot.curation_stage", new_callable=AsyncMock, return_value=curation_mock)

    original_synthesis = SynthesisResult(
        content="Original Content",
        lead_link="https://example.com",
        topic="General",
        image_data=b"original_image_bytes",
        image_url="https://example.com/image.png",
        image_alt_text="Original Alt"
    )
    mocker.patch("bot.synthesis_stage", new_callable=AsyncMock, return_value=(original_synthesis, curation_mock))
    
    # Mock send_draft_for_approval to return the SAME image bytes
    mocker.patch(
        "bot.send_draft_for_approval",
        new_callable=AsyncMock,
        return_value=("Approved Content", b"original_image_bytes", "Original Alt")
    )

    broadcast_mock = mocker.patch("bot.broadcast_stage", new_callable=AsyncMock, return_value=([], None))
    mocker.patch("bot.persistence_stage", new_callable=AsyncMock)

    mocker.patch("google.genai.Client")

    await main()

    # Verify that the synthesis object passed to broadcast_stage preserves image_url
    assert broadcast_mock.called
    called_synthesis = broadcast_mock.call_args[0][1]
    assert called_synthesis.image_url == "https://example.com/image.png"
    assert called_synthesis.image_data == b"original_image_bytes"
    assert called_synthesis.content == "Approved Content"
    assert called_synthesis.image_alt_text == "Original Alt"
