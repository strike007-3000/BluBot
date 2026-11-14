"""Weekly LinkedIn draft: shortlist this week's stories in Telegram, draft one, deliver for manual posting.

Independent of the daily bot and the Friday roundup. Nothing is ever posted to LinkedIn.
"""
import asyncio
from datetime import datetime
from typing import Optional

import httpx
from google import genai

from src.linkedin_draft import build_verified_draft
from src.linkedin_select import (
    current_iso_week, eligible_this_week, is_week_done, mark_week_done, prerank, rate_candidates,
)
from src.linkedin_telegram import run_linkedin_session
from src.engagement import fetch_bluesky_metrics
from src.logger import SafeLogger
from src.settings import settings
from src.utils import load_seen_articles, save_seen_articles


async def run(client, genai_client, now: Optional[datetime] = None) -> str:
    if not settings.telegram_bot_token or not settings.telegram_user_id:
        return "telegram_disabled"
    iso_week = current_iso_week(now)
    state = await asyncio.to_thread(load_seen_articles)
    if is_week_done(state, iso_week):
        SafeLogger.info(f"LinkedIn weekly: {iso_week} already done.")
        return "skipped_done"
    eligible = eligible_this_week(state, iso_week)
    if not eligible:
        return "no_stories"

    metrics = await fetch_bluesky_metrics(client, eligible)
    candidates = await rate_candidates(genai_client, prerank(eligible, metrics), metrics)

    async def make_draft(candidate, take):
        return await build_verified_draft(genai_client, client, candidate.entry, take)

    result = await run_linkedin_session(candidates, iso_week, make_draft)
    if result is None:
        return "cancelled"
    if not result.reviewed:
        return "auto_drafted"
    mark_week_done(state, iso_week, result.candidate.entry["url"])
    saved, _ = await asyncio.to_thread(save_seen_articles, state)
    if not saved:
        SafeLogger.error("LinkedIn weekly: week marker was not persisted; a rerun may send another shortlist.")
        return "marker_failed"
    return "done"


async def main() -> None:
    genai_client = genai.Client(api_key=settings.gemini_key)
    async with httpx.AsyncClient(follow_redirects=False) as client:
        outcome = await run(client, genai_client)
    SafeLogger.info(f"LinkedIn weekly outcome: {outcome}")
    if outcome == "marker_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
