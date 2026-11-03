import pytest
from unittest.mock import AsyncMock
from src import telegram_gateway as tg


def test_split_news_with_and_without_url():
    assert tg.split_news("Google launched X https://a.com/p") == ("Google launched X", "https://a.com/p")
    assert tg.split_news("Google launched X") == ("Google launched X", None)


def test_news_command_parsing():
    ok = tg.process_authorized_command("/news Google launched X https://example.com/a")
    assert ok["action"] == "news" and ok["topic"] == "Google launched X https://example.com/a"
    assert tg.process_authorized_command("/news Google launched X")["action"] == "news"
    assert tg.process_authorized_command("/news Hi http://127.0.0.1/x")["action"] == "news_invalid"


@pytest.mark.asyncio
async def test_abort_unapproved_requeues_and_raises(mocker, tmp_path):
    f = tmp_path / "pending.json"
    mocker.patch("src.config.PENDING_TOPIC_FILE_PATH", str(f))
    bot = mocker.patch("src.telegram_gateway._make_bot").return_value
    bot.send_message = AsyncMock()
    with pytest.raises(tg.ApprovalUnavailable):
        await tg._abort_unapproved(1, {"topic": "t u", "kind": "news"}, "Approval timed out.")
    assert '"kind": "news"' in f.read_text()
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_own_thread_parts_not_counted_as_replies():
    from src.engagement import _external_replies

    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"thread": {"replies": [{"post": {"author": {"did": "me"}}}, {"post": {"author": {"did": "x"}}}]}}

    class C:
        async def get(self, *a, **k): return R()

    post = {"uri": "at://u", "replyCount": 2, "author": {"did": "me"}}
    assert await _external_replies(C(), post) == 1
