"""Tests for the breaking-news gate."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.curator import select_breaking

NOW = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
ARGS = dict(min_score=40, max_age_hours=6, cooldown_hours=3, max_posts_24h=4)


def _art(score=45, age_h=2):
    return SimpleNamespace(score=score, published=(NOW - timedelta(hours=age_h)).isoformat(), title="T")


def _posts(*hours_ago):
    return [{"published_at": (NOW - timedelta(hours=h)).isoformat()} for h in hours_ago]


def test_strong_fresh_story_passes():
    lead = _art()
    assert select_breaking([lead], _posts(8), NOW, **ARGS) is lead


def test_weak_or_stale_story_is_rejected():
    assert select_breaking([_art(score=35)], [], NOW, **ARGS) is None
    assert select_breaking([_art(age_h=9)], [], NOW, **ARGS) is None


def test_cooldown_blocks_recent_post():
    assert select_breaking([_art()], _posts(1), NOW, **ARGS) is None


def test_daily_cap_blocks_fifth_post():
    assert select_breaking([_art()], _posts(5, 9, 15, 20), NOW, **ARGS) is None
    assert select_breaking([_art()], _posts(5, 9, 15, 26), NOW, **ARGS) is not None


def test_empty_candidates_and_bad_dates_do_not_crash():
    assert select_breaking([], [], NOW, **ARGS) is None
    bad = SimpleNamespace(score=50, published="not a date", title="T")
    assert select_breaking([bad], [{"published_at": "junk"}, {}], NOW, **ARGS) is None
