import pytest
import httpx
import io
from PIL import Image
from unittest.mock import AsyncMock, MagicMock, patch
from src.settings import settings, Settings
from src.models import (
    MediaAsset, MediaSource, ImageValidationResult,
    SynthesisResult, CurationResult, Article
)
from src.curator import validate_opengraph_image, generate_visual_prompt
from src.broadcaster import post_to_bluesky, post_to_mastodon, post_to_threads
from bot import media_strategy_stage, main
from src.telegram_gateway import send_draft_for_approval

# Helper to create dummy valid image bytes
def create_dummy_image(width=400, height=300):
    img = Image.new("RGB", (width, height), color="blue")
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()

@pytest.mark.asyncio
async def test_opengraph_validation_scenarios():
    # 1. Valid image
    img_bytes = create_dummy_image(400, 300)
    res = validate_opengraph_image(img_bytes, "https://example.com/valid.jpg")
    assert res.valid
    assert res.width == 400
    assert res.height == 300
    assert res.mime_type == "image/jpeg"

    # 2. Unsupported MIME type (empty bytes or malformed)
    res = validate_opengraph_image(b"malformed_data", "https://example.com/invalid.jpg")
    assert not res.valid
    assert "unsupported_mime" in res.reason or "decode_failed" in res.reason

    # 3. Small dimensions
    small_bytes = create_dummy_image(150, 150)
    res = validate_opengraph_image(small_bytes, "https://example.com/small.jpg")
    assert not res.valid
    assert "dimensions_too_small" in res.reason

    # 4. Extreme aspect ratio
    extreme_bytes = create_dummy_image(2000, 200) # 10:1 ratio
    res = validate_opengraph_image(extreme_bytes, "https://example.com/extreme.jpg")
    assert not res.valid
    assert "extreme_aspect_ratio" in res.reason

    # 5. Placeholder URL pattern
    placeholder_bytes = create_dummy_image(400, 300)
    res = validate_opengraph_image(placeholder_bytes, "https://example.com/arxiv-logo.jpg")
    assert not res.valid
    assert "placeholder" in res.reason

@pytest.mark.asyncio
async def test_media_strategy_linked_valid_opengraph(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, enable_image_gen=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    # Mock get_link_metadata to return valid og bytes
    valid_bytes = create_dummy_image()
    mocker.patch("bot.get_link_metadata", new_callable=AsyncMock, return_value={
        "image": valid_bytes,
        "image_url": "https://example.com/valid.jpg",
        "title": "Test Title",
        "description": "Test Desc",
        "url": "https://example.com/article"
    })
    mocker.patch("src.curator.generate_image_alt_text", new_callable=AsyncMock, return_value="Alt Text description")

    synthesis = SynthesisResult(content="Article post", lead_link="https://example.com/article", topic="General")
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])

    async with httpx.AsyncClient() as client:
        media = await media_strategy_stage(client, None, synthesis, curation)

    assert media is not None
    assert media.source == MediaSource.OPENGRAPH
    assert media.image_bytes == valid_bytes
    assert media.public_url == "https://example.com/valid.jpg"
    assert media.alt_text == "Alt Text description"

@pytest.mark.asyncio
async def test_media_strategy_invalid_opengraph_fallback_success(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, enable_image_gen=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    # 1. Invalid og bytes (too small)
    invalid_bytes = create_dummy_image(100, 100)
    mocker.patch("bot.get_link_metadata", new_callable=AsyncMock, return_value={
        "image": invalid_bytes,
        "image_url": "https://example.com/invalid.jpg",
        "title": "Test Title",
        "description": "Test Desc",
        "url": "https://example.com/article"
    })
    
    # AI Fallback mocks
    mocker.patch("src.curator.generate_visual_prompt", new_callable=AsyncMock, return_value="Tech Prompt")
    gen_bytes = create_dummy_image()
    mocker.patch("src.curator.generate_nvidia_image", new_callable=AsyncMock, return_value=gen_bytes)
    mocker.patch("src.curator.generate_image_alt_text", new_callable=AsyncMock, return_value="Generated Alt")

    synthesis = SynthesisResult(content="Article post", lead_link="https://example.com/article", topic="General")
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])

    async with httpx.AsyncClient() as client:
        media = await media_strategy_stage(client, None, synthesis, curation)

    assert media is not None
    assert media.source == MediaSource.GENERATED
    assert media.image_bytes == gen_bytes
    assert media.public_url is None
    assert media.alt_text == "Generated Alt"

