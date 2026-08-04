import pytest
from datetime import datetime, timedelta, timezone
from src.curator import calculate_relevance_score, strip_markdown, fetch_news
from src.config import BASE_TIER_1, SIGNAL_BOOST, MOMENTUM_BOOST, SYNERGY_BONUS

def test_calculate_relevance_score_factors():
    """Verify that different scoring factors are correctly applied."""
    now_utc = datetime.now(timezone.utc)
    
    # 1. Tier 1 Research Lab
    item_tier1 = {
        "title": "New Model Release",
        "summary": "This is a summary",
        "link": "https://openai.com/news/1",
        "source_id": "openai_news"
    }
    score_tier1 = calculate_relevance_score(item_tier1, now_utc, now_utc)
    assert score_tier1 >= 30
    
    # 2. Keyword Boost
    item_signal = {
        "title": "Autonomous Agent SOTA",
        "summary": "New breakthrough in agentic reasoning",
        "link": "https://example.com/1",
        "source_id": "unknown"
    }
    score_signal = calculate_relevance_score(item_signal, now_utc, now_utc)
    assert score_signal >= SIGNAL_BOOST
    
    # 3. Momentum Product
    item_momentum = {
        "title": "GPT-5 First Look",
        "summary": "Testing the new model",
        "link": "https://example.com/2",
        "source_id": "unknown"
    }
    score_momentum = calculate_relevance_score(item_momentum, now_utc, now_utc)
    assert score_momentum >= MOMENTUM_BOOST

def test_strip_markdown_cleanliness():
    """Verify that bold and italic markers are stripped."""
    text = "The **latest** news on *AI* and __reasoning__."
    assert strip_markdown(text) == "The latest news on AI and reasoning."
    assert strip_markdown("") == ""
    assert strip_markdown(None) is None

@pytest.mark.asyncio
async def test_fetch_single_feed_atom_updated_fallback(mock_httpx_client, mocker):
    """Verify Atom updated_parsed is used when published_parsed is absent."""
    from src.curator import fetch_single_feed
    now_utc = datetime.now(timezone.utc)
    
    mock_entry = mocker.MagicMock()
    mock_entry.link = "https://github.com/vllm-project/vllm/releases/tag/v0.26.0"
    mock_entry.title = "v0.26.0 Release"
    mock_entry.summary = "Release notes"
    del mock_entry.published_parsed  # Absent in Atom releases
    mock_entry.updated_parsed = (2026, 8, 4, 12, 0, 0, 1, 216, 0)
    
    mock_feed = mocker.MagicMock()
    mock_feed.entries = [mock_entry]
    mock_feed.feed = mocker.MagicMock(title="vLLM Releases")
    
    mocker.patch("feedparser.parse", return_value=mock_feed)
    
    mock_resp = mocker.MagicMock()
    mock_resp.content = b"<atom feed>"
    mock_httpx_client.get = mocker.AsyncMock(return_value=mock_resp)
    
    items = await fetch_single_feed(mock_httpx_client, "https://github.com/vllm-project/vllm/releases.atom", now_utc - timedelta(days=2), now_utc, [], [])
    assert len(items) == 1
    assert items[0]["published"].startswith("2026-08-04T12:00:00")

@pytest.mark.asyncio
async def test_fetch_news_synergy_and_deduplication(mock_httpx_client, mocker):
    """Verify that cross-source duplicate stories get a synergy bonus and are ranked correctly."""
    # Mocking fetch_single_feed to return specific items with different publisher domains
    item_a = {"title": "Llama 4 Release Announced", "link": "https://site1.com/a", "summary": "...", "source": "Site 1", "source_id": "site1", "score": 10}
    item_b = {"title": "Llama 4 Release Details", "link": "https://site2.com/b", "summary": "...", "source": "Site 2", "source_id": "site2", "score": 10} # Corroborating domain
    item_c = {"title": "Story C Unrelated Release", "link": "https://site3.com/c", "summary": "...", "source": "Site 3", "source_id": "site3", "score": 15}
    
    mocker.patch("src.curator.fetch_single_feed", side_effect=[[item_a], [item_b], [item_c]])
    mocker.patch("src.curator.RSS_FEEDS", ["f1", "f2", "f3"])
    
    top_news = await fetch_news(mock_httpx_client)
    
    # Item A should be first because it gets SYNERGY_BONUS (10 + SYNERGY_BONUS = 25 > 15)
    assert len(top_news) == 2 # Clustered
    assert "Llama 4" in top_news[0]["title"]
    assert top_news[1]["title"] == "Story C Unrelated Release"
    assert top_news[0]["score"] == 10 + SYNERGY_BONUS
    assert top_news[0]["supporting_sources"] == ["Site 2"]

