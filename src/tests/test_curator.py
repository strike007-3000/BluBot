import base64
import pytest
from datetime import datetime, timedelta, timezone
from src.curator import calculate_relevance_score, strip_markdown, fetch_news
from src.config import BASE_TIER_1, SIGNAL_BOOST, MOMENTUM_BOOST, SYNERGY_BONUS

def test_calculate_relevance_score_factors(monkeypatch):
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
    # Keep the scoring fixture independent of weekly product-list updates.
    monkeypatch.setattr("src.curator.MOMENTUM_PRODUCTS", ["gpt-5"])
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
    recent_dt = now_utc - timedelta(hours=5)
    mock_entry.updated_parsed = recent_dt.utctimetuple()

    mock_feed = mocker.MagicMock()
    mock_feed.entries = [mock_entry]
    mock_feed.feed = mocker.MagicMock(title="vLLM Releases")

    mocker.patch("feedparser.parse", return_value=mock_feed)

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"<atom feed>"
    mock_httpx_client.get = mocker.AsyncMock(return_value=mock_resp)

    url, items, is_healthy, err = await fetch_single_feed(mock_httpx_client, "https://github.com/vllm-project/vllm/releases.atom", now_utc - timedelta(days=2), now_utc, [], [])
    assert is_healthy is True
    assert err is None
    assert len(items) == 1
    assert items[0]["published"].startswith(recent_dt.strftime("%Y-%m-%d"))

@pytest.mark.asyncio
async def test_fetch_news_synergy_and_deduplication(mock_httpx_client, mocker):
    """Verify that cross-source duplicate stories get a synergy bonus and are ranked correctly."""
    # Mocking fetch_single_feed to return specific items with different publisher domains
    item_a = {"title": "Llama 4 Release Announced", "link": "https://site1.com/a", "summary": "...", "source": "Site 1", "source_id": "site1", "score": 10}
    item_b = {"title": "Llama 4 Release Details", "link": "https://site2.com/b", "summary": "...", "source": "Site 2", "source_id": "site2", "score": 10} # Corroborating domain
    item_c = {"title": "Story C Unrelated Release", "link": "https://site3.com/c", "summary": "...", "source": "Site 3", "source_id": "site3", "score": 15}

    mocker.patch("src.curator.fetch_single_feed", side_effect=[
        ("f1", [item_a], True, None),
        ("f2", [item_b], True, None),
        ("f3", [item_c], True, None)
    ])
    mocker.patch("src.curator.RSS_FEEDS", ["f1", "f2", "f3"])

    top_news, feed_outcomes = await fetch_news(mock_httpx_client)
    assert len(feed_outcomes) == 3
    assert all(healthy for _, healthy, _ in feed_outcomes)

    # Item A should be first because it gets SYNERGY_BONUS (10 + SYNERGY_BONUS = 25 > 15)
    assert len(top_news) == 2 # Clustered
    assert "Llama 4" in top_news[0]["title"]
    assert top_news[1]["title"] == "Story C Unrelated Release"
    assert top_news[0]["score"] == 10 + SYNERGY_BONUS
    assert top_news[0]["supporting_sources"] == ["Site 2"]

@pytest.mark.asyncio
async def test_fetch_news_refills_after_semantic_history_filter(mock_httpx_client, mocker, monkeypatch):
    """Historical duplicates are removed before lead policy and the final limit."""
    titles = [
        "Anthropic Releases Claude 3.7 Sonnet",
        "Critical Safety Incident Report",
        "Quantum Compiler Breakthrough",
        "Robotics Warehouse Deployment",
        "Chip Fabrication Advance",
        "Policy Copyright Decision",
        "Medical Imaging Benchmark",
        "Open Source Database Launch",
        "Satellite Foundation Model",
    ]
    items = [
        {
            "title": title,
            "link": f"https://example.com/{idx}",
            "summary": "Summary",
            "source": "Source",
            "source_id": "critical_feed" if idx == 1 else "standard_feed",
            "published": f"2026-10-05T00:00:0{idx}+00:00",
            "score": 100 - idx,
        }
        for idx, title in enumerate(titles)
    ]
    mocker.patch("src.curator.fetch_single_feed", return_value=("f1", items, True, None))

    from src.config import FEED_CATEGORY_MAP
    monkeypatch.setitem(FEED_CATEGORY_MAP, "critical_feed", "critical")
    monkeypatch.setitem(FEED_CATEGORY_MAP, "standard_feed", "research_lab")
    story_state = {
        "recent_stories": [{"title": "Anthropic Announces New Claude 3.7 Sonnet Model"}],
        "pending_stories": [],
    }

    articles, _ = await fetch_news(
        mock_httpx_client,
        feed_list=["f1"],
        limit=8,
        story_state=story_state,
    )

    assert len(articles) == 8
    assert titles[0] not in [article["title"] for article in articles]
    assert titles[-1] in [article["title"] for article in articles]
    assert articles[0]["source_id"] == "standard_feed"