@pytest.mark.asyncio
async def test_media_strategy_invalid_opengraph_fallback_failed(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, enable_image_gen=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    # Return None metadata -> fails OpenGraph
    mocker.patch("bot.get_link_metadata", new_callable=AsyncMock, return_value=None)
    
    # Fail AI generation
    mocker.patch("src.curator.generate_visual_prompt", new_callable=AsyncMock, return_value="Tech Prompt")
    mocker.patch("src.curator.generate_nvidia_image", new_callable=AsyncMock, return_value=None)

    synthesis = SynthesisResult(content="Article post", lead_link="https://example.com/article", topic="General")
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])

    async with httpx.AsyncClient() as client:
        media = await media_strategy_stage(client, None, synthesis, curation)

    # Failures result in no media
    assert media is None

@pytest.mark.asyncio
async def test_media_strategy_scratch_post_enabled(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, enable_image_gen=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    mocker.patch("src.curator.generate_visual_prompt", new_callable=AsyncMock, return_value="Tech Prompt")
    gen_bytes = create_dummy_image()
    mocker.patch("src.curator.generate_nvidia_image", new_callable=AsyncMock, return_value=gen_bytes)
    mocker.patch("src.curator.generate_image_alt_text", new_callable=AsyncMock, return_value="Generated Alt")

    # No lead link (scratch-generated)
    synthesis = SynthesisResult(content="Scratch post content", lead_link=None, topic="Agents")
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])

    async with httpx.AsyncClient() as client:
        media = await media_strategy_stage(client, None, synthesis, curation)

    assert media is not None
    assert media.source == MediaSource.GENERATED
    assert media.image_bytes == gen_bytes
    assert media.public_url is None
    assert media.alt_text == "Generated Alt"

@pytest.mark.asyncio
async def test_media_strategy_scratch_post_disabled(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, enable_image_gen=False)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    # Scratch post with gen disabled
    synthesis = SynthesisResult(content="Scratch post content", lead_link=None, topic="Agents")
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])

    async with httpx.AsyncClient() as client:
        media = await media_strategy_stage(client, None, synthesis, curation)

    assert media is None

@pytest.mark.asyncio
async def test_bluesky_broadcaster_options(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, bsky_handle="test", bsky_password="test")
    monkeypatch.setattr("src.broadcaster.settings", mock_settings)

    bsky_client = MagicMock()
    bsky_client.send_post = AsyncMock()
    mock_blob = {
        "ref": {"$link": "mock_cid"},
        "mime_type": "image/jpeg",
        "size": 100
    }
    bsky_client.upload_blob = AsyncMock(return_value=MagicMock(blob=mock_blob))
    
    # 1. Lead link with media -> AppBskyEmbedExternal
    valid_bytes = create_dummy_image()
    media = MediaAsset(source=MediaSource.OPENGRAPH, image_bytes=valid_bytes, public_url="https://example.com/img.jpg")
    
    mocker.patch("src.broadcaster.get_link_metadata", new_callable=AsyncMock, return_value={
        "title": "Title", "description": "Desc", "url": "https://example.com/article", "image": valid_bytes
    })

    async with httpx.AsyncClient() as client:
        await post_to_bluesky(bsky_client, client, "Text content", "https://example.com/article", media)
    
    assert bsky_client.send_post.called
    embed = bsky_client.send_post.call_args[1]["embed"]
    assert embed.__class__.__name__ == "Main" # AppBskyEmbedExternal
    assert embed.external.uri == "https://example.com/article"
    assert embed.external.thumb is not None
    assert embed.external.thumb.ref.link == "mock_cid"

    # Reset
    bsky_client.send_post.reset_mock()

    # 2. No lead link but media exists -> AppBskyEmbedImages
    await post_to_bluesky(bsky_client, client, "Text content", None, media)
    assert bsky_client.send_post.called
    embed = bsky_client.send_post.call_args[1]["embed"]
    assert embed.__class__.__name__ == "Main" # AppBskyEmbedImages
    assert len(embed.images) == 1

