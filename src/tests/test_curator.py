import pytest
from datetime import datetime, timedelta, timezone
from src.curator import calculate_relevance_score, strip_markdown, fetch_news
from src.config import BASE_TIER_1, SIGNAL_BOOST, MOMENTUM_BOOST, SYNERGY_BONUS

def test_calculate_relevance_score_factors():
    """Verify that different scoring factors are correctly applied."""
    now_utc = datetime.now(timezone.utc)
    
    # 1. Tier 1 Source
    item_tier1 = {
        "title": "New Model Release",
        "summary": "This is a summary",
        "link": "https://openai.com/news/1"
    }
    score_tier1 = calculate_relevance_score(item_tier1, now_utc, now_utc)
    assert score_tier1 >= BASE_TIER_1
    
    # 2. Keyword Boost
    item_signal = {
        "title": "Autonomous Agent SOTA",
        "summary": "New breakthrough in agentic reasoning",
        "link": "https://example.com/1"
    }
    score_signal = calculate_relevance_score(item_signal, now_utc, now_utc)
    assert score_signal >= SIGNAL_BOOST
    
    # 3. Momentum Product
    item_momentum = {
        "title": "GPT-5 First Look",
        "summary": "Testing the new model",
        "link": "https://example.com/2"
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
