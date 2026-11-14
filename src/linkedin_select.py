"""Week marker and candidate selection for the LinkedIn weekly draft."""
from datetime import datetime, timezone
from typing import Optional


def is_week_done(state: dict, iso_week: str) -> bool:
    return iso_week in (state.get("linkedin_weeks") or {})


def mark_week_done(state: dict, iso_week: str, url: str) -> dict:
    weeks = state.get("linkedin_weeks")
    if not isinstance(weeks, dict):
        weeks = state["linkedin_weeks"] = {}
    weeks[iso_week] = {"status": "done", "url": url, "at": datetime.now(timezone.utc).isoformat()}
    return state
