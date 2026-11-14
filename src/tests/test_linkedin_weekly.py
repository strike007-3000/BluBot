import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import linkedin_weekly as lw
from src.linkedin_draft import DraftResult
from src.linkedin_select import Candidate, is_week_done

NOW = datetime(2026, 11, 15, 9, tzinfo=timezone.utc)  # Sunday, ISO week 2026-W46
WEEK = "2026-W46"


def _entry(i):
    return {"url": f"https://a.example/{i}", "title": f"T{i}", "topic": "t", "summary": f"S{i}",
            "published_at": "2026-11-10T10:00:00+00:00", "category": "research_lab",
            "posts": {"bluesky": {"uri": f"at://x/{i}", "text": "BSKYTEXT"}}}


@pytest.fixture
def env(monkeypatch):
    st = SimpleNamespace(
        state={"published_posts": [_entry(1), _entry(2), _entry(3), _entry(4)]},
        saved=[], sessions=[], drafts=[], rate_prompts=[], published_calls=[],
    )
    monkeypatch.setattr(lw, "settings", SimpleNamespace(telegram_bot_token="tok", telegram_user_id="1"))
    monkeypatch.setattr(lw, "load_seen_articles", lambda: st.state)
    monkeypatch.setattr(lw, "save_seen_articles", lambda s, **k: (st.saved.append(s) or (True, s)))

    async def metrics(client, entries):
        return {}

    async def rate(genai_client, entries, m):
        st.rate_prompts.append([e["title"] for e in entries])
        return [Candidate(e, f"angle {e['title']}", 0) for e in entries[:3]]

    monkeypatch.setattr(lw, "fetch_bluesky_metrics", metrics)
    monkeypatch.setattr(lw, "rate_candidates", rate)

    st.outcome = "done"  # "done" | "auto" | "cancel"
    st.take = None
    st.results = []  # DraftResult queue for build_verified_draft

    async def build(genai_client, client, entry, take):
        st.drafts.append((entry["url"], take))
        return st.results.pop(0) if st.results else DraftResult("clean draft #a #b #c", True)

    async def session(candidates, iso_week, make_draft):
        st.sessions.append([c.entry["url"] for c in candidates])
        c = candidates[0]
        r = await make_draft(c, st.take)
        if st.outcome == "regen":
            r = await make_draft(c, st.take)
        if st.outcome == "cancel":
            return None
        return SimpleNamespace(candidate=c, draft=r.text, reviewed=st.outcome != "auto")

    monkeypatch.setattr(lw, "build_verified_draft", build)
    monkeypatch.setattr(lw, "run_linkedin_session", session)
    return st


def go():
    return asyncio.run(lw.run(None, None, NOW))


def test_normal_run_three_candidates_one_verified_draft(env):
    assert go() == "done"
    assert len(env.sessions[0]) == 3 and len(env.drafts) == 1
    assert env.saved and is_week_done(env.saved[0], WEEK)


def test_take_is_reflected_in_draft_call(env):
    env.take = "I saw this at a conference"
    go()
    assert env.drafts[0][1] == "I saw this at a conference"


def test_unsupported_statistic_withheld_is_not_saved_as_done(env):
    env.results = [DraftResult(None, False, error="27.7% not in source")]
    env.outcome = "cancel"
    assert go() == "cancelled"
    assert env.saved == []


def test_rerun_after_done_sends_no_second_shortlist(env):
    assert go() == "done"
    env.state = env.saved[0]
    env.sessions.clear()
    assert go() == "skipped_done"
    assert env.sessions == []


def test_regenerate_keeps_story_and_take_and_publishes_nothing(env, monkeypatch):
    env.outcome, env.take = "regen", "my context"
    go()
    assert len(env.drafts) == 2 and env.drafts[0] == env.drafts[1]
    import src.broadcaster as b
    assert not hasattr(lw, "post_to_bluesky") and b  # entry point never imports a broadcaster


def test_bluesky_text_never_reaches_rating_or_drafting(env):
    go()
    assert "BSKYTEXT" not in str(env.rate_prompts) and "BSKYTEXT" not in str(env.drafts)


def test_no_stories_sends_nothing(env):
    env.state = {"published_posts": []}
    assert go() == "no_stories" and env.sessions == []


def test_cancel_does_not_write_marker(env):
    env.outcome = "cancel"
    assert go() == "cancelled" and env.saved == []


def test_done_writes_marker_once(env):
    go()
    assert len(env.saved) == 1


def test_timeout_autodraft_returns_auto_drafted_and_writes_no_marker(env):
    env.outcome = "auto"
    assert go() == "auto_drafted" and env.saved == []


def test_missing_telegram_config_is_disabled(env, monkeypatch):
    monkeypatch.setattr(lw, "settings", SimpleNamespace(telegram_bot_token=None, telegram_user_id="1"))
    assert go() == "telegram_disabled" and env.sessions == []
