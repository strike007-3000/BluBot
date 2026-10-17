"""Report-only Bluesky engagement metrics (public AppView, no login)."""
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx

from src.logger import SafeLogger

APPVIEW_GET_POSTS = "https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts"
BATCH_SIZE = 25
START_MARKER = "<!-- ENGAGEMENT:START -->"
END_MARKER = "<!-- ENGAGEMENT:END -->"
_FIELDS = (("likes", "likeCount"), ("reposts", "repostCount"), ("replies", "replyCount"), ("quotes", "quoteCount"))


def bluesky_uri(entry: dict) -> Optional[str]:
    uri = ((entry.get("posts") or {}).get("bluesky") or {}).get("uri")
    return uri if isinstance(uri, str) and uri.startswith("at://") else None


def recent_entries(state: dict, days: int = 7, now: Optional[datetime] = None) -> List[dict]:
    """Ledger entries published within the last `days` days that have a Bluesky URI."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    out = []
    for entry in state.get("published_posts", []):
        try:
            when = datetime.fromisoformat(str(entry.get("published_at")))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if when >= cutoff and bluesky_uri(entry):
            out.append(entry)
    return out


async def fetch_bluesky_metrics(client: httpx.AsyncClient, entries: List[dict]) -> Dict[str, Dict[str, int]]:
    """Return {uri: {likes, reposts, replies, quotes}}; {} on any failure."""
    uris = [u for u in (bluesky_uri(e) for e in entries) if u]
    metrics: Dict[str, Dict[str, int]] = {}
    try:
        for i in range(0, len(uris), BATCH_SIZE):
            resp = await client.get(APPVIEW_GET_POSTS, params=[("uris", u) for u in uris[i:i + BATCH_SIZE]], timeout=10.0)
            resp.raise_for_status()
            for post in resp.json().get("posts", []):
                metrics[post["uri"]] = {name: int(post.get(key) or 0) for name, key in _FIELDS}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        SafeLogger.warn(f"Engagement metrics unavailable: {e}")
        return {}
    return metrics


def render_table(metrics: Dict[str, Dict[str, int]], entries: List[dict]) -> str:
    rows = ["| Post | Likes | Reposts | Replies | Quotes |", "|:---|--:|--:|--:|--:|"]
    for e in entries:
        m = metrics.get(bluesky_uri(e) or "")
        if m:
            title = str(e.get("title", "")).replace("|", "/")[:60]
            rows.append(f"| {title} | {m['likes']} | {m['reposts']} | {m['replies']} | {m['quotes']} |")
    return "\n".join(rows)


def render_status_summary(metrics: Dict[str, Dict[str, int]], entries: List[dict]) -> str:
    """Compact 7-day summary block for STATUS.md."""
    scored = [(e, metrics[bluesky_uri(e)]) for e in entries if bluesky_uri(e) in metrics]
    if not scored:
        return "**Engagement (7d):** unavailable"
    totals = {k: sum(m[k] for _, m in scored) for k in ("likes", "reposts", "replies")}
    top, top_m = max(scored, key=lambda p: p[1]["likes"] + p[1]["reposts"] + p[1]["replies"])
    title = str(top.get("title", "")).replace("|", "/")[:60]
    return (f"**Engagement (7d):** {len(scored)} posts · {totals['likes']} likes · "
            f"{totals['reposts']} reposts · {totals['replies']} replies  \n"
            f"Top: {title} ({top_m['likes']}❤ {top_m['reposts']}🔁 {top_m['replies']}💬)")


def update_status_section(path: str, summary: str) -> None:
    """Replace (or insert) the marked engagement section in STATUS.md; idempotent."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    block = f"{START_MARKER}\n{summary}\n{END_MARKER}"
    start, end = text.find(START_MARKER), text.find(END_MARKER)
    if start != -1 and end > start:
        text = text[:start] + block + text[end + len(END_MARKER):]
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


async def update_engagement_report(client: httpx.AsyncClient, state: dict, status_path: str) -> None:
    """Fetch 7-day metrics and refresh STATUS.md. Never raises."""
    try:
        entries = recent_entries(state)
        metrics = await fetch_bluesky_metrics(client, entries)
        update_status_section(status_path, render_status_summary(metrics, entries))
    except Exception as e:
        SafeLogger.warn(f"Engagement report failed: {e}")