@pytest.mark.asyncio
@pytest.mark.parametrize("match_decision,expected_count", [
    ("POSSIBLE_MATCH", 0),
    ("CONFIDENT_UPDATE", 1),
])
async def test_fetch_news_only_preserves_confirmed_updates(
    mock_httpx_client, mocker, match_decision, expected_count
):
    from src.settings import settings

    item = {
        "title": "OpenAI Releases GPT-5!",
        "link": "https://example.com/new-coverage",
        "summary": "Coverage of the same event.",
        "source": "Source",
        "source_id": "standard_feed",
        "published": "2026-10-18T00:00:00+00:00",
        "score": 100,
    }
    object.__setattr__(settings, "story_update_detection_enabled", True)
    mocker.patch("src.curator.fetch_single_feed", return_value=("f1", [item], True, None))
    mocker.patch("src.utils.is_story_semantic_duplicate", return_value=True)
    mocker.patch(
        "src.curator.match_story_continuity",
        return_value=(match_decision, {"title": "OpenAI Releases GPT-5"}, "test"),
    )

    articles, _ = await fetch_news(
        mock_httpx_client,
        feed_list=["f1"],
        story_state={"published_posts": [{"title": "OpenAI Releases GPT-5"}]},
    )

    assert len(articles) == expected_count

@pytest.mark.asyncio
async def test_fetch_news_deduplicates_canonical_urls(mock_httpx_client, mocker):
    items = [
        {"title": "First Headline", "link": "https://example.com/story?utm_source=rss", "summary": "...", "source": "One", "source_id": "one", "published": "2026-10-05T00:00:00+00:00", "score": 10},
        {"title": "Different Headline", "link": "HTTPS://EXAMPLE.COM/story#share", "summary": "...", "source": "Two", "source_id": "two", "published": "2026-10-05T00:00:01+00:00", "score": 20},
    ]
    mocker.patch("src.curator.fetch_single_feed", return_value=("f1", items, True, None))

    articles, _ = await fetch_news(mock_httpx_client, feed_list=["f1"])

    assert len(articles) == 1
    assert articles[0]["link"] == items[1]["link"]
    assert articles[0]["score"] == 20

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

    _, count_versions = normalize_headline("Service reaches 100 customers")
    assert count_versions == set()

    _, ios_18 = normalize_headline("Apple releases iOS 18 security update")
    _, ios_19 = normalize_headline("Apple releases iOS 19 security update")
    assert ios_18 == {"18"}
    assert ios_19 == {"19"}

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
    mock_save = mocker.patch("bot.save_seen_articles", side_effect=lambda data, **kw: (True, data))

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

    assert mock_save.call_count == 2
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
    m1.name = "models/gemini-3.5-flash-lite"
    m2 = MagicMock()
    m2.name = "models/gemini-2.5-flash-lite"
    mock_model_list = [m1, m2]
    mock_client.aio.models.list = AsyncMock(return_value=AsyncListMock(mock_model_list))

    await prune_gemini_model_priority_async(mock_client)

    assert "models/gemini-3.5-flash-lite" in GEMINI_MODEL_PRIORITY
    assert "models/gemini-2.5-flash-lite" in GEMINI_MODEL_PRIORITY
    assert "models/gemini-3.7-flash" not in GEMINI_MODEL_PRIORITY

    # Restore
    GEMINI_MODEL_PRIORITY.clear()
    GEMINI_MODEL_PRIORITY.extend(original_priority)

