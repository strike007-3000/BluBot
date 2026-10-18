"""Tests for the durable published_posts ledger and publisher root-ID returns."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.broadcaster as broadcaster
from src.models import Article, BroadcastResult, CurationResult, SynthesisResult
from src.settings import settings
from src.utils import (
    PUBLISHED_POSTS_CAP, _merge_publication_states, filter_and_update_pending_stories,
    sanitize_and_migrate_state,
)


@pytest.fixture
def set_setting():
    """Temporarily override frozen settings fields."""
    original = {}

    def _set(name, value):
        original.setdefault(name, getattr(settings, name))
        object.__setattr__(settings, name, value)

    yield _set
    for name, value in original.items():
        object.__setattr__(settings, name, value)


# --- Migration ---

def test_migration_adds_empty_ledger_to_legacy_state():
    assert sanitize_and_migrate_state({"links": []})["published_posts"] == []


def test_migration_replaces_non_list_ledger():
    assert sanitize_and_migrate_state({"published_posts": "bad"})["published_posts"] == []


def test_migration_drops_invalid_entries():
    state = sanitize_and_migrate_state({"published_posts": [
        {"url": "u1"}, "x", {"title": "no url"}, {"url": ""}, {"url": "   "},
        {"url": ["https://example.com/list"]}, {"url": {"value": "https://example.com/dict"}},
    ]})
    assert state["published_posts"] == [{"url": "u1"}]


def test_migration_caps_ledger_keeping_newest():
    entries = [
        {"url": f"u{i}", "published_at": f"2026-01-{(i % 28) + 1:02d}T{i // 28:02d}:00:00Z"}
        for i in range(PUBLISHED_POSTS_CAP + 100)
    ]
    entries.reverse()
    ledger = sanitize_and_migrate_state({"published_posts": entries})["published_posts"]
    assert len(ledger) == PUBLISHED_POSTS_CAP
    assert ledger == sorted(entries, key=lambda entry: entry["published_at"])[-PUBLISHED_POSTS_CAP:]


# --- Merge ---

def test_merge_unions_ledgers_and_merges_platform_posts():
    s1 = {"published_posts": [
        {"url": "a", "published_at": "2026-01-01", "posts": {"bluesky": {"uri": "at://a"}}},
        {"url": "b", "published_at": "2026-01-02", "posts": {}},
    ]}
    s2 = {"published_posts": [
        {"url": "a", "published_at": "2026-01-01", "posts": {"mastodon": {"id": "1"}}},
        {"url": "c", "published_at": "2026-01-03", "posts": {}},
    ]}
    ledger = _merge_publication_states(s1, s2)["published_posts"]
    assert [p["url"] for p in ledger] == ["a", "b", "c"]
    assert ledger[0]["posts"] == {"bluesky": {"uri": "at://a"}, "mastodon": {"id": "1"}}


def test_merge_combines_fields_for_the_same_platform_post():
    s1 = {"published_posts": [{
        "url": "a", "published_at": "2026-01-01",
        "posts": {"bluesky": {"uri": "at://a", "cid": "cid-a", "receipt_uri": None}},
    }]}
    s2 = {"published_posts": [{
        "url": "a", "published_at": "2026-01-01",
        "posts": {"bluesky": {"receipt_uri": "at://receipt"}},
    }]}

    entry = _merge_publication_states(s1, s2)["published_posts"][0]

    assert entry["posts"]["bluesky"] == {
        "uri": "at://a", "cid": "cid-a", "receipt_uri": "at://receipt",
    }


def test_merge_drops_entries_with_unhashable_urls():
    s1 = {"published_posts": [
        {"url": ["https://example.com/list"], "published_at": "2026-01-01"},
        {"url": "https://example.com/valid-1", "published_at": "2026-01-02"},
    ]}
    s2 = {"published_posts": [
        {"url": {"value": "https://example.com/dict"}, "published_at": "2026-01-03"},
        {"url": "https://example.com/valid-2", "published_at": "2026-01-04"},
    ]}

    ledger = _merge_publication_states(s1, s2)["published_posts"]

    assert [entry["url"] for entry in ledger] == [
        "https://example.com/valid-1", "https://example.com/valid-2",
    ]


def test_merge_caps_ledger():
    s1 = {"published_posts": [{"url": f"a{i}", "published_at": f"2026-01-01T00:{i:04d}"} for i in range(400)]}
    s2 = {"published_posts": [{"url": f"b{i}", "published_at": f"2026-02-01T00:{i:04d}"} for i in range(400)]}
    ledger = _merge_publication_states(s1, s2)["published_posts"]
    assert len(ledger) == PUBLISHED_POSTS_CAP
    assert ledger[-1]["url"] == "b399"


# --- Retention ---

def test_ledger_survives_14_day_pruning():
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    state = sanitize_and_migrate_state({
        "recent_stories": [{"url": "https://example.com/old", "published_at": old}],
        "published_posts": [{"url": "https://example.com/old", "published_at": old}],
    })
    filter_and_update_pending_stories(state)
    assert state["recent_stories"] == []
    assert state["published_posts"][0]["url"] == "https://example.com/old"


# --- Settlement ---

@pytest.mark.asyncio
async def test_settlement_records_only_successful_platform_ids(mocker, set_setting):
    import bot
    from bot import reserve_pending_stage, settle_persistence_stage

    mocker.patch.object(bot, "load_seen_articles", return_value={"pending_stories": []})
    mocker.patch.object(bot, "save_seen_articles", side_effect=lambda data, **_: (True, data))
    set_setting("is_dry_run", False)

    article = Article(title="Art 1", link="https://example.com/art1", summary="s",
                      published="2026-08-18T09:00:00+00:00", source="src", score=100,
                      supporting_links=["https://other.com/x"])
    curation = CurationResult(top_articles=[article], seen_links=[], recent_topics=[])
    synthesis = SynthesisResult(content="Content", lead_link="https://example.com/art1", topic="AI")

    state, matched = await reserve_pending_stage(curation, synthesis)
    results = [
        BroadcastResult("Bluesky", True, post_id="at://root", post_cid="cid1"),
        BroadcastResult("Mastodon", False, error="boom"),
        BroadcastResult("Threads", True),  # success without ID -> not recorded
    ]
    final = await settle_persistence_stage(state, curation, synthesis, matched, results)

    entry = final["published_posts"][-1]
    assert entry["url"] == "https://example.com/art1"
    assert entry["supporting_links"] == ["https://other.com/x"]
    assert entry["posts"] == {"bluesky": {"uri": "at://root", "cid": "cid1", "receipt_uri": None}}


# --- Publisher root IDs ---

@pytest.mark.asyncio
async def test_bluesky_returns_root_post(mocker, set_setting):
    set_setting("bsky_handle", "bot.bsky.social")
    set_setting("max_thread_parts", 3)
    mocker.patch.object(broadcaster, "human_delay", AsyncMock())
    mocker.patch.object(broadcaster, "smart_split", return_value=["one", "two"])
    root = SimpleNamespace(uri="at://root", cid="c0")
    child = SimpleNamespace(uri="at://child", cid="c1")
    client = MagicMock(send_post=AsyncMock(side_effect=[root, child]))

    assert await broadcaster.post_to_bluesky(client, None, "text") is root


@pytest.mark.asyncio
async def test_mastodon_returns_first_status_id(mocker, set_setting):
    set_setting("mastodon_token", "t")
    set_setting("mastodon_base_url", "https://m.example")
    mocker.patch.object(broadcaster, "human_delay", AsyncMock())
    mocker.patch.object(broadcaster, "smart_split", return_value=["a", "b", "c"])
    api = MagicMock()
    api.status_post.side_effect = [{"id": 101}, {"id": 102}, {"id": 103}]
    mocker.patch.object(broadcaster, "Mastodon", return_value=api)

    assert await broadcaster.post_to_mastodon("text") == 101


@pytest.mark.asyncio
async def test_threads_returns_first_published_id(mocker, set_setting):
    set_setting("threads_user_id", "u")
    set_setting("threads_token", "t")
    mocker.patch.object(broadcaster, "human_delay", AsyncMock())
    mocker.patch.object(broadcaster, "smart_split", return_value=["a", "b"])

    def resp(payload):
        r = MagicMock(status_code=200)
        r.json.return_value = payload
        return r

    client = MagicMock()
    client.post = AsyncMock(side_effect=[
        resp({"id": "c1"}), resp({"id": "root"}),
        resp({"id": "c2"}), resp({"id": "child"}),
    ])
    client.get = AsyncMock(return_value=resp({"status": "FINISHED"}))

    assert await broadcaster.post_to_threads(client, "text") == "root"


@pytest.mark.asyncio
async def test_bluesky_reply_targeting(set_setting):
    set_setting("bsky_handle", "user.bsky.social")
    root = SimpleNamespace(uri="at://first-update", cid="cu0")
    child = SimpleNamespace(uri="at://second-update", cid="cu1")
    client = MagicMock(send_post=AsyncMock(side_effect=[root, child]))

    reply_to = {"uri": "at://parent-root", "cid": "c-orig"}
    res = await broadcaster.post_to_bluesky(client, None, "text", reply_to=reply_to)
    assert res is root
    # First chunk replies to target root
    first_call = client.send_post.call_args_list[0]
    assert first_call.kwargs["reply_to"].root.uri == "at://parent-root"
    assert first_call.kwargs["reply_to"].parent.uri == "at://parent-root"


@pytest.mark.asyncio
async def test_mastodon_and_threads_reply_targeting(mocker, set_setting):
    set_setting("mastodon_token", "t")
    set_setting("mastodon_base_url", "https://m.example")
    set_setting("threads_user_id", "u")
    set_setting("threads_token", "t")
    mocker.patch.object(broadcaster, "human_delay", AsyncMock())
    mocker.patch.object(broadcaster, "smart_split", return_value=["update chunk"])

    # Mastodon in_reply_to_id
    api = MagicMock()
    api.status_post.return_value = {"id": 202}
    mocker.patch.object(broadcaster, "Mastodon", return_value=api)

    assert await broadcaster.post_to_mastodon("update chunk", reply_to_id=101) == 202
    assert api.status_post.call_args.kwargs["in_reply_to_id"] == 101

    # Threads reply_to_id
    def resp(payload):
        r = MagicMock(status_code=200)
        r.json.return_value = payload
        return r

    threads_client = MagicMock()
    threads_client.post = AsyncMock(side_effect=[
        resp({"id": "container_up"}), resp({"id": "published_up"})
    ])
    threads_client.get = AsyncMock(return_value=resp({"status": "FINISHED"}))

    published_id = await broadcaster.post_to_threads(threads_client, "update chunk", reply_to_id="root_threads_id")
    assert published_id == "published_up"
    # Container creation call includes reply_to_id
    container_call_data = threads_client.post.call_args_list[0].kwargs["data"]
    assert container_call_data["reply_to_id"] == "root_threads_id"
