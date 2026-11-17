"""Tests for the breaking-news gate."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.curator import select_breaking

NOW = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
ARGS = dict(min_score=40, max_age_hours=6, cooldown_hours=3)


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


def test_one_breaking_post_per_rolling_day_regardless_of_scheduled_posts():
    breaking = [{"published_at": (NOW - timedelta(hours=10)).isoformat(), "breaking": True}]
    assert select_breaking([_art()], breaking, NOW, **ARGS) is None
    old_breaking = [{"published_at": (NOW - timedelta(hours=25)).isoformat(), "breaking": True}]
    assert select_breaking([_art()], old_breaking, NOW, **ARGS) is not None
    scheduled_only = _posts(5, 9, 15, 20)  # many scheduled posts must not block the lane
    assert select_breaking([_art()], scheduled_only, NOW, **ARGS) is not None


def test_empty_candidates_and_bad_dates_do_not_crash():
    assert select_breaking([], [], NOW, **ARGS) is None
    bad = SimpleNamespace(score=50, published="not a date", title="T")
    assert select_breaking([bad], [{"published_at": "junk"}, {}], NOW, **ARGS) is None


def test_append_published_post_records_breaking_marker():
    from src.utils import append_published_post
    state = {}
    entry = append_published_post(state, url="https://e.com/a", title="A", breaking=True)
    normal = append_published_post(state, url="https://e.com/b", title="B")
    assert entry["breaking"] is True and "breaking" not in normal
