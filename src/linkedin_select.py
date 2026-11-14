"""Week marker and candidate selection for the LinkedIn weekly draft."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from scripts.build_archive import is_valid_public_http_url
from src.engagement import bluesky_uri
from src.linkedin_llm import gemini_generate

PRERANK_TOP_N = 8
SHORTLIST_SIZE = 3
_BOOST = {"research_lab": 3, "enterprise": 3, "academic": 3, "open_source": 3, "practitioner": 2}
_NO_ANGLE = "No angle available"


@dataclass(frozen=True)
class Candidate:
    entry: dict
    angle: str
    engagement: int


def current_iso_week(now: Optional[datetime] = None) -> str:
    y, w, _ = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def eligible_this_week(state: dict, iso_week: str) -> List[dict]:
    out = []
    for e in state.get("published_posts") or []:
        try:
            when = datetime.fromisoformat(str(e.get("published_at")))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if current_iso_week(when) != iso_week or e.get("kind") == "roundup":
            continue
        if not is_valid_public_http_url(e.get("url")):
            continue
        out.append({**e, "title": " ".join(str(e.get("title") or "").split())[:120]})
    return out


def engagement_total(entry: dict, metrics: Dict[str, Dict[str, int]]) -> int:
    m = metrics.get(bluesky_uri(entry) or "") or {}
    return sum(int(m.get(k) or 0) for k in ("likes", "reposts", "replies", "quotes"))


def prerank(entries: List[dict], metrics: Dict[str, Dict[str, int]]) -> List[dict]:
    def score(e):
        return engagement_total(e, metrics) + _BOOST.get(e.get("category"), 0)
    # ISO timestamps sort lexically; shortcut: assumes a uniform UTC format for tie-breaks.
    ranked = sorted(entries, key=lambda e: str(e.get("published_at")), reverse=True)
    return sorted(ranked, key=score, reverse=True)[:PRERANK_TOP_N]


async def rate_candidates(genai_client, entries: List[dict], metrics) -> List[Candidate]:
    def fallback():
        return [Candidate(e, _NO_ANGLE, engagement_total(e, metrics)) for e in entries[:SHORTLIST_SIZE]]

    items = [{"index": i, "title": e.get("title"), "topic": e.get("topic"), "summary": e.get("summary")}
             for i, e in enumerate(entries)]
    prompt = (
        "Rate these stories for an enterprise-focused LinkedIn post. Return a JSON array of "
        '{"index": int, "angle": "one-sentence enterprise angle", "relevant": bool}.\n'
        + json.dumps(items, ensure_ascii=False)
    )
    raw = await gemini_generate(genai_client, prompt, "You are an editorial assistant.", json_mode=True)
    try:
        out = [
            Candidate(entries[r["index"]], str(r.get("angle") or _NO_ANGLE), engagement_total(entries[r["index"]], metrics))
            for r in sorted(json.loads(raw), key=lambda r: r["index"]) if r.get("relevant") is True
        ][:SHORTLIST_SIZE]
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        return fallback()
    return out or fallback()


def is_week_done(state: dict, iso_week: str) -> bool:
    return iso_week in (state.get("linkedin_weeks") or {})


def mark_week_done(state: dict, iso_week: str, url: str) -> dict:
    weeks = state.get("linkedin_weeks")
    if not isinstance(weeks, dict):
        weeks = state["linkedin_weeks"] = {}
    weeks[iso_week] = {"status": "done", "url": url, "at": datetime.now(timezone.utc).isoformat()}
    return state