from src.curator import normalize_headline, calculate_title_similarity, cluster_articles

def test_headline_normalization():
    tokens1, ver1 = normalize_headline("OpenAI Announces GPT-4.5 Turbo Release | TechCrunch")
    assert ver1 == {"4.5"}
    assert "gpt-4.5" in tokens1 or "gpt" in tokens1
    assert "techcrunch" not in tokens1

    # Verify hyphenated product versions like GPT-5 are preserved and not stripped as suffix
    tokens_hyphen, ver_hyphen = normalize_headline("OpenAI releases GPT-5")
    assert ver_hyphen == {"5"}
    assert "gpt-5" in tokens_hyphen or "gpt" in tokens_hyphen

def test_title_similarity_matching():
    # Same announcement with different titles
    t1, v1 = normalize_headline("Meta Unveils Llama 4 Open Model")
    t2, v2 = normalize_headline("Meta Launches Llama 4 for Open Source")
    assert calculate_title_similarity(t1, v1, t2, v2) is True

    # Conflicting version numbers block merge
    t3, v3 = normalize_headline("Meta Releases Llama 4.0")
    t4, v4 = normalize_headline("Meta Releases Llama 4.5")
    assert calculate_title_similarity(t3, v3, t4, v4) is False

    # Short generic titles do not cluster
    t5, v5 = normalize_headline("AI News")
    t6, v6 = normalize_headline("AI Update")
    assert calculate_title_similarity(t5, v5, t6, v6) is False

def test_cluster_articles_corroboration():
    # Same publisher domain multiple articles -> no consensus bonus
    raw_same_domain = [
        {"title": "Claude 4 Released by Anthropic", "link": "https://anthropic.com/post1", "source": "Anthropic", "source_id": "anthropic", "score": 20},
        {"title": "Claude 4 Release Details", "link": "https://anthropic.com/post2", "source": "Anthropic", "source_id": "anthropic", "score": 15}
    ]
    clusters_same = cluster_articles(raw_same_domain)
    assert len(clusters_same) == 1
    assert clusters_same[0]["consensus_synergy"] is False
    assert clusters_same[0]["supporting_sources"] == ["Anthropic"]
    assert clusters_same[0]["score"] == 20

    # Cross-domain corroboration -> earns bonus and official source is lead
    raw_multi_domain = [
        {"title": "Claude 4 Released by Anthropic", "link": "https://techcrunch.com/claude", "source": "TechCrunch", "source_id": "techcrunch_ai", "score": 12},
        {"title": "Claude 4 Technical Breakthrough", "link": "https://anthropic.com/claude4", "source": "Anthropic", "source_id": "openai_news", "score": 30} # Official tier source
    ]
    clusters_multi = cluster_articles(raw_multi_domain)
    assert len(clusters_multi) == 1
    assert clusters_multi[0]["link"] == "https://anthropic.com/claude4"
    assert clusters_multi[0]["consensus_synergy"] is True
    assert clusters_multi[0]["score"] == 30 + SYNERGY_BONUS

