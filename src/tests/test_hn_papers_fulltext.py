"""Tests for Hacker News, HF Daily Papers, and full-article grounding."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import FEED_SCORE_MAP, HF_DAILY_PAPERS_URL, HN_SEARCH_URL, RSS_FEEDS
from src.settings import Settings
from src.curator import fetch_hacker_news, fetch_hf_daily_papers, summarize_news


def _resp(payload, status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = payload
    return r


def test_new_api_sources_registered_and_not_rss():
    assert HN_SEARCH_URL not in RSS_FEEDS and HF_DAILY_PAPERS_URL not in RSS_FEEDS
    assert FEED_SCORE_MAP["hn_ai"] == 15 and FEED_SCORE_MAP["hf_daily_papers"] == 18


@pytest.mark.asyncio
async def test_hf_daily_papers_filters_and_shapes():
    now = datetime.now(timezone.utc)
    ok = {"paper": {"id": "2611.1", "upvotes": 12}, "title": "Good Paper", "summary": "Does X.",
          "publishedAt": (now - timedelta(hours=5)).isoformat()}
    low = {"paper": {"id": "2611.2", "upvotes": 1}, "title": "Low", "summary": "s", "publishedAt": now.isoformat()}
    old = {"paper": {"id": "2611.3", "upvotes": 50}, "title": "Old", "summary": "s",
           "publishedAt": (now - timedelta(days=9)).isoformat()}
    client = MagicMock(get=AsyncMock(return_value=_resp([ok, low, old, {"bad": 1}])))

    items = await fetch_hf_daily_papers(client)

    assert [i["title"] for i in items] == ["Good Paper"]
    assert items[0]["source_id"] == "hf_daily_papers"
    assert items[0]["link"].endswith("/papers/2611.1") and "score" in items[0]


@pytest.mark.asyncio
async def test_hf_daily_papers_http_error_returns_empty():
    client = MagicMock(get=AsyncMock(return_value=_resp(None, status=503)))
    assert await fetch_hf_daily_papers(client) == []


@pytest.mark.asyncio
async def test_hacker_news_dedupes_across_queries_and_skips_urlless():
    ts = int(datetime.now(timezone.utc).timestamp()) - 3600
    hits = [
        {"title": "New LLM", "url": "https://example.com/a", "points": 150, "num_comments": 9, "created_at_i": ts},
        {"title": "Ask HN: LLMs?", "url": None, "points": 300, "num_comments": 5, "created_at_i": ts},
    ]
    client = MagicMock(get=AsyncMock(return_value=_resp({"hits": hits})))

    items = await fetch_hacker_news(client)  # two queries return the same hit

    assert len(items) == 1 and items[0]["source_id"] == "hn_ai"
    assert "150 points" in items[0]["summary"]


@pytest.mark.asyncio
async def test_hacker_news_survives_network_errors():
    client = MagicMock(get=AsyncMock(side_effect=RuntimeError("boom")))
    assert await fetch_hacker_news(client) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fetched,expect_field", [("Full body text.", True), (None, False)])
async def test_summarize_news_adds_article_text_only_when_fetched(monkeypatch, fetched, expect_field):
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=MagicMock(text=(
        '{"topic":"AI","bluesky":"A specific observation about the story.","threads":"A conversational take on the story.","mastodon":"A technical overview. #AI"}'
    )))
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)
    monkeypatch.setattr("src.curator.GEMINI_MODEL_PRIORITY", ["models/gemini-3.5-flash-lite"])
    monkeypatch.setattr("src.curator.settings", Settings(gemini_key="test", is_dry_run=False))
    monkeypatch.setattr("src.linkedin_draft.fetch_source_text", AsyncMock(return_value=fetched))

    await summarize_news(
        [{"title": "T", "source": "S", "summary": "blurb", "link": "https://example.com/x"}],
        {"day": "Monday", "session": "Morning Intelligence"},
    )

    contents = mock_client.aio.models.generate_content.await_args.kwargs["contents"]
    assert ("Full body text." in contents) is expect_field
    assert "blurb" in contents


@pytest.mark.asyncio
async def test_safe_fetch_stops_at_max_bytes(monkeypatch):
    import httpx
    from src.utils import get_with_safe_redirects

    monkeypatch.setattr("src.utils._resolve_public_ip_candidates", lambda host: ["93.184.216.34"])
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * 50_000))
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await get_with_safe_redirects(client, "https://example.com/big", max_bytes=1_000)

    assert resp.status_code == 200 and len(resp.content) == 1_000


@pytest.mark.asyncio
async def test_non_lead_stories_get_shorter_article_excerpt(monkeypatch):
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=MagicMock(text=(
        '{"topic":"AI","bluesky":"A specific observation about the story.","threads":"A conversational take.","mastodon":"A technical overview. #AI"}'
    )))
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)
    monkeypatch.setattr("src.curator.GEMINI_MODEL_PRIORITY", ["models/gemini-3.5-flash-lite"])
    monkeypatch.setattr("src.curator.settings", Settings(gemini_key="test", is_dry_run=False))
    monkeypatch.setattr("src.linkedin_draft.fetch_source_text", AsyncMock(return_value="y" * 6000))

    items = [{"title": f"T{i}", "source": "S", "summary": "b", "link": f"https://example.com/{i}"} for i in range(2)]
    await summarize_news(items, {"day": "Monday", "session": "Morning Intelligence"})

    contents = mock_client.aio.models.generate_content.await_args.kwargs["contents"]
    assert "y" * 6000 in contents and "y" * 6001 not in contents
    assert contents.count("y" * 2000) == 4  # lead (6000) holds three 2000-runs; the other story holds one
