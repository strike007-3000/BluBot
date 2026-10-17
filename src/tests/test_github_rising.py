"""Tests for the GitHub Fast-Rising AI Repositories curation source."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import FEED_CATEGORY_MAP, FEED_SCORE_MAP, GITHUB_SEARCH_REPOS_URL, RSS_FEEDS
from src.curator import (
    _fetch_github_readme_excerpt,
    _is_valid_github_repo_url,
    fetch_github_rising,
    fetch_news,
)
from src.settings import settings


@pytest.fixture(autouse=True)
def restore_github_token():
    original = settings.github_token
    yield
    object.__setattr__(settings, "github_token", original)


def _response(payload=None, status=200, text="", headers=None, content=None):
    resp = MagicMock(status_code=status)
    resp.json.return_value = payload if payload is not None else {}
    resp.text = text
    resp.content = content if content is not None else (text.encode("utf-8") if text else b"")
    resp.headers = headers or {}
    return resp


def test_github_rising_registered_correctly():
    assert GITHUB_SEARCH_REPOS_URL not in RSS_FEEDS
    assert FEED_SCORE_MAP["github_rising"] == 16
    assert FEED_CATEGORY_MAP["github_rising"] == "open_source"


def test_url_validation_accepts_only_https_github_com():
    assert _is_valid_github_repo_url("https://github.com/org/repo") is True
    assert _is_valid_github_repo_url("http://github.com/org/repo") is False
    assert _is_valid_github_repo_url("https://evil.com/org/repo") is False
    assert _is_valid_github_repo_url("https://notgithub.com") is False
    assert _is_valid_github_repo_url("javascript:alert(1)") is False
    assert _is_valid_github_repo_url("") is False


@pytest.mark.asyncio
async def test_candidate_limiting_before_readme_fetch():
    now = datetime.now(timezone.utc)
    repos = []
    for i in range(10):
        repos.append({
            "full_name": f"org/repo-{i}",
            "html_url": f"https://github.com/org/repo-{i}",
            "created_at": (now - timedelta(days=2)).isoformat(),
            "stargazers_count": 100 * (i + 1),
            "description": f"AI model runner {i}",
        })
    search_payload = {"items": repos}

    client = MagicMock()
    # First call is Search API, subsequent calls are for README
    readme_resp = _response(status=200, text="Clean README text")
    client.get = AsyncMock(side_effect=[_response(search_payload, status=200)] + [readme_resp] * 10)

    items = await fetch_github_rising(client, limit=3)

    assert len(items) == 3
    # Exactly 1 search call + 3 README calls = 4 total GET calls
    assert client.get.await_count == 4
    # Verify bounded byte range header was sent
    assert client.get.await_args_list[1].kwargs["headers"]["Range"] == "bytes=0-8191"
    assert items[0]["title"] == "org/repo-9"
    assert "Clean README text" in items[0]["summary"]
    assert "AI model runner 9" in items[0]["summary"]
    assert items[1]["title"] == "org/repo-8"
    assert "Clean README text" in items[1]["summary"]
    assert items[2]["title"] == "org/repo-7"
    assert "Clean README text" in items[2]["summary"]


@pytest.mark.asyncio
async def test_skips_repository_without_description_or_readme():
    now = datetime.now(timezone.utc)
    search_payload = {
        "items": [
            {
                "full_name": "org/empty-repo",
                "html_url": "https://github.com/org/empty-repo",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "stargazers_count": 200,
                "description": "",
            }
        ]
    }
    client = MagicMock()
    # README returns 404
    client.get = AsyncMock(side_effect=[
        _response(search_payload, status=200),
        _response(status=404, text="")
    ])

    items = await fetch_github_rising(client)
    assert items == []


@pytest.mark.asyncio
async def test_velocity_bonus_capped_and_recorded_in_score_debug():
    now = datetime.now(timezone.utc)
    search_payload = {
        "items": [
            {
                "full_name": "org/mega-viral",
                "html_url": "https://github.com/org/mega-viral",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "stargazers_count": 5000,  # Velocity = 5000 / 1 = 5000 > 10.0
                "description": "Groundbreaking LLM framework",
            }
        ]
    }
    client = MagicMock()
    client.get = AsyncMock(side_effect=[
        _response(search_payload, status=200),
        _response(status=200, text="Detailed documentation")
    ])

    items = await fetch_github_rising(client)
    assert len(items) == 1
    item = items[0]
    assert "Detailed documentation" in item["summary"]
    assert "Groundbreaking LLM framework" in item["summary"]
    assert item["_score_debug"]["source"] == 16
    assert item["_score_debug"]["github_velocity"] == 10.0
    # base_score(16) - decay(24h * 0.5 = 12) + velocity_bonus(10) = 14
    assert 13.9 <= item["score"] <= 14.1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [403, 429])
async def test_rate_limits_handle_retry_after_and_return_empty(status_code):
    client = MagicMock()
    client.get = AsyncMock(return_value=_response(
        status=status_code,
        headers={"Retry-After": "60", "x-ratelimit-reset": "1776450000"}
    ))

    items = await fetch_github_rising(client)
    assert items == []


@pytest.mark.asyncio
async def test_github_token_header_included_when_configured():
    object.__setattr__(settings, "github_token", "ghp_secret_test_token")
    client = MagicMock()
    client.get = AsyncMock(return_value=_response({"items": []}, status=200))

    await fetch_github_rising(client)
    assert client.get.await_count == 1
    headers = client.get.await_args_list[0].kwargs["headers"]
    assert headers.get("Authorization") == "Bearer ghp_secret_test_token"
    assert headers.get("Accept") == "application/vnd.github+json"


@pytest.mark.asyncio
async def test_fetch_news_integrates_github_rising_parallel():
    sample_gh_item = {
        "title": "org/gh-rising",
        "summary": "AI agents library",
        "link": "https://github.com/org/gh-rising",
        "source": "GitHub Fast-Rising Repositories",
        "source_id": "github_rising",
        "published": "2026-10-17T00:00:00Z",
        "score": 25.0,
    }
    with patch("src.curator.fetch_hf_trending", new_callable=AsyncMock, return_value=[]), \
         patch("src.curator.fetch_github_rising", new_callable=AsyncMock, return_value=[sample_gh_item]) as mock_gh:
        client = MagicMock()
        items, _ = await fetch_news(client, feed_list=[], include_api_sources=True, days_lookback=2)

    assert any(item["source_id"] == "github_rising" for item in items)
    assert mock_gh.call_args.kwargs["days_lookback"] == 7


@pytest.mark.asyncio
async def test_repository_with_readme_only_uses_readme_excerpt():
    now = datetime.now(timezone.utc)
    search_payload = {
        "items": [
            {
                "full_name": "org/readme-only",
                "html_url": "https://github.com/org/readme-only",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "stargazers_count": 100,
                "description": "",  # Empty description
            }
        ]
    }
    client = MagicMock()
    readme_resp = _response(status=200, text="# Project Title\n\nHigh-performance AI inference engine in C++.")
    client.get = AsyncMock(side_effect=[_response(search_payload, status=200), readme_resp])

    items = await fetch_github_rising(client)
    assert len(items) == 1
    assert items[0]["title"] == "org/readme-only"
    assert "High-performance AI inference engine in C++." in items[0]["summary"]
