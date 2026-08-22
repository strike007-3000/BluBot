"""YouTube discovery primitives for the content factory pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple
import re

from src.logger import SafeLogger
from src.settings import settings


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
DEFAULT_VIDEOS_PER_QUERY = 8
DEFAULT_MAX_ITEMS = 12
ISO_DURATION_RE = re.compile(r"PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?")


@dataclass(frozen=True)
class YouTubeVideo:
    """Normalized video candidate produced by discovery."""

    video_id: str
    title: str
    channel_title: str
    description: str
    url: str
    published_at: str
    views: int
    likes: int
    comments: int
    duration_seconds: Optional[int]
    russian_score: int
    is_russian_facing: bool
    language_hints: List[str]

    def as_article_dict(self) -> Dict[str, str]:
        """Project the video into the existing curation story format."""
        summary = self.description.strip()
        if len(summary) > 220:
            summary = summary[:217].rstrip() + "..."
        return {
            "title": self.title,
            "summary": summary,
            "link": self.url,
            "published": self.published_at,
            "source": "YouTube",
            "source_url": "https://www.youtube.com/",
            "source_id": "youtube",
            "score": self.views,
        }


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # ISO-8601 from YouTube can end in 'Z'
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _parse_iso_duration(duration: Optional[str]) -> Optional[int]:
    if not duration:
        return None
    match = ISO_DURATION_RE.fullmatch(duration)
    if not match:
        return None
    parts = match.groupdict(default="0")
    hours = int(parts["h"])
    minutes = int(parts["m"])
    seconds = int(parts["s"])
    return hours * 3600 + minutes * 60 + seconds


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def is_russian_facing(snippet: Dict[str, Any], text: str = "") -> Tuple[bool, int, List[str]]:
    """
    Heuristic Russian relevance check:
    - explicit language hints (defaultAudioLanguage/defaultLanguage),
    - Cyrillic text presence,
    - russian marker words.
    """
    hints = []
    lang = (snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "").lower()
    if lang:
        hints.append(lang)

    title = (snippet.get("title") or "").lower()
    desc = (snippet.get("description") or "").lower()
    combined = " ".join([title, desc, (text or "").lower()])
    extra_text = combined.strip()

    score = 0
    if lang.startswith("ru") or snippet.get("defaultLanguage", "").startswith("ru"):
        score += 4
        hints.append("lang_hint")

    ru_keywords = {"русск", "нейросеть", "обучение", "чат", "код", "модель", "виде"}
    if any(keyword in extra_text for keyword in ru_keywords):
        score += 2
        hints.append("keyword")

    if re.search(r"[А-Яа-я]", combined):
        score += 3
        hints.append("cyrillic")

    is_ru = score >= 3
    return is_ru, score, list(dict.fromkeys(hints))


def _safe_youtube_id_to_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


async def _request_json(client, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{YOUTUBE_API_BASE}/{endpoint}"
    response = await client.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


async def fetch_youtube_videos(
    client,
    query_terms: Optional[Sequence[str]] = None,
    *,
    region_codes: Optional[Sequence[str]] = None,
    language_hints: Optional[Sequence[str]] = None,
    max_results_per_query: int = DEFAULT_VIDEOS_PER_QUERY,
    max_items: int = DEFAULT_MAX_ITEMS,
    only_russian_facing: bool = False,
    age_days: int = 30,
    min_views: int = 200,
    min_duration_seconds: int = 90,
) -> List[YouTubeVideo]:
    """
    Fetches YouTube candidates from search and videos endpoints.
    Returns normalized candidates sorted by view count + recency.
    """
    api_key = settings.youtube_api_key
    if not api_key:
        SafeLogger.warn("YouTube discovery skipped: YOUTUBE_API_KEY is not configured.")
        return []

    if max_results_per_query <= 0 or max_items <= 0:
        return []

    terms = list(query_terms or [])
    if not terms:
        terms = settings.youtube_seed_queries or [
            "Claude Code",
            "OpenAI Codex",
            "AI agents MCP",
        ]

    regions = list(region_codes or settings.youtube_region_codes or [])
    if not regions:
        regions = ["US"]

    hints = list(language_hints or settings.youtube_language_hints or ["ru", "en"])
    max_results_per_query = max(1, min(50, int(max_results_per_query)))
    max_items = max(1, min(50, int(max_items)))
    age_cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(age_days)))

    video_scores: Dict[str, Dict[str, Any]] = {}

    for region in regions:
        for term in terms:
            params = {
                "part": "snippet",
                "type": "video",
                "order": "viewCount",
                "maxResults": max_results_per_query,
                "q": term,
                "regionCode": region,
                "relevanceLanguage": "en",
                "key": api_key,
                "videoEmbeddable": "true",
            }
            search_payload = await _request_json(
                client,
                "search",
                params=params,
            )

            for item in search_payload.get("items", []):
                snippet = item.get("snippet") or {}
                video_id = item.get("id", {}).get("videoId")
                if not video_id:
                    continue
                raw_published = snippet.get("publishedAt")
                published = _parse_iso_timestamp(raw_published)
                if published and published < age_cutoff:
                    continue
                video_scores[video_id] = {
                    "snippet": snippet,
                    "published": published,
                }

            # No more calls when cap reached.
            if len(video_scores) >= max_items * 3:
                break
        if len(video_scores) >= max_items * 3:
            break

    if not video_scores:
        return []

    # Enrich selected ids in a single videos.list call.
    ids = list(video_scores.keys())[: min(50, max_items * 3)]
    details_payload = await _request_json(
        client,
        "videos",
        params={
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(ids),
            "key": api_key,
        },
    )

    out: List[YouTubeVideo] = []
    for item in details_payload.get("items", []):
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        duration = _parse_iso_duration((item.get("contentDetails") or {}).get("duration"))
        published = _parse_iso_timestamp(snippet.get("publishedAt"))
        published_text = snippet.get("publishedAt") or datetime.now(timezone.utc).isoformat()

        is_ru, ru_score, ru_hints = is_russian_facing(snippet)
        if only_russian_facing and not is_ru:
            continue

        views = _as_int(stats.get("viewCount"))
        likes = _as_int(stats.get("likeCount"))
        comments = _as_int(stats.get("commentCount"))
        if views < min_views:
            continue
        if duration is not None and duration < min_duration_seconds:
            continue
        if published and published < age_cutoff:
            continue

        lang_match = False
        langs = []
        for candidate in [
            lang
            for lang in [
                snippet.get("defaultLanguage", ""),
                snippet.get("defaultAudioLanguage", ""),
            ]
            if isinstance(lang, str)
        ]:
            lang_code = candidate.split("-", 1)[0].lower()
            if lang_code:
                langs.append(lang_code)
            if lang_code in [h.lower() for h in hints]:
                lang_match = True

        # При включении include-all-languages не фильтруем,
        # при отсутствии явной языковой метки не режем русские-ориентированный контент.
        if not lang_match and (not langs) and "ru" in [h.lower() for h in hints] and is_ru:
            lang_match = True

        out.append(
            YouTubeVideo(
                video_id=item.get("id", ""),
                title=snippet.get("title", ""),
                channel_title=snippet.get("channelTitle", "Unknown"),
                description=snippet.get("description", ""),
                url=_safe_youtube_id_to_url(item.get("id", "")),
                published_at=published_text,
                views=views,
                likes=likes,
                comments=comments,
                duration_seconds=duration,
                russian_score=ru_score,
                is_russian_facing=is_ru or lang_match,
                language_hints=langs,
            )
        )

    out.sort(key=lambda x: (x.views + x.russian_score * 10), reverse=True)
    return out[:max_items]