@pytest.mark.asyncio
async def test_persistence_stage_saves_supporting_links(mocker, monkeypatch):
    from bot import persistence_stage
    from src.models import Article, CurationResult, SynthesisResult
    from src.settings import Settings
    
    mock_settings = Settings(gemini_key="mock", is_dry_run=False)
    monkeypatch.setattr("bot.settings", mock_settings)
    
    mock_load = mocker.patch("bot.load_seen_articles", return_value={"links": [], "recent_topics": []})
    mock_save = mocker.patch("bot.save_seen_articles")
    
    article = Article(
        title="Lead Article",
        link="https://lead.com/1",
        summary="...",
        published="2026-08-04T00:00:00Z",
        source="Lead",
        supporting_links=["https://supporting1.com/a", "https://supporting2.com/b"]
    )
    curation = CurationResult(top_articles=[article], seen_links=[], recent_topics=[])
    synthesis = SynthesisResult(content="Summary", lead_link="https://lead.com/1", topic="General")
    
    await persistence_stage(curation, synthesis)
    
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert "https://lead.com/1" in saved_data["links"]
    assert "https://supporting1.com/a" in saved_data["links"]
    assert "https://supporting2.com/b" in saved_data["links"]



from src.curator import supports_thinking, prune_gemini_model_priority_async, summarize_news
from src.config import GEMINI_MODEL_PRIORITY
from unittest.mock import MagicMock, AsyncMock, patch

def test_supports_thinking():
    assert supports_thinking("models/gemini-2.5-pro") is True
    assert supports_thinking("models/gemini-2.5-flash") is True
    assert supports_thinking("models/gemma-4-31b-it") is False
    assert supports_thinking("models/gemini-2.5-flash-lite") is True

@pytest.mark.asyncio
async def test_prune_gemini_model_priority_async(monkeypatch):
    from src.settings import Settings
    monkeypatch.setattr("src.curator.settings", Settings(gemini_key="mock", is_dry_run=False))
    monkeypatch.setenv("CI", "false")
    original_priority = list(GEMINI_MODEL_PRIORITY)
    
    # Mock list models async generator
    class AsyncListMock:
        def __init__(self, models):
            self.models = models
        def __aiter__(self):
            self.models_iter = iter(self.models)
            return self
        async def __anext__(self):
            try:
                return next(self.models_iter)
            except StopIteration:
                raise StopAsyncIteration

    mock_client = MagicMock()
    m1 = MagicMock()
    m1.name = "models/gemma-4-31b-it"
    m2 = MagicMock()
    m2.name = "models/gemini-2.5-flash-lite"
    mock_model_list = [m1, m2]
    mock_client.aio.models.list = AsyncMock(return_value=AsyncListMock(mock_model_list))
    
    await prune_gemini_model_priority_async(mock_client)
    
    assert "models/gemma-4-31b-it" in GEMINI_MODEL_PRIORITY
    assert "models/gemini-2.5-flash-lite" in GEMINI_MODEL_PRIORITY
    assert "models/gemini-3.1-flash-lite-preview" not in GEMINI_MODEL_PRIORITY
    
    # Restore
    GEMINI_MODEL_PRIORITY.clear()
    GEMINI_MODEL_PRIORITY.extend(original_priority)

@pytest.mark.asyncio
async def test_summarize_news_with_thinking_budget(monkeypatch):
    """Verify that summarize_news includes thinking_config when supported by the model."""
    monkeypatch.setenv("CI", "true")
    
    # Force GEMINI_MODEL_PRIORITY to only contain a model supporting thinking
    original_priority = list(GEMINI_MODEL_PRIORITY)
    GEMINI_MODEL_PRIORITY.clear()
    GEMINI_MODEL_PRIORITY.append("models/gemini-2.5-flash")
    
    # Mock client and response
    mock_client = MagicMock()
    mock_response = AsyncMock()
    mock_response.text = "TOPIC: LLMs\nBODY: This is the news brief."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    # Patch genai.Client and settings singleton
    with patch("google.genai.Client", return_value=mock_client), \
         patch("src.curator.settings") as mock_settings:
        mock_settings.gemini_key = "test_key"
        mock_settings.thinking_budget = 500
        mock_settings.is_dry_run = False
        
        # We need some dummy news items
        news_items = [{"title": "Important AI Breakthrough", "link": "https://openai.com/1", "source": "OpenAI", "score": 100}]
        context = {"day": "Monday", "session": "Morning"}
        await summarize_news(news_items, context)
        
    # Verify generate_content was called with thinking_config containing the budget
    args, kwargs = mock_client.aio.models.generate_content.call_args
    config = kwargs.get("config")
    assert config is not None
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 500
    
    # Restore
    GEMINI_MODEL_PRIORITY.clear()
    GEMINI_MODEL_PRIORITY.extend(original_priority)