@pytest.mark.asyncio
async def test_async_model_pruning_does_not_match_preview_alias(monkeypatch):
    from src.settings import Settings
    monkeypatch.setattr("src.curator.settings", Settings(gemini_key="mock", is_dry_run=False))
    monkeypatch.setenv("CI", "false")
    original_priority = list(GEMINI_MODEL_PRIORITY)

    class AsyncListMock:
        def __aiter__(self):
            return self
        async def __anext__(self):
            if hasattr(self, "done"):
                raise StopAsyncIteration
            self.done = True
            model = MagicMock()
            model.name = "models/gemini-3.1-flash-lite-preview"
            return model

    mock_client = MagicMock()
    mock_client.aio.models.list = AsyncMock(return_value=AsyncListMock())
    await prune_gemini_model_priority_async(mock_client)

    # No exact approved model was returned, so the safety behavior keeps defaults.
    assert GEMINI_MODEL_PRIORITY == original_priority
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
        mock_settings.bluesky_limit = 300
        mock_settings.threads_limit = 500
        mock_settings.mastodon_limit = 500

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
        assert source.get("kind", "rss") in {"rss", "api"}

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
    generate_cloudflare_image,
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
async def test_generate_cloudflare_success(monkeypatch):
    from src.settings import Settings
    mock_settings = Settings(
        gemini_key="mock",
        cloudflare_account_id="account-id",
        cloudflare_api_token="cf-token",
        image_provider="cloudflare",
    )
    monkeypatch.setattr("src.curator.settings", mock_settings)

    valid_bytes = create_valid_test_image_bytes()
    encoded = base64.b64encode(valid_bytes).decode("ascii")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "result": {"image": encoded}}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    assert await generate_cloudflare_image("Test Prompt", mock_client) == valid_bytes
    args, kwargs = mock_client.post.call_args
    assert args[0].endswith("/ai/run/@cf/black-forest-labs/flux-1-schnell")
    assert kwargs["headers"]["Authorization"] == "Bearer cf-token"
    assert kwargs["json"] == {"prompt": "Test Prompt"}

@pytest.mark.asyncio
async def test_generate_cloudflare_caps_prompt(monkeypatch):
    from src.settings import Settings
    monkeypatch.setattr(
        "src.curator.settings",
        Settings(
            gemini_key="mock",
            cloudflare_account_id="account-id",
            cloudflare_api_token="cf-token",
        ),
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(
        200,
        request=httpx.Request("POST", "https://api.cloudflare.com/test"),
        json={"result": {"image": base64.b64encode(create_valid_test_image_bytes()).decode("ascii")}},
    )

    await generate_cloudflare_image("x" * 3000, mock_client)
    assert len(mock_client.post.call_args.kwargs["json"]["prompt"]) == 2048

@pytest.mark.asyncio
async def test_generate_cloudflare_skips_without_credentials(monkeypatch):
    from src.settings import Settings
    monkeypatch.setattr("src.curator.settings", Settings(gemini_key="mock"))
    mock_client = AsyncMock()

    assert await generate_cloudflare_image("Test Prompt", mock_client) is None
    mock_client.post.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 500])
