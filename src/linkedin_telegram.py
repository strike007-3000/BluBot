import asyncio
import time
from dataclasses import dataclass
from html import escape
from typing import Any, Awaitable, Callable, List, Optional, TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.settings import settings
from src.telegram_gateway import _make_bot
from src.utils import SafeLogger

if TYPE_CHECKING:  # Candidate/DraftResult live in sibling modules; duck-typed at runtime.
    from src.linkedin_select import Candidate
    from src.linkedin_draft import DraftResult

TAKE_MAX_CHARS = 1000
AUTO_LABEL = "Auto-selected, not reviewed"


@dataclass(frozen=True)
class SessionResult:
    candidate: "Candidate"
    draft: str
    reviewed: bool


def _kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in r] for r in rows])


async def run_linkedin_session(
    candidates: List["Candidate"],
    iso_week: str,
    make_draft: Callable[["Candidate", Optional[str]], Awaitable["DraftResult"]],
) -> Optional[SessionResult]:
    if not candidates or not settings.telegram_bot_token or not settings.telegram_user_id:
        return None
    bot = _make_bot(settings.telegram_bot_token)
    chat_id = settings.telegram_user_id
    offset = 0
    for u in await bot.get_updates(limit=100):  # drain stale updates
        offset = max(offset, u.update_id + 1)
    deadline = time.monotonic() + settings.linkedin_telegram_timeout_minutes * 60

    async def send(text: str, markup=None) -> int:
        m = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=markup)
        return m.message_id

    async def wait(msg_id: int, accept: Callable[[Any], Optional[Any]]) -> Optional[Any]:
        """Poll until accept(update) returns non-None or the shared deadline passes."""
        nonlocal offset
        while time.monotonic() < deadline:
            try:
                updates = await bot.get_updates(offset=offset, timeout=1)
            except Exception as e:
                SafeLogger.warn(f"LinkedIn Telegram: polling failed: {e}")
                await asyncio.sleep(1)
                continue
            for u in updates:
                offset = u.update_id + 1
                q, m = u.callback_query, u.message
                if q:
                    ok = str(q.from_user.id) == str(chat_id) and q.message.message_id == msg_id
                    parts = (q.data or "").split(":")
                    ok = ok and len(parts) >= 3 and parts[0] == "li" and parts[-1] == iso_week
                    res = accept(q) if ok else None
                    try:
                        await bot.answer_callback_query(q.id, text=None if res is not None else "Stale button")
                    except Exception:
                        pass
                    if res is not None:
                        return res
                elif m and str(m.from_user.id) == str(chat_id):
                    res = accept(m)
                    if res is not None:
                        return res
        return None

    def action(q) -> Optional[tuple]:
        if not hasattr(q, "data"):
            return None
        p = q.data.split(":")
        return (p[1], int(p[2]) if len(p) == 4 else None)

    # 1. Shortlist
    lines = ["<b>LinkedIn weekly shortlist</b>"]
    buttons = []
    for i, c in enumerate(candidates):
        lines.append(f"\n{i + 1}. <b>{escape(str(c.entry.get('title', '')))}</b>\n"
                     f"Enterprise angle: {escape(c.angle)}\nEngagement: {c.engagement}")
        buttons.append([(f"Pick {i + 1}", f"li:pick:{i}:{iso_week}")])
    buttons.append([("Cancel", f"li:cancel:{iso_week}")])
    sid = await send("\n".join(lines), _kb(*buttons))
    picked = await wait(sid, action)
    auto = picked is None
    take: Optional[str] = None
    if picked and picked[0] == "cancel":
        return None
    cand = candidates[0] if auto else candidates[picked[1] if picked[1] is not None and picked[1] < len(candidates) else 0]

    # 2. Optional take
    if not auto:
        pid = await send("Add personal context (reply to this message), or Skip.", _kb([("Skip", f"li:skip:{iso_week}")]))

        def take_or_skip(x) -> Optional[tuple]:
            if hasattr(x, "data"):
                return ("skip",) if x.data.startswith("li:skip") else None
            r = getattr(x, "reply_to_message", None)
            if r and r.message_id == pid and getattr(x, "text", None):
                return ("take", x.text[:TAKE_MAX_CHARS])
            return None

        t = await wait(pid, take_or_skip)
        if t and t[0] == "take":
            take = t[1]
            await send(f"Take saved: <i>{escape(take)}</i>")

    # 3. Draft / review loop
    while True:
        result = await make_draft(cand, take)
        if result.text is None:
            err = f"Draft failed: {escape(str(result.error or 'unknown error'))}"
            if auto:
                await send(f"{AUTO_LABEL}. {err}")
                return None
            eid = await send(err, _kb([("Retry", f"li:retry:{iso_week}"), ("Cancel", f"li:cancel:{iso_week}")]))
            a = await wait(eid, action)
            if a and a[0] == "retry":
                continue
            return None
        head = f"<b>{AUTO_LABEL}</b>\n" if auto else ""
        if not result.verified or result.flags:
            head += "<b>UNVERIFIED</b>: " + escape("; ".join(result.flags) or "not checked against source") + "\n"
        body = f"{head}\n{escape(result.text)}"
        if auto:
            await send(body)
            return SessionResult(cand, result.text, False)
        did = await send(body, _kb([("Done", f"li:done:{iso_week}"), ("Regenerate", f"li:regen:{iso_week}"),
                                    ("Cancel", f"li:cancel:{iso_week}")]))
        a = await wait(did, action)
        if a is None:  # review timed out: draft stays delivered in the chat
            return SessionResult(cand, result.text, False)
        if a[0] == "regen":
            continue
        if a[0] == "done":
            await send("Marked reviewed. Post it to LinkedIn manually.")
            return SessionResult(cand, result.text, True)
        return None