def test_registry_validation():
    from src.config import SOURCE_REGISTRY
    
    allowed_categories = {
        "research_lab", "enterprise", "practitioner", "open_source",
        "infrastructure", "business", "journalism", "academic", "critical"
    }
    allowed_qualities = {"official", "community", "academic", "journalism", "opinion"}
    
    ids = set()
    urls = set()
    
    for source in SOURCE_REGISTRY:
        # Check required fields
        assert "id" in source
        assert "name" in source
        assert "url" in source
        assert "category" in source
        assert "quality" in source
        assert "base_score" in source
        
        # Check duplicate IDs and URLs
        assert source["id"] not in ids, f"Duplicate ID: {source['id']}"
        assert source["url"] not in urls, f"Duplicate URL: {source['url']}"
        ids.add(source["id"])
        urls.add(source["url"])
        
        # Check allowed category and quality values
        assert source["category"] in allowed_categories, f"Invalid category: {source['category']}"
        assert source["quality"] in allowed_qualities, f"Invalid quality: {source['quality']}"

def test_fallback_behavior_unknown_source():
    now_utc = datetime.now(timezone.utc)
    item_unknown = {
        "title": "Title",
        "summary": "Summary",
        "link": "https://unknown.com/news",
        "source_id": "unknown"
    }
    score = calculate_relevance_score(item_unknown, now_utc, now_utc)
    assert score <= 0

from src.curator import (
    generate_ai_image,
    validate_image_bytes,
    generate_pollinations_image,
    generate_huggingface_image,
    generate_nvidia_image,
)
import httpx
from PIL import Image
import io

def create_valid_test_image_bytes() -> bytes:
    # Helper to generate minimal valid PNG bytes
    out = io.BytesIO()
    im = Image.new("RGBA", (10, 10), "blue")
    im.save(out, format="PNG")
    return out.getvalue()

def test_validate_image_bytes():
    valid_bytes = create_valid_test_image_bytes()
    assert validate_image_bytes(valid_bytes) is True
    assert validate_image_bytes(b"") is False
    assert validate_image_bytes(b"{}") is False
    assert validate_image_bytes(valid_bytes[:10]) is False  # truncated

@pytest.mark.asyncio
async def test_generate_pollinations_success(monkeypatch):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        pollinations_api_url="https://image.pollinations.ai/prompt/",
        image_provider="pollinations"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = valid_bytes
    mock_response.headers = {"Content-Type": "image/png"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    res = await generate_pollinations_image("Test Prompt", mock_client)
    assert res == valid_bytes

    # Pollinations free API needs no auth — just verify the URL format
    mock_client.get.assert_called_once()
    args, kwargs = mock_client.get.call_args
    assert "image.pollinations.ai/prompt/" in args[0]
    assert "Authorization" not in kwargs["headers"]

@pytest.mark.asyncio
async def test_generate_nvidia_success(monkeypatch):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        nvidia_key="nv-token",
        image_provider="nvidia"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    
    # NVIDIA NIM returns base64 string in JSON {"image": "..."}
    import base64
    encoded = base64.b64encode(valid_bytes).decode("utf-8")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"image": encoded})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    res = await generate_nvidia_image("Test Prompt", mock_client)
    assert res == valid_bytes

    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert "Authorization" in kwargs["headers"]
    assert "Bearer nv-token" in kwargs["headers"]["Authorization"]

@pytest.mark.asyncio
async def test_generate_nvidia_missing_key(monkeypatch):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        nvidia_key=None,
        image_provider="nvidia"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    mock_client = AsyncMock()
    res = await generate_nvidia_image("Test Prompt", mock_client)
    assert res is None

