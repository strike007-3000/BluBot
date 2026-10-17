"""Tests for the Hugging Face Trending curation source."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import FEED_CATEGORY_MAP, FEED_SCORE_MAP, HF_MODELS_API_URL, RSS_FEEDS
from src.curator import cluster_articles, fetch_hf_trending, fetch_news
from src.settings import settings


@pytest.fixture(autouse=True)
def restore_huggingface_key():
    original = settings.huggingface_api_key
    yield
    object.__setattr__(settings, "huggingface_api_key", original)


def _response(payload, status=200):
    response = MagicMock(status_code=status)
    response.json.return_value = payload
    return response


def test_hf_api_source_is_scored_but_not_an_rss_feed():
    assert HF_MODELS_API_URL not in RSS_FEEDS
    assert FEED_SCORE_MAP["hf_trending"] == 18
    assert FEED_CATEGORY_MAP["hf_trending"] == "open_source"


@pytest.mark.asyncio
async def test_hf_trending_shape_lookback_seen_filter_and_score():
    now = datetime.now(timezone.utc)
    payload = [
        {"id": "org/fresh", "pipeline_tag": "text-generation", "createdAt": (now - timedelta(days=5)).isoformat(), "lastModified": (now - timedelta(hours=1)).isoformat()},
        {"id": "org/old", "pipeline_tag": "text-generation", "createdAt": (now - timedelta(days=10)).isoformat(), "lastModified": (now - timedelta(days=9)).isoformat()},
        {"id": "org/seen", "pipeline_tag": "feature-extraction", "createdAt": (now - timedelta(hours=2)).isoformat(), "lastModified": (now - timedelta(hours=1)).isoformat()},
    ]
    client = MagicMock(get=AsyncMock(return_value=_response(payload)))

    items = await fetch_hf_trending(
        client, seen_links=["https://huggingface.co/org/seen"], days_lookback=2
    )

    assert len(items) == 1
    item = items[0]
    assert item["title"] == "org/fresh (text generation)"
    assert item["link"] == "https://huggingface.co/org/fresh"
    assert item["source"] == "Hugging Face Trending"
    assert item["source_id"] == "hf_trending"
    assert item["score"] > 0
    assert item["_score_debug"]["source"] == 18
    params = client.get.await_args.kwargs["params"]
    assert ("sort", "trendingScore") in params
    assert ("direction", "-1") in params


@pytest.mark.asyncio
@pytest.mark.parametrize("token, expected", [(None, {}), ("hf_token", {"Authorization": "Bearer hf_token"})])
async def test_hf_trending_auth_header_is_optional(token, expected):
    object.__setattr__(settings, "huggingface_api_key", token)
    client = MagicMock(get=AsyncMock(return_value=_response([])))
    await fetch_hf_trending(client)
    assert client.get.await_args.kwargs["headers"] == expected


@pytest.mark.asyncio
async def test_hf_trending_http_and_json_errors_return_empty():
    http_client = MagicMock(get=AsyncMock(return_value=_response([], status=503)))
    assert await fetch_hf_trending(http_client) == []

    bad_response = _response([])
    bad_response.json.side_effect = ValueError("bad json")
    json_client = MagicMock(get=AsyncMock(return_value=bad_response))
    assert await fetch_hf_trending(json_client) == []


@pytest.mark.asyncio
async def test_fetch_news_keeps_rss_results_when_hf_fails(mocker):
    rss_item = {
        "title": "RSS release", "summary": "release", "link": "https://rss.example/item",
        "source": "RSS", "source_id": "openai_news", "published": "2026-10-17T00:00:00Z", "score": 30,
    }
    mocker.patch("src.curator.RSS_FEEDS", ["https://rss.example/feed"])
    mocker.patch("src.curator.fetch_single_feed", new_callable=AsyncMock, return_value=("https://rss.example/feed", [rss_item], True, None))
    mocker.patch("src.curator.fetch_hf_trending", new_callable=AsyncMock, return_value=[])

    articles, outcomes = await fetch_news(MagicMock())

    assert [article["link"] for article in articles] == ["https://rss.example/item"]
    assert outcomes == [("https://rss.example/feed", True, None)]


@pytest.mark.asyncio
async def test_fetch_news_includes_hf_with_explicit_vanguard_feed_list(mocker):
    rss_item = {
        "title": "RSS release", "summary": "release", "link": "https://rss.example/item",
        "source": "RSS", "source_id": "openai_news", "published": "2026-10-17T00:00:00Z", "score": 30,
    }
    hf_item = {
        "title": "org/model", "summary": "model", "link": "https://huggingface.co/org/model",
        "source": "Hugging Face Trending", "source_id": "hf_trending", "published": "2026-10-17T00:00:00Z", "score": 18,
    }
    mocker.patch("src.curator.fetch_single_feed", new_callable=AsyncMock, return_value=("https://rss.example/feed", [rss_item], True, None))
    fetch_hf = mocker.patch("src.curator.fetch_hf_trending", new_callable=AsyncMock, return_value=[hf_item])

    articles, _ = await fetch_news(MagicMock(), feed_list=["https://rss.example/feed"])

    fetch_hf.assert_awaited_once()
    assert {article["link"] for article in articles} == {
        "https://rss.example/item", "https://huggingface.co/org/model"
    }


@pytest.mark.asyncio
async def test_fetch_news_can_exclude_api_sources_for_rss_audit(mocker):
    mocker.patch("src.curator.fetch_single_feed", new_callable=AsyncMock, return_value=("https://rss.example/feed", [], True, None))
    fetch_hf = mocker.patch("src.curator.fetch_hf_trending", new_callable=AsyncMock)

    await fetch_news(
        MagicMock(), feed_list=["https://rss.example/feed"], include_api_sources=False
    )

    fetch_hf.assert_not_awaited()


def test_hf_entry_clusters_with_rss_story_about_same_model():
    entries = [
        {"title": "org/model-x (text generation)", "summary": "Trending model", "link": "https://huggingface.co/org/model-x", "source": "Hugging Face Trending", "source_id": "hf_trending", "published": "2026-10-17T00:00:00Z", "score": 18},
        {"title": "Org releases Model-X text generation weights", "summary": "Release", "link": "https://news.example/model-x", "source": "News", "source_id": "techcrunch_ai", "published": "2026-10-17T01:00:00Z", "score": 12},
    ]

    clusters = cluster_articles(entries)

    assert len(clusters) == 1
    assert clusters[0]["consensus_synergy"] is True
    assert clusters[0]["supporting_links"] == ["https://news.example/model-x"]
