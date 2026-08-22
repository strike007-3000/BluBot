import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.youtube_discovery import is_russian_facing, fetch_youtube_videos


@pytest.mark.asyncio
async def test_russian_hinting_detects_cyrillic():
    is_ru, score, hints = is_russian_facing(
        {
            "title": "Новый релиз Claude Code",
            "description": "Как запускать AI в проде.",
            "defaultAudioLanguage": "ru-RU",
        },
        text="обучение нейросетей",
    )

    assert is_ru is True
    assert score >= 3
    assert "lang_hint" in hints


@pytest.mark.asyncio
async def test_no_api_key_returns_empty(monkeypatch):
    from src.settings import Settings

    monkeypatch.setattr("src.youtube_discovery.settings", Settings(youtube_api_key=None))

    client = AsyncMock()
    videos = await fetch_youtube_videos(client)
    assert videos == []


@pytest.mark.asyncio
async def test_fetch_youtube_videos_returns_candidates(monkeypatch):
    from src.settings import Settings

    monkeypatch.setattr(
        "src.youtube_discovery.settings",
        Settings(
            youtube_api_key="test-key",
            youtube_seed_queries=["Claude Code"],
            youtube_region_codes=["RU"],
            youtube_language_hints=["ru", "en"],
        ),
    )

    now = datetime.now(timezone.utc)
    search_payload = {
        "items": [
            {"id": {"videoId": "abc123"}, "snippet": {"publishedAt": now.isoformat()}}
        ]
    }
    details_payload = {
        "items": [
            {
                "id": "abc123",
                "snippet": {
                    "title": "Claude Code News",
                    "description": "Короткий разбор обновления.",
                    "channelTitle": "AI Daily",
                    "publishedAt": now.isoformat(),
                    "defaultAudioLanguage": "ru-RU",
                },
                "statistics": {"viewCount": "12000", "likeCount": "100", "commentCount": "12"},
                "contentDetails": {"duration": "PT2M20S"},
            }
        ]
    }

    async def side_effect_get(url, params=None, timeout=None):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        if re.search(r"/search$", str(url)):
            mock_response.json.return_value = search_payload
        else:
            mock_response.json.return_value = details_payload
        return mock_response

    client = MagicMock()
    client.get = AsyncMock(side_effect=side_effect_get)

    videos = await fetch_youtube_videos(
        client,
        max_results_per_query=1,
        max_items=3,
        min_views=1000,
        min_duration_seconds=30,
    )

    assert len(videos) == 1
    assert videos[0].video_id == "abc123"
    assert videos[0].is_russian_facing is True
