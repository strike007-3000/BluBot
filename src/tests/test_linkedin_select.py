import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.linkedin_llm import gemini_generate
from src.linkedin_select import is_week_done, mark_week_done
from src.utils import sanitize_and_migrate_state


def _client(*behaviours):
    """Each behaviour is an Exception to raise or a str to return, consumed per call."""
    calls = iter(behaviours)

    async def gen(**kwargs):
        b = next(calls)
        if isinstance(b, Exception):
            raise b
        return SimpleNamespace(text=b)

    client = MagicMock()
    client.aio.models.generate_content = gen
    return client


def test_is_week_done_false_for_empty_state():
    assert is_week_done({}, "2026-W46") is False


def test_mark_week_done_then_is_week_done_true():
    state = mark_week_done({}, "2026-W46", "https://a.example/x")
    assert is_week_done(state, "2026-W46")
    assert not is_week_done(state, "2026-W47")


def test_marker_survives_sanitize_round_trip():
    state = mark_week_done({}, "2026-W46", "https://a.example/x")
    assert sanitize_and_migrate_state(state)["linkedin_weeks"] == state["linkedin_weeks"]
    assert sanitize_and_migrate_state({"linkedin_weeks": "bad"})["linkedin_weeks"] == {}


def test_gemini_generate_returns_none_when_all_models_fail():
    client = _client(*[RuntimeError("x")] * 20)
    assert asyncio.run(gemini_generate(client, "p", "s")) is None


def test_gemini_generate_rotates_to_next_model():
    client = _client(RuntimeError("x"), " ok ")
    assert asyncio.run(gemini_generate(client, "p", "s")) == "ok"


# ---- Task 2: candidate selection ----
import json
from datetime import datetime, timezone

from src.linkedin_select import (
    PRERANK_TOP_N, SHORTLIST_SIZE, current_iso_week, eligible_this_week,
    engagement_total, prerank, rate_candidates,
)

WEEK = "2026-W46"  # 2026-11-09..15


def _e(i, when="2026-11-10T10:00:00+00:00", **kw):
    e = {"url": f"https://a.example/{i}", "title": f"T{i}", "topic": "t", "summary": f"S{i}",
         "published_at": when, "posts": {"bluesky": {"uri": f"at://x/{i}", "text": "SECRETBSKY"}}}
    e.update(kw)
    return e


def test_current_iso_week_format():
    assert current_iso_week(datetime(2026, 11, 14, tzinfo=timezone.utc)) == WEEK


def test_eligible_this_week_excludes_roundup_entries():
    s = {"published_posts": [_e(1), _e(2, kind="roundup")]}
    assert [x["url"] for x in eligible_this_week(s, WEEK)] == ["https://a.example/1"]


def test_eligible_this_week_excludes_other_weeks():
    s = {"published_posts": [_e(1, when="2026-11-02T10:00:00+00:00"), _e(2)]}
    assert [x["url"] for x in eligible_this_week(s, WEEK)] == ["https://a.example/2"]


def test_eligible_this_week_excludes_invalid_urls():
    s = {"published_posts": [_e(1, url="generated:abc"), _e(2, url="http://127.0.0.1/x")]}
    assert eligible_this_week(s, WEEK) == []


def test_eligible_this_week_collapses_and_cuts_title():
    out = eligible_this_week({"published_posts": [_e(1, title="a \n  b" + "x" * 200)]}, WEEK)
    assert out[0]["title"].startswith("a b") and len(out[0]["title"]) == 120


def test_engagement_total_zero_without_metrics():
    assert engagement_total(_e(1), {}) == 0
    assert engagement_total(_e(1), {"at://x/1": {"likes": 1, "reposts": 2, "replies": 3, "quotes": 4}}) == 10


def test_prerank_orders_by_engagement_plus_category_boost():
    es = [_e(1), _e(2, category="research_lab"), _e(3, category="practitioner")]
    m = {"at://x/1": {"likes": 4}, "at://x/3": {"likes": 2}}
    assert [x["title"] for x in prerank(es, m)] == ["T1", "T3", "T2"]


def test_prerank_caps_at_eight():
    assert PRERANK_TOP_N == 8
    assert len(prerank([_e(i) for i in range(12)], {})) == 8


def _g(reply):
    prompts = []

    async def gen(**kw):
        prompts.append(kw["contents"])
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(text=reply)
    c = MagicMock()
    c.aio.models.generate_content = gen
    return c, prompts


def test_rate_candidates_keeps_relevant_and_angles():
    es = [_e(i) for i in range(3)]
    c, _ = _g(json.dumps([{"index": 0, "angle": "A0", "relevant": True},
                          {"index": 1, "angle": "A1", "relevant": False},
                          {"index": 2, "angle": "A2", "relevant": True}]))
    out = asyncio.run(rate_candidates(c, es, {}))
    assert [(x.entry["title"], x.angle) for x in out] == [("T0", "A0"), ("T2", "A2")]


def test_rate_candidates_falls_back_on_invalid_json():
    es = [_e(i) for i in range(5)]
    c, _ = _g("not json")
    out = asyncio.run(rate_candidates(c, es, {}))
    assert len(out) == SHORTLIST_SIZE and out[0].angle == "No angle available"


def test_rate_candidates_falls_back_when_gemini_fails():
    c, _ = _g(RuntimeError("x"))
    out = asyncio.run(rate_candidates(c, [_e(i) for i in range(4)], {}))
    assert len(out) == SHORTLIST_SIZE and out[0].angle == "No angle available"


def test_rate_candidates_with_two_entries_returns_two():
    c, _ = _g("bad")
    assert len(asyncio.run(rate_candidates(c, [_e(1), _e(2)], {}))) == 2


def test_rate_candidates_prompt_excludes_bluesky_text():
    c, prompts = _g("[]")
    asyncio.run(rate_candidates(c, [_e(1)], {}))
    assert prompts and "SECRETBSKY" not in prompts[0]