@pytest.mark.asyncio
async def test_threads_broadcaster_scenarios(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, threads_user_id="test", threads_token="test")
    monkeypatch.setattr("src.broadcaster.settings", mock_settings)

    client = MagicMock()
    # Mock container finished check and publish response
    container_res = MagicMock(status_code=200)
    container_res.json.return_value = {"id": "container123"}
    status_res = MagicMock(status_code=200)
    status_res.json.return_value = {"status": "FINISHED"}
    publish_res = MagicMock(status_code=200)
    publish_res.json.return_value = {"id": "post123"}
    
    client.post = AsyncMock(side_effect=[container_res, publish_res])
    client.get = AsyncMock(return_value=status_res)

    # 1. OpenGraph with public URL
    media = MediaAsset(source=MediaSource.OPENGRAPH, public_url="https://example.com/public.jpg", image_bytes=b"bytes")
    await post_to_threads(client, "Text content", media)
    assert client.post.called
    payload = client.post.call_args_list[0][1]["data"]
    assert payload["media_type"] == "IMAGE"
    assert payload["image_url"] == "https://example.com/public.jpg"

    # Reset
    client.post.reset_mock()
    client.post.side_effect = [container_res, publish_res]

    # 2. Generated with no public URL -> fall back to text-only
    media_gen = MediaAsset(source=MediaSource.GENERATED, public_url=None, image_bytes=b"bytes")
    await post_to_threads(client, "Text content", media_gen)
    payload = client.post.call_args_list[0][1]["data"]
    assert payload["media_type"] == "TEXT"
    assert "image_url" not in payload

@pytest.mark.asyncio
async def test_mastodon_broadcaster_scenarios(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, mastodon_token="test", mastodon_base_url="https://mastodon.social")
    monkeypatch.setattr("src.broadcaster.settings", mock_settings)

    # Mock Mastodon class
    mock_mastodon = MagicMock()
    mock_mastodon.media_post = MagicMock(side_effect=Exception("Upload failed"))
    mock_mastodon.status_post = MagicMock()
    mocker.patch("src.broadcaster.Mastodon", return_value=mock_mastodon)

    # If upload fails, it should still post status
    media = MediaAsset(source=MediaSource.GENERATED, image_bytes=b"bytes", alt_text="Alt")
    await post_to_mastodon("Text content", media)
    
    assert mock_mastodon.status_post.called
    assert mock_mastodon.status_post.call_args[1]["media_ids"] is None or len(mock_mastodon.status_post.call_args[1]["media_ids"]) == 0

@pytest.mark.asyncio
async def test_media_stage_resilience(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, enable_image_gen=True)
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    # Simulate exception inside media strategy
    mocker.patch("bot.get_link_metadata", side_effect=Exception("Network failure"))
    mocker.patch("src.curator.generate_visual_prompt", side_effect=Exception("Gemini failure"))

    synthesis = SynthesisResult(content="Article post", lead_link="https://example.com/article", topic="General")
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])

    async with httpx.AsyncClient() as client:
        # Should not raise exception
        media = await media_strategy_stage(client, None, synthesis, curation)

    assert media is None

@pytest.mark.asyncio
async def test_media_strategy_imagen_provider(monkeypatch, mocker):
    mock_settings = Settings(gemini_key="mock", is_dry_run=False, enable_image_gen=True, image_provider="imagen")
    monkeypatch.setattr("src.settings.settings", mock_settings)
    monkeypatch.setattr("src.curator.settings", mock_settings)
    monkeypatch.setattr("bot.settings", mock_settings)

    mocker.patch("src.curator.generate_visual_prompt", new_callable=AsyncMock, return_value="Tech Prompt")
    
    # Mock Imagen generation
    gen_bytes = create_dummy_image()
    mocker.patch("src.curator.generate_imagen_image", new_callable=AsyncMock, return_value=gen_bytes)
    mocker.patch("src.curator.generate_image_alt_text", new_callable=AsyncMock, return_value="Generated Alt")

    synthesis = SynthesisResult(content="Scratch post content", lead_link=None, topic="Agents")
    curation = CurationResult(top_articles=[], seen_links=[], recent_topics=[])

    async with httpx.AsyncClient() as client:
        media = await media_strategy_stage(client, MagicMock(), synthesis, curation)

    assert media is not None
    assert media.source == MediaSource.GENERATED
    assert media.image_bytes == gen_bytes

def test_smart_split_paragraph_truncation():
    from src.utils import smart_split
    # Para 1 is small, Para 2 is small. Limit fits both.
    text = "Paragraph one.\n\nParagraph two."
    res = smart_split(text, limit=100, max_chunks=2)
    assert len(res) == 2
    assert res[0] == "Paragraph one."
    assert res[1] == "Paragraph two."

    # Para 1 needs to be split (limit = 10), which takes up the full budget of 2 chunks.
    # Para 2 exists. The second paragraph should be dropped and the last chunk of Para 1 gets "..."
    text2 = "abcdef ghijkl\n\nParagraph two."
    res2 = smart_split(text2, limit=8, max_chunks=2)
    assert len(res2) == 2
    assert res2[0] == "abcdef"
    assert res2[1] == "ghijkl..."