async def test_generate_cloudflare_http_failures_return_none(monkeypatch, status_code):
    from src.settings import Settings
    monkeypatch.setattr(
        "src.curator.settings",
        Settings(
            gemini_key="mock",
            cloudflare_account_id="account-id",
            cloudflare_api_token="cf-token",
        ),
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/test")
    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(status_code, request=request)

    assert await generate_cloudflare_image("Test Prompt", mock_client) is None

@pytest.mark.asyncio
async def test_generate_cloudflare_timeout_returns_none(monkeypatch):
    from src.settings import Settings
    monkeypatch.setattr(
        "src.curator.settings",
        Settings(
            gemini_key="mock",
            cloudflare_account_id="account-id",
            cloudflare_api_token="cf-token",
        ),
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/test")
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("timed out", request=request)

    assert await generate_cloudflare_image("Test Prompt", mock_client) is None

@pytest.mark.asyncio
async def test_generate_cloudflare_invalid_image_returns_none(monkeypatch):
    from src.settings import Settings
    monkeypatch.setattr(
        "src.curator.settings",
        Settings(
            gemini_key="mock",
            cloudflare_account_id="account-id",
            cloudflare_api_token="cf-token",
        ),
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/test")
    response = httpx.Response(
        200,
        request=request,
        json={"result": {"image": base64.b64encode(b"not an image").decode("ascii")}},
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = response

    assert await generate_cloudflare_image("Test Prompt", mock_client) is None

@pytest.mark.asyncio
async def test_dispatcher_falls_back_after_real_cloudflare_quota_error(monkeypatch, mocker):
    from src.settings import Settings
    monkeypatch.setattr(
        "src.curator.settings",
        Settings(
            gemini_key="mock",
            image_provider="cloudflare",
            cloudflare_account_id="account-id",
            cloudflare_api_token="cf-token",
        ),
    )
    valid_bytes = create_valid_test_image_bytes()
    request = httpx.Request("POST", "https://api.cloudflare.com/test")
    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(429, request=request)
    pollinations = AsyncMock(return_value=valid_bytes)
    mocker.patch("src.curator.IMAGE_GENERATORS", {
        "cloudflare": generate_cloudflare_image,
        "pollinations": pollinations,
        "huggingface": AsyncMock(return_value=None),
    })

    assert await generate_ai_image(mock_client, None, "Test Prompt") == valid_bytes
    pollinations.assert_awaited_once_with("Test Prompt", mock_client)

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
async def test_generate_nvidia_404_immediate_fallback(monkeypatch):
    """Verify HTTP 404 from NVIDIA NIM returns None immediately without retrying."""
    import httpx
    from src.settings import Settings
    mock_settings = Settings(gemini_key="mock", nvidia_key="nv-token", image_provider="nvidia")
    monkeypatch.setattr("src.curator.settings", mock_settings)

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    res = await generate_nvidia_image("Test Prompt", mock_client)
    assert res is None
    # Verify post was called only once (no retries spent on 404!)
    assert mock_client.post.call_count == 1

@pytest.mark.asyncio
async def test_generate_nvidia_permanent_4xx_immediate_fallback(monkeypatch):
    """Permanent NVIDIA client errors must not spend the retry budget."""
    from src.settings import Settings
    mock_settings = Settings(gemini_key="mock", nvidia_key="nv-token", image_provider="nvidia")
    monkeypatch.setattr("src.curator.settings", mock_settings)

    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    assert await generate_nvidia_image("Test Prompt", mock_client) is None
    assert mock_client.post.call_count == 1

@pytest.mark.asyncio
async def test_generate_nvidia_429_retains_retries(monkeypatch):
    """Rate limits remain retryable after permanent 4xx errors are bypassed."""
    import httpx
    from src.settings import Settings
    mock_settings = Settings(gemini_key="mock", nvidia_key="nv-token", image_provider="nvidia")
    monkeypatch.setattr("src.curator.settings", mock_settings)
    monkeypatch.setattr("src.utils.asyncio.sleep", AsyncMock())

    request = httpx.Request("POST", "https://ai.api.nvidia.com/test")
    response = httpx.Response(429, request=request)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)

    with pytest.raises(httpx.HTTPStatusError):
        await generate_nvidia_image("Test Prompt", mock_client)
    assert mock_client.post.call_count == 3

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
async def test_dispatcher_cloudflare_falls_back_to_pollinations_then_huggingface(monkeypatch, mocker):
    from src.settings import Settings
    monkeypatch.setattr(
        "src.curator.settings",
        Settings(gemini_key="mock", image_provider="cloudflare"),
    )
    valid_bytes = create_valid_test_image_bytes()
    generators = mocker.patch("src.curator.IMAGE_GENERATORS", {
        "cloudflare": AsyncMock(return_value=None),
        "pollinations": AsyncMock(return_value=None),
        "huggingface": AsyncMock(return_value=valid_bytes),
    })

    assert await generate_ai_image(AsyncMock(), None, "Test Prompt") == valid_bytes
    assert generators["cloudflare"].await_count == 1
    assert generators["pollinations"].await_count == 1
    assert generators["huggingface"].await_count == 1

@pytest.mark.asyncio
async def test_dispatcher_does_not_fall_back_to_imagen(monkeypatch, mocker):
    from src.settings import Settings
    monkeypatch.setattr(
        "src.curator.settings",
        Settings(gemini_key="mock", image_provider="cloudflare"),
    )
    mocker.patch("src.curator.IMAGE_GENERATORS", {
        "cloudflare": AsyncMock(return_value=None),
        "pollinations": AsyncMock(return_value=None),
        "huggingface": AsyncMock(return_value=None),
    })
    imagen = mocker.patch("src.curator.generate_imagen_image", return_value=b"unexpected")

    assert await generate_ai_image(AsyncMock(), MagicMock(), "Test Prompt") is None
    imagen.assert_not_called()

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

@pytest.mark.asyncio
async def test_platform_drafts_parsing_and_fallback():
    from src.curator import parse_platform_drafts, validate_platform_drafts
    from src.models import PlatformDrafts

    # 1. Valid JSON with all 3 keys
    raw = '{"bluesky": "Bsky text", "threads": "Threads text", "mastodon": "Masto text"}'
    drafts = parse_platform_drafts(raw)
    assert drafts.bluesky == "Bsky text"
    assert drafts.threads == "Threads text"
    assert drafts.mastodon == "Masto text"

    # 2. Per-field fallback when 1 key is missing
    partial = '{"bluesky": "Bsky only", "threads": "Threads too"}'
    drafts_partial = parse_platform_drafts(partial)
    assert drafts_partial.bluesky == "Bsky only"
    assert drafts_partial.threads == "Threads too"
    assert drafts_partial.mastodon == "Bsky only"  # Inherits best valid candidate

    # 3. Complete JSON failure fallback
    malformed = 'This is plain text output from Gemini without JSON'
    drafts_fallback = parse_platform_drafts(malformed)
    assert drafts_fallback.bluesky == malformed
    assert drafts_fallback.threads == malformed

@pytest.mark.asyncio
async def test_deterministic_url_truncation_policy():
    from src.curator import repair_platform_drafts
    from src.models import PlatformDrafts

    long_url = "https://deepmind.google/discover/blog/introducing-gemini-3-8-frontier-capabilities"
    short_text = f"Frontier reasoning launch announced: {long_url}"
    drafts = PlatformDrafts.from_single(short_text)

    repaired = repair_platform_drafts(drafts)
    # Fits within all platform limits intact
    assert long_url in repaired.bluesky
    assert long_url in repaired.threads
    assert long_url in repaired.mastodon

    # Oversized text where URL + context cannot fit within 290 chars
    oversized_prefix = "A " * 200  # 400 chars
    oversized = f"{oversized_prefix}{long_url}"
    drafts_over = PlatformDrafts.from_single(oversized)

    repaired_over = repair_platform_drafts(drafts_over)
    assert len(repaired_over.bluesky) <= 290
    # URL was omitted without broken URL emitted
    assert not repaired_over.bluesky.endswith("https://deepmind.google/disc...")

@pytest.mark.asyncio
async def test_remix_platform_draft_api_failure_preserves_original():
    from src.curator import remix_platform_draft

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("Quota or network error"))

    orig = "Original robust draft text."
    success, result = await remix_platform_draft(mock_client, orig, "Make it punchier", "Bluesky")
    # Preserved original text on failure and reports success=False
    assert success is False
    assert result == orig

@pytest.mark.asyncio
async def test_remix_all_malformed_json_preserves_variants():
    """Verify malformed non-JSON Gemini output preserves all platform variants and reports success=False."""
    from src.curator import remix_all_drafts
    from src.models import PlatformDrafts

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is a malformed Gemini response without valid JSON braces."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    current = PlatformDrafts(
        bluesky="Original Bluesky post",
        threads="Original Threads narrative",
        mastodon="Original Mastodon technical note #AI"
    )

    success, result = await remix_all_drafts(mock_client, current, "Make all punchier")
    assert success is False
    assert result == current
    assert result.threads == "Original Threads narrative"
    assert result.mastodon == "Original Mastodon technical note #AI"

@pytest.mark.asyncio
async def test_summarize_news_empty_input_arity():
    """Verify summarize_news on empty news_items returns 6 items with PlatformDrafts."""
    from src.curator import summarize_news
    from src.models import PlatformDrafts

    result = await summarize_news([], "Some context")
    assert len(result) == 6
    summary, lead_link, topic, is_failover, dialect, drafts = result
    assert summary is None
    assert lead_link is None
    assert topic == "General"
    assert is_failover is False
    assert dialect is None
    assert isinstance(drafts, PlatformDrafts)
    assert drafts.bluesky == ""

def test_parse_platform_drafts_rejects_metadata_only_json():
    """Verify JSON with only metadata and no platform keys does not become post content."""
    from src.curator import parse_platform_drafts
    metadata_json = '{"topic": "Artificial Intelligence", "category": "tech"}'
    drafts = parse_platform_drafts(metadata_json, fallback_text="Fallback content")
    # Must not contain the serialized json string
    assert "topic" not in drafts.bluesky
    assert drafts.bluesky == "Fallback content"
    assert drafts.threads == "Fallback content"
    assert drafts.mastodon == "Fallback content"

    # Also test with no fallback_text
    drafts_empty = parse_platform_drafts(metadata_json)
    assert drafts_empty.bluesky == ""
    assert drafts_empty.threads == ""
    assert drafts_empty.mastodon == ""

@pytest.mark.asyncio
async def test_remix_omits_temperature_for_flash_models(monkeypatch):
    """Verify remix calls omit temperature when model is gemini-3.7-flash or gemini-3.6-flash."""
    from src.curator import remix_platform_draft, remix_all_drafts
    from src.models import PlatformDrafts

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()

    captured_configs = []
    async def mock_generate_content(*args, **kwargs):
        captured_configs.append(kwargs.get("config"))
        resp = MagicMock()
        resp.text = '{"bluesky": "Remixed B", "threads": "Remixed T", "mastodon": "Remixed M"}'
        return resp

    mock_client.aio.models.generate_content = AsyncMock(side_effect=mock_generate_content)

    monkeypatch.setattr("src.curator.GEMINI_MODEL_PRIORITY", ["models/gemini-3.7-flash"])

    # Test single platform remix
    await remix_platform_draft(mock_client, "Current text", "make punchy", "Bluesky")
    assert len(captured_configs) >= 1
    assert captured_configs[0].temperature is None

    # Test all platforms remix
    captured_configs.clear()
    await remix_all_drafts(mock_client, PlatformDrafts.from_single("Base"), "make punchy")
    assert len(captured_configs) >= 1
    assert captured_configs[0].temperature is None

def test_url_safe_truncation_retains_post_url_prose():
    """Verify that when a URL is embedded mid-sentence, prose following the URL is preserved if budget allows."""
    from src.curator import _repair_text_url_safe
    text = "Intro words https://example.com/link trailing details and conclusion"
    # Limit generous enough to keep intro, url, and trailing details
    limit = 65
    repaired = _repair_text_url_safe(text, limit, "Bluesky")
    assert "https://example.com/link" in repaired
    assert repaired.startswith("Intro words")
    # Verify post-URL text was not needlessly dropped
    assert "trailing" in repaired
    assert len(repaired) <= limit


def test_continuity_matcher_72h_window_and_duplicate_url():
    """Phase 11 Curator tests: match within 72h, reject outside 72h, reject duplicate URLs."""
    from src.curator import match_story_continuity
    from src.models import MatchDecision
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    parent_recent = {
        "url": "https://techcrunch.com/2026/10/17/openai-releases-gpt5",
        "title": "OpenAI Releases GPT-5 to Early Testers",
        "published_at": "2026-10-17T12:00:00Z",
        "source": "TechCrunch",
        "entry_kind": "original",
        "story_fingerprint": "gpt-5 openai releases testers",
        "thread_roots": {"bluesky": {"uri": "at://orig", "cid": "c0"}}
    }
    parent_old = {
        "url": "https://techcrunch.com/2026/10/10/anthropic-announces-claude4",
        "title": "Anthropic Announces Claude 4",
        "published_at": "2026-10-10T12:00:00Z",
        "source": "TechCrunch",
        "entry_kind": "original",
        "story_fingerprint": "announces anthropic claude-4",
        "thread_roots": {"bluesky": {"uri": "at://old", "cid": "c0"}}
    }
    published = [parent_recent, parent_old]

    # 1. Match within 72h with new source/action
    cand_update = {
        "title": "OpenAI Launches GPT-5 to All Developers Today",
        "link": "https://theverge.com/2026/10/18/openai-gpt5-launch",
        "source": "The Verge",
        "summary": "Full public rollout of GPT-5 is now live for all developers with API access.",
    }
    decision, matched, exp = match_story_continuity(cand_update, published, now_utc=now)
    assert decision == MatchDecision.CONFIDENT_UPDATE.value
    assert matched["title"] == parent_recent["title"]
    assert "new source/domain" in exp or "new event action" in exp

    # 2. Reject entries outside 72 hours
    cand_old_target = {
        "title": "Anthropic Claude 4 Model Launches Today",
        "link": "https://theverge.com/2026/10/18/anthropic-claude4-launch",
        "source": "The Verge",
        "summary": "General release of Claude 4 begins today across all regions.",
    }
    decision, matched, exp = match_story_continuity(cand_old_target, published, now_utc=now)
    assert decision == MatchDecision.NO_MATCH.value

    # 3. Reject duplicate canonical URL
    cand_dup_url = {
        "title": "OpenAI Releases GPT-5 to Early Testers (Updated)",
        "link": "https://techcrunch.com/2026/10/17/openai-releases-gpt5",
        "source": "TechCrunch",
        "summary": "Minor edits in TechCrunch article.",
    }
    decision, matched, exp = match_story_continuity(cand_dup_url, published, now_utc=now)
    assert decision != MatchDecision.CONFIDENT_UPDATE.value


def test_continuity_matcher_version_conflict_and_change_detection():
    """Phase 11 Curator tests: reject version conflicts, reject syndicated copies, ignore update entries as parents."""
    from src.curator import match_story_continuity, detect_meaningful_change
    from src.models import MatchDecision
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    orig_entry = {
        "url": "https://techcrunch.com/2026/10/18/mistral-large-2",
        "title": "Mistral Releases Large 2 Model",
        "published_at": "2026-10-18T06:00:00Z",
        "source": "TechCrunch",
        "entry_kind": "original",
        "story_fingerprint": "large-2 mistral model releases",
        "thread_roots": {"bluesky": {"uri": "at://root-mistral", "cid": "c0"}}
    }
    prior_update = {
        "url": "https://venturebeat.com/2026/10/18/mistral-large-2-benchmark",
        "title": "Mistral Large 2 Benchmarks Beat Competitors",
        "published_at": "2026-10-18T08:00:00Z",
        "source": "VentureBeat",
        "entry_kind": "update",
        "parent_story_fingerprint": orig_entry["story_fingerprint"],
        "story_fingerprint": "benchmarks large-2 mistral",
    }
    published = [orig_entry, prior_update]

    # Version conflict (e.g. Large 2 vs Large 3) rejects
    cand_version_conflict = {
        "title": "Mistral Releases Large 3 Model",
        "link": "https://wired.com/2026/10/18/mistral-large-3",
        "source": "Wired",
        "summary": "Mistral has introduced Large 3 today.",
    }
    decision, matched, exp = match_story_continuity(cand_version_conflict, published, now_utc=now)
    assert decision == MatchDecision.NO_MATCH.value

    # Reject syndicated copy: same publisher, identical title without new facts
    cand_syndicated = {
        "title": "Mistral Releases Large 2 Model",
        "link": "https://techcrunch.com/2026/10/18/mistral-large-2-mirror",
        "source": "TechCrunch",
        "summary": "Mistral Releases Large 2 Model for enterprise developers.",
    }
    has_change, chg_exp = detect_meaningful_change(
        candidate_title=cand_syndicated["title"],
        candidate_summary=cand_syndicated["summary"],
        candidate_url=cand_syndicated["link"],
        candidate_source=cand_syndicated["source"],
        parent_entry=orig_entry
    )
    assert has_change is False
    assert "syndicated" in chg_exp or "rejected" in chg_exp

    # Candidate matches original root, ignoring prior_update as parent
    cand_valid_update = {
        "title": "Mistral Large 2 Open-Sources Weights and Launches Weights on Hugging Face",
        "link": "https://huggingface.co/blog/mistral-large-2",
        "source": "Hugging Face",
        "summary": "Official open-weights release of Mistral Large 2 is now available.",
    }
    decision, matched, exp = match_story_continuity(cand_valid_update, published, now_utc=now)
    assert decision == MatchDecision.CONFIDENT_UPDATE.value
    # Crucial: Parent must be the original story, not prior_update
    assert matched["entry_kind"] == "original"
    assert matched["url"] == orig_entry["url"]

def test_meaningful_change_requires_factual_development():
    from src.curator import detect_meaningful_change
    orig_entry = {
        "title": "Anthropic Announces Claude 3.5 Sonnet",
        "url": "https://anthropic.com/news/claude-3-5-sonnet",
        "summary": "Anthropic introduces Claude 3.5 Sonnet with enhanced vision and reasoning benchmarks.",
        "source": "Anthropic",
    }

    # Different source and modified phrasing alone without new verbs/evidence/version/summary-diff is rejected
    has_change, exp = detect_meaningful_change(
        candidate_title="Anthropic Announces Claude 3.5 Sonnet Model Details",
        candidate_summary="Anthropic introduces Claude 3.5 Sonnet with enhanced vision and reasoning benchmarks.",
        candidate_url="https://theverge.com/news/claude-3-5",
        candidate_source="The Verge",
        parent_entry=orig_entry
    )
    assert has_change is False
    assert "syndicated copy" in exp or "no identifiable new fact" in exp

    # Factual development (e.g. new action verb / release) is accepted
    has_change_fact, exp_fact = detect_meaningful_change(
        candidate_title="Anthropic Deploys Claude 3.5 Sonnet to Enterprise Workspaces with Pricing",
        candidate_summary="Anthropic deploys Claude 3.5 Sonnet with new API availability and benchmark results.",
        candidate_url="https://theverge.com/news/claude-3-5-pricing",
        candidate_source="The Verge",
        parent_entry=orig_entry
    )
    assert has_change_fact is True
    assert "new event action" in exp_fact

def test_truncate_with_preserved_link():
    from src.curator import _truncate_with_preserved_link
    url = "https://example.com/very/long/path/to/story"
    text = "This is a detailed lead sentence explaining something important. " * 5
    result = _truncate_with_preserved_link(text, url, limit=100)
    assert url in result
    assert len(result) <= 100
    assert result.endswith(url)

    unfit_url = "https://example.com/" + ("x" * 100)
    unfit_result = _truncate_with_preserved_link("Update details", unfit_url, limit=50)
    assert unfit_url not in unfit_result
    assert not unfit_result.endswith(unfit_url[:50])
    assert len(unfit_result) <= 50


def test_event_verb_inflections_are_not_meaningful_changes():
    from src.curator import detect_meaningful_change

    changed, explanation = detect_meaningful_change(
        candidate_title="OpenAI Announced GPT-5",
        candidate_summary="OpenAI introduced GPT-5 to developers today.",
        candidate_url="https://example.net/gpt-5",
        candidate_source="Example",
        parent_entry={
            "title": "OpenAI Announces GPT-5",
            "summary": "OpenAI introduced GPT-5 to developers today.",
            "url": "https://example.com/gpt-5",
            "source": "Example",
        },
    )

    assert changed is False
    assert "no identifiable new fact" in explanation


def test_rollout_is_a_meaningful_event_but_new_publishers_are_not():
    from src.curator import detect_meaningful_change

    parent = {
        "title": "OpenAI Announces GPT-5 API",
        "url": "https://example.com/announcement",
        "source": "Example",
    }
    rollout, explanation = detect_meaningful_change(
        candidate_title="OpenAI Rolls Out GPT-5 API Worldwide",
        candidate_summary="",
        candidate_url="https://example.net/rollout",
        candidate_source="Other",
        parent_entry=parent,
    )
    assert rollout is True
    assert "rollout" in explanation

    syndicated, explanation = detect_meaningful_change(
        candidate_title="OpenAI Announced GPT-5 API",
        candidate_summary="Same report without a new fact.",
        candidate_url="https://example.net/copy",
        candidate_source="Other",
        parent_entry={**parent, "summary": "Same report without a new fact."},
    )
    assert syndicated is False
    assert "no identifiable new fact" in explanation


def test_base_event_verbs_and_changed_numeric_facts_are_meaningful():
    from src.curator import detect_meaningful_change

    released, explanation = detect_meaningful_change(
        candidate_title="Developers Release Acme Model Publicly",
        candidate_summary="",
        candidate_url="https://example.net/release",
        candidate_source="Other",
        parent_entry={
            "title": "Developers Announce Acme Model Preview",
            "url": "https://example.com/preview",
            "source": "Example",
        },
    )
    assert released is True
    assert "release" in explanation

    grew, explanation = detect_meaningful_change(
        candidate_title="Service Reaches 200 Customers",
        candidate_summary="",
        candidate_url="https://example.net/200",
        candidate_source="Other",
        parent_entry={
            "title": "Service Reaches 100 Customers",
            "url": "https://example.com/100",
            "source": "Example",
        },
    )
    assert grew is True
    assert "changed numeric fact" in explanation

    equivalent, explanation = detect_meaningful_change(
        candidate_title="Acme Revenue Grows 50% This Quarter",
        candidate_summary="",
        candidate_url="https://example.net/revenue",
        candidate_source="Other",
        parent_entry={
            "title": "Acme Revenue Grows 50 Percent",
            "url": "https://example.com/revenue",
            "source": "Example",
        },
    )
    assert equivalent is False
    assert "no identifiable new fact" in explanation


def test_generic_model_versions_remain_separate_stories():
    from src.curator import detect_meaningful_change

    changed, explanation = detect_meaningful_change(
        candidate_title="xAI Releases Grok 4 Model",
        candidate_summary="",
        candidate_url="https://example.net/grok-4",
        candidate_source="Other",
        parent_entry={
            "title": "xAI Releases Grok 3 Model",
            "url": "https://example.com/grok-3",
            "source": "Example",
        },
    )
    assert changed is False
    assert "conflicting version numbers" in explanation
