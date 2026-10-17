"""Tests for report-only engagement metrics."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src import engagement as eng

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def _entry(n, days_ago=1, with_uri=True):
    posts = {"bluesky": {"uri": f"at://did:plc:x/app.bsky.feed.post/{n}"}} if with_uri else {}
    return {"url": f"https://e.com/{n}", "title": f"T{n}", "posts": posts,
            "published_at": (NOW - timedelta(days=days_ago)).isoformat()}


def _client(payload=None, exc=None):
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload or {"posts": []}
    client.get = AsyncMock(side_effect=exc) if exc else AsyncMock(return_value=resp)
    return client


def test_recent_entries_filters_age_and_missing_uri():
    state = {"published_posts": [_entry(1), _entry(2, days_ago=9), _entry(3, with_uri=False)]}
    assert [e["url"] for e in eng.recent_entries(state, 7, NOW)] == ["https://e.com/1"]


@pytest.mark.asyncio
async def test_fetch_batches_25_and_parses_counts():
    entries = [_entry(i) for i in range(30)]
    payload = {"posts": [{"uri": eng.bluesky_uri(entries[0]), "likeCount": 3, "repostCount": 1, "replyCount": 2}]}
    client = _client(payload)
    metrics = await eng.fetch_bluesky_metrics(client, entries)
    assert client.get.await_count == 2
    first_params = client.get.await_args_list[0].kwargs["params"]
    assert len(first_params) == 25 and first_params[0][0] == "uris"
    assert metrics[eng.bluesky_uri(entries[0])] == {"likes": 3, "reposts": 1, "replies": 2, "quotes": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [httpx.ConnectTimeout("t"), ValueError("bad json")])
async def test_fetch_returns_empty_on_error(exc):
    assert await eng.fetch_bluesky_metrics(_client(exc=exc), [_entry(1)]) == {}


def test_status_section_is_idempotent(tmp_path):
    path = tmp_path / "STATUS.md"
    path.write_text("# Status\n")
    eng.update_status_section(str(path), "first")
    eng.update_status_section(str(path), "second")
    text = path.read_text()
    assert text.count(eng.START_MARKER) == 1 and "second" in text and "first" not in text


def test_summary_unavailable_without_metrics():
    assert "unavailable" in eng.render_status_summary({}, [_entry(1)])


def test_summary_reports_top_post():
    e1, e2 = _entry(1), _entry(2)
    metrics = {eng.bluesky_uri(e1): {"likes": 1, "reposts": 0, "replies": 0, "quotes": 0},
               eng.bluesky_uri(e2): {"likes": 5, "reposts": 1, "replies": 0, "quotes": 0}}
    out = eng.render_status_summary(metrics, [e1, e2])
    assert "2 posts" in out and "6 likes" in out and "Top: T2" in out


def test_diagnostic_ask_never_blocks_in_non_interactive_mode(monkeypatch):
    import importlib.util, pathlib
    path = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "diagnostic.py"
    spec = importlib.util.spec_from_file_location("diagnostic_mod", path)
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("input() called"))
    diag.NON_INTERACTIVE = True
    assert diag._ask("x") == ""
