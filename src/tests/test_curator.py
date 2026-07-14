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
async def test_fetch_news_synergy_and_deduplication(mock_httpx_client, mocker):
    """Verify that duplicate stories get a synergy bonus and are ranked correctly."""
    # Mocking fetch_single_feed to return specific items
    item_a = {"title": "Story A", "link": "https://site1.com/a", "summary": "...", "source": "Site 1", "score": 10}
    item_b = {"title": "Story A", "link": "https://site1.com/a", "summary": "...", "source": "Site 2", "score": 10} # Duplicate link
    item_c = {"title": "Story C", "link": "https://site2.com/c", "summary": "...", "source": "Site 2", "score": 15}
    
    # Patching fetch_single_feed instead of full fetch_news to avoid network
    mocker.patch("src.curator.fetch_single_feed", side_effect=[[item_a], [item_b], [item_c]])
    
    # We need to mock RSS_FEEDS to have 3 entries for our side_effect
    mocker.patch("src.curator.RSS_FEEDS", ["f1", "f2", "f3"])
    
    top_news = await fetch_news(mock_httpx_client)
    
    # Item A should be first because it gets SYNERGY_BONUS (10 + SYNERGY_BONUS = 25 > 15)
    assert len(top_news) == 2 # Deduplicated
    assert top_news[0]["title"] == "Story A"
    assert top_news[1]["title"] == "Story C"
    assert top_news[0]["score"] == 10 + SYNERGY_BONUS

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

