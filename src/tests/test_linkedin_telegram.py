import itertools
from types import SimpleNamespace as NS

import pytest
from src.settings import Settings
from src import linkedin_telegram as lt

pytestmark = pytest.mark.asyncio
WEEK = "2026-W46"
OWNER = 42


class Clock:
    t = 0.0

    def monotonic(self):
        return self.t


class FakeBot:
    def __init__(self, script, clock):
        self.script, self.clock, self.sent, self.ids = list(script), clock, [], itertools.count(1)
        self.answered = []

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        mid = next(self.ids)
        self.sent.append(NS(id=mid, text=text, markup=reply_markup))
        return NS(message_id=mid)

    async def answer_callback_query(self, qid, text=None):
        self.answered.append(text)

    async def get_updates(self, offset=None, timeout=None, limit=None):
        if limit:
            return []
        if self.script:
            return self.script.pop(0)(self)
        self.clock.t += 61  # nothing scripted: time passes
        return []


def cb(data, msg_id, user=OWNER, uid=[100]):
    uid[0] += 1
    return NS(update_id=uid[0], message=None,
              callback_query=NS(id="q", data=data, from_user=NS(id=user), message=NS(message_id=msg_id)))


def txt(text, reply_to, user=OWNER, uid=[500]):
    uid[0] += 1
    return NS(update_id=uid[0], callback_query=None,
              message=NS(text=text, from_user=NS(id=user), reply_to_message=NS(message_id=reply_to) if reply_to else None))


def cand(i=0):
    return NS(entry={"title": f"Story {i} <b>"}, angle=f"angle {i}", engagement=i)


def ok(text="Draft <x>", verified=True, flags=()):
    return NS(text=text, verified=verified, flags=tuple(flags), error=None)


@pytest.fixture
def run(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(lt, "time", clock)
    monkeypatch.setattr(lt, "settings", Settings(gemini_key="k", telegram_bot_token="t", telegram_user_id=str(OWNER),
                                                  linkedin_telegram_timeout_minutes=1))

    async def go(script, drafts, cands=None):
        bot = FakeBot([(lambda b, s=s: [s(b)] if callable(s) else [s]) for s in script], clock)
        monkeypatch.setattr(lt, "_make_bot", lambda token: bot)
        calls, it = [], iter(drafts)

        async def make_draft(c, take):
            calls.append((c, take))
            return next(it)

        res = await lt.run_linkedin_session(cands if cands is not None else [cand(0), cand(1), cand(2)], WEEK, make_draft)
        return res, bot, calls
    return go


async def test_pick_skip_done_returns_candidate_and_draft(run):
    res, bot, calls = await run([cb(f"li:pick:1:{WEEK}", 1), cb(f"li:skip:{WEEK}", 2), cb(f"li:done:{WEEK}", 3)], [ok()])
    assert res.reviewed and res.draft == "Draft <x>" and res.candidate.angle == "angle 1"
    assert calls[0][1] is None
    assert "Enterprise angle: angle 0" in bot.sent[0].text and "&lt;b&gt;" in bot.sent[0].text
    assert "Draft &lt;x&gt;" in bot.sent[2].text
    assert "Marked reviewed" in bot.sent[-1].text


async def test_reply_take_reaches_make_draft(run):
    res, _, calls = await run([cb(f"li:pick:0:{WEEK}", 1), txt("my take", 2), cb(f"li:done:{WEEK}", 4)], [ok()])
    assert calls[0][1] == "my take" and res.reviewed


async def test_unrelated_text_message_is_not_taken_as_take(run):
    res, _, calls = await run([cb(f"li:pick:0:{WEEK}", 1), txt("hello", None), txt("hi", 1),
                               cb(f"li:skip:{WEEK}", 2), cb(f"li:done:{WEEK}", 3)], [ok()])
    assert calls[0][1] is None


async def test_regenerate_keeps_story_and_take(run):
    res, _, calls = await run([cb(f"li:pick:2:{WEEK}", 1), txt("t", 2), cb(f"li:regen:{WEEK}", 4),
                               cb(f"li:done:{WEEK}", 5)], [ok("a"), ok("b")])
    assert len(calls) == 2 and calls[0] == calls[1] and res.draft == "b"


async def test_cancel_returns_none(run):
    res, _, calls = await run([cb(f"li:cancel:{WEEK}", 1)], [])
    assert res is None and not calls


async def test_shortlist_timeout_autodrafts_first_candidate_unreviewed(run):
    res, bot, calls = await run([], [ok()])
    assert res.reviewed is False and res.candidate.angle == "angle 0" and calls[0][1] is None
    assert "Auto-selected, not reviewed" in bot.sent[-1].text and bot.sent[-1].markup is None


async def test_take_prompt_timeout_proceeds_without_take(run):
    res, bot, calls = await run([cb(f"li:pick:0:{WEEK}", 1)], [ok()])
    assert calls[0][1] is None and res.reviewed is False


async def test_review_timeout_leaves_draft_delivered(run):
    res, bot, _ = await run([cb(f"li:pick:0:{WEEK}", 1), cb(f"li:skip:{WEEK}", 2)], [ok()])
    assert res.reviewed is False and res.draft == "Draft <x>"


async def test_autodraft_failure_returns_none_and_sends_error(run):
    res, bot, _ = await run([], [NS(text=None, verified=False, flags=(), error="boom")])
    assert res is None and "boom" in bot.sent[-1].text


async def test_non_owner_callback_ignored(run):
    res, _, calls = await run([cb(f"li:pick:1:{WEEK}", 1, user=7)], [ok()])
    assert res.candidate.angle == "angle 0" and res.reviewed is False  # fell through to auto-draft


async def test_stale_week_callback_ignored(run):
    res, bot, _ = await run([cb("li:pick:1:2026-W01", 1)], [ok()])
    assert res.candidate.angle == "angle 0" and "Stale button" in bot.answered


async def test_error_result_offers_retry_and_cancel(run):
    err = NS(text=None, verified=False, flags=(), error="bad")
    res, bot, calls = await run([cb(f"li:pick:0:{WEEK}", 1), cb(f"li:skip:{WEEK}", 2), cb(f"li:retry:{WEEK}", 3),
                                 cb(f"li:done:{WEEK}", 4)], [err, ok()])
    labels = [b.text for b in bot.sent[2].markup.inline_keyboard[0]]
    assert labels == ["Retry", "Cancel"] and len(calls) == 2 and res.reviewed


async def test_take_html_is_escaped_and_truncated(run):
    res, bot, calls = await run([cb(f"li:pick:0:{WEEK}", 1), txt("<i>" + "x" * 2000, 2), cb(f"li:done:{WEEK}", 4)], [ok()])
    assert len(calls[0][1]) == lt.TAKE_MAX_CHARS
    assert "&lt;i&gt;" in bot.sent[2].text and "<i>x" not in bot.sent[2].text


async def test_zero_candidates_sends_nothing(run):
    res, bot, _ = await run([], [], cands=[])
    assert res is None and not bot.sent