@pytest.mark.asyncio
async def test_generate_pollinations_works_without_key(monkeypatch):
    """Pollinations free API works without any API key."""
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        pollinations_api_key=None,
        pollinations_api_url="https://image.pollinations.ai/prompt/",
        image_provider="pollinations"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = valid_bytes
    mock_response.headers = {"Content-Type": "image/jpeg"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    res = await generate_pollinations_image("Test Prompt", mock_client)
    assert res == valid_bytes
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_generate_huggingface_success(monkeypatch):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        huggingface_api_key="hf-token",
        huggingface_image_model="stabilityai/stable-diffusion-3-medium-diffusers",
        image_provider="huggingface"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = valid_bytes
    mock_response.headers = {"Content-Type": "image/png"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    res = await generate_huggingface_image("Test Prompt", mock_client)
    assert res == valid_bytes

    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert "Authorization" in kwargs["headers"]
    assert "Bearer hf-token" in kwargs["headers"]["Authorization"]

@pytest.mark.asyncio
async def test_generate_huggingface_nvidia_fallback(monkeypatch):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        huggingface_api_key=None,
        nvidia_key="legacy-nv-token",
        huggingface_image_model="stabilityai/stable-diffusion-3-medium-diffusers",
        image_provider="huggingface"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = valid_bytes
    mock_response.headers = {"Content-Type": "image/png"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    res = await generate_huggingface_image("Test Prompt", mock_client)
    assert res == valid_bytes

    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert "Authorization" in kwargs["headers"]
    assert "Bearer legacy-nv-token" in kwargs["headers"]["Authorization"]

@pytest.mark.asyncio
async def test_dispatcher_pollinations_success_stops_chain(monkeypatch, mocker):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        image_provider="pollinations"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    
    # Mock the functions inside curator using mocker.patch
    mock_poll = mocker.patch("src.curator.IMAGE_GENERATORS", {
        "pollinations": AsyncMock(return_value=valid_bytes),
        "huggingface": AsyncMock(return_value=None)
    })

    mock_client = AsyncMock()
    res = await generate_ai_image(mock_client, None, "Test Prompt")
    assert res == valid_bytes
    assert mock_poll["pollinations"].await_count == 1
    assert mock_poll["huggingface"].await_count == 0

@pytest.mark.asyncio
async def test_dispatcher_pollinations_failure_uses_huggingface(monkeypatch, mocker):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        image_provider="pollinations"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_poll = mocker.patch("src.curator.IMAGE_GENERATORS", {
        "pollinations": AsyncMock(return_value=None),
        "huggingface": AsyncMock(return_value=valid_bytes)
    })

    mock_client = AsyncMock()
    res = await generate_ai_image(mock_client, None, "Test Prompt")
    assert res == valid_bytes
    assert mock_poll["pollinations"].await_count == 1
    assert mock_poll["huggingface"].await_count == 1

@pytest.mark.asyncio
async def test_dispatcher_explicit_imagen_provider(monkeypatch, mocker):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        image_provider="imagen"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    mock_imagen = mocker.patch("src.curator.generate_imagen_image", return_value=b"ImagenBytes")
    
    mock_client = AsyncMock()
    mock_genai = MagicMock()
    res = await generate_ai_image(mock_client, mock_genai, "Test Prompt")
    assert res == b"ImagenBytes"
    mock_imagen.assert_called_once()

@pytest.mark.asyncio
async def test_dispatcher_legacy_nvidia_provider_no_key(monkeypatch, mocker):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        image_provider="nvidia",
        nvidia_key=None
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_poll = mocker.patch("src.curator.IMAGE_GENERATORS", {
        "huggingface": AsyncMock(return_value=valid_bytes)
    })

    mock_client = AsyncMock()
    res = await generate_ai_image(mock_client, None, "Test Prompt")
    assert res == valid_bytes
    assert mock_poll["huggingface"].await_count == 1

@pytest.mark.asyncio
async def test_dispatcher_legacy_nvidia_provider_with_key(monkeypatch, mocker):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        image_provider="nvidia",
        nvidia_key="test-nv-key"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_poll = mocker.patch("src.curator.IMAGE_GENERATORS", {
        "nvidia": AsyncMock(return_value=valid_bytes)
    })

    mock_client = AsyncMock()
    res = await generate_ai_image(mock_client, None, "Test Prompt")
    assert res == valid_bytes
    assert mock_poll["nvidia"].await_count == 1

@pytest.mark.asyncio
async def test_dispatcher_unexpected_provider_exception_continues(monkeypatch, mocker):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        image_provider="pollinations"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    mock_poll = mocker.patch("src.curator.IMAGE_GENERATORS", {
        "pollinations": AsyncMock(side_effect=Exception("Unexpected API error")),
        "huggingface": AsyncMock(return_value=valid_bytes)
    })

    mock_client = AsyncMock()
    res = await generate_ai_image(mock_client, None, "Test Prompt")
    assert res == valid_bytes
    assert mock_poll["pollinations"].await_count == 1
    assert mock_poll["huggingface"].await_count == 1
@pytest.mark.asyncio
async def test_generate_huggingface_skips_without_keys(monkeypatch):
    """HF generator returns None when neither huggingface_api_key nor nvidia_key is set."""
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        huggingface_api_key=None,
        nvidia_key=None,
        huggingface_image_model="stabilityai/stable-diffusion-3-medium-diffusers",
        image_provider="huggingface"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    mock_client = AsyncMock()
    res = await generate_huggingface_image("Test Prompt", mock_client)
    assert res is None
    mock_client.post.assert_not_called()


def test_frozen_settings_setattr():
    """Verify object.__setattr__ bypass works on frozen Settings (used by diagnostic.py)."""
    from src.settings import Settings
    s = Settings(gemini_key="original")
    object.__setattr__(s, "gemini_key", "patched")
    assert s.gemini_key == "patched"


@pytest.mark.asyncio
async def test_pollinations_url_uses_correct_domain(monkeypatch):
    """Catch endpoint migrations: Pollinations URL must use image.pollinations.ai."""
    from src.settings import Settings
    from src.config import POLLINATIONS_API_URL
    mock_settings = Settings(
        gemini_key="mock",
        pollinations_api_url=POLLINATIONS_API_URL,
        image_provider="pollinations"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("skip"))

    await generate_pollinations_image("test", mock_client)
    url_called = mock_client.get.call_args[0][0]
    assert "image.pollinations.ai" in url_called, f"Pollinations URL stale: {url_called}"


@pytest.mark.asyncio
async def test_huggingface_url_uses_correct_domain(monkeypatch):
    """Catch endpoint migrations: HF URL must use router.huggingface.co."""
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        huggingface_api_key="hf-test",
        huggingface_image_model="test-model",
        image_provider="huggingface"
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("skip"))

    await generate_huggingface_image("test", mock_client)
    url_called = mock_client.post.call_args[0][0]
    assert "router.huggingface.co" in url_called, f"HF URL stale: {url_called}"


@pytest.mark.asyncio
async def test_generate_imagen_legacy_mode(monkeypatch):
    """Verify legacy imagen- model uses generate_images API."""
    monkeypatch.setattr("src.config.IMAGEN_MODEL", "imagen-4.0-generate-001")
    
    mock_response = MagicMock()
    mock_image = MagicMock()
    mock_image.image_bytes = b"LegacyImagenBytes"
    mock_response.generated_images = [MagicMock(image=mock_image)]
    
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_images = AsyncMock(return_value=mock_response)
    
    from src.curator import generate_imagen_image
    res = await generate_imagen_image(mock_client, "test prompt")
    assert res == b"LegacyImagenBytes"
    mock_client.aio.models.generate_images.assert_called_once()


@pytest.mark.asyncio
async def test_generate_imagen_multimodal_mode(monkeypatch):
    """Verify gemini-3.1-flash-image model uses generate_content API with image response modality."""
    monkeypatch.setattr("src.config.IMAGEN_MODEL", "gemini-3.1-flash-image")
    
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock(data=b"MultimodalImagenBytes")
    
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    from src.curator import generate_imagen_image
    res = await generate_imagen_image(mock_client, "test prompt")
    assert res == b"MultimodalImagenBytes"
    mock_client.aio.models.generate_content.assert_called_once()

