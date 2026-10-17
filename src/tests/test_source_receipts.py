"""Tests for best-effort Bluesky source receipts."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot
import src.broadcaster as broadcaster
from src.models import Article, BroadcastResult
from src.settings import settings


@pytest.fixture(autouse=True)
def restore_receipt_settings():
    original = (
        settings.bluesky_limit,
        settings.enable_source_receipts_bsky,
        settings.is_dry_run,
    )
    yield
    object.__setattr__(settings, "bluesky_limit", original[0])
    object.__setattr__(settings, "enable_source_receipts_bsky", original[1])
    object.__setattr__(settings, "is_dry_run", original[2])


def _article(**overrides):
    values = {
        "title": "Model release",
        "link": "https://lead.example/story",
        "summary": "summary",
        "published": "2026-10-17T00:00:00Z",
        "source": "Lead",
        "consensus_synergy": True,
        "supporting_sources": ["Source One", "Source Two"],
        "supporting_links": ["https://one.example/report", "https://two.example/report"],
    }
    values.update(overrides)
    return Article(**values)


def test_receipt_pair_filtering_keeps_sources_aligned():
    article = _article(
        supporting_sources=["Lead Copy", "Invalid", "Keep One", "Duplicate One", "Keep Two"],
        supporting_links=[
            "https://lead.example/story?utm_source=x",
            "not-a-url",
            "https://one.example/report?utm_campaign=x",
            "https://one.example/report#duplicate",
            "https://two.example/report",
        ],
    )

    assert bot._source_receipt_pairs(article) == [
        ("Keep One", "https://one.example/report"),
        ("Keep Two", "https://two.example/report"),
    ]


@pytest.mark.asyncio
async def test_receipt_replies_to_root_with_two_link_facets():
    client = MagicMock(send_post=AsyncMock(return_value=SimpleNamespace(uri="at://receipt")))

    receipt = await broadcaster.post_bluesky_receipt(
        client,
        "at://root",
        "root-cid",
        [("Sourcé", "https://one.example/a"), ("Two", "https://two.example/b"), ("Three", "https://three.example/c")],
    )

    assert receipt == "at://receipt"
    kwargs = client.send_post.await_args.kwargs
    assert kwargs["reply_to"].root.uri == "at://root"
    assert kwargs["reply_to"].root.cid == "root-cid"
    assert kwargs["reply_to"].parent == kwargs["reply_to"].root
    assert "Three" not in kwargs["text"]
    assert len(kwargs["facets"]) == 2
    first_url = "https://one.example/a"
    expected_start = len(kwargs["text"].split(first_url)[0].encode("utf-8"))
    assert kwargs["facets"][0].index.byte_start == expected_start
    assert kwargs["facets"][0].index.byte_end == expected_start + len(first_url.encode("utf-8"))


@pytest.mark.asyncio
async def test_receipt_drops_second_pair_then_skips_if_one_pair_is_too_long():
    object.__setattr__(settings, "bluesky_limit", 80)
    client = MagicMock(send_post=AsyncMock(return_value=SimpleNamespace(uri="at://receipt")))

    receipt = await broadcaster.post_bluesky_receipt(
        client,
        "at://root",
        "cid",
        [("One", "https://one.example/a"), ("X" * 100, "https://two.example/b")],
    )
    assert receipt == "at://receipt"
    assert "two.example" not in client.send_post.await_args.kwargs["text"]

    client.send_post.reset_mock()
    assert await broadcaster.post_bluesky_receipt(
        client, "at://root", "cid", [("X" * 100, "https://one.example/a")]
    ) is None
    client.send_post.assert_not_awaited()


@pytest.mark.asyncio
async def test_receipt_send_failure_is_nonfatal():
    client = MagicMock(send_post=AsyncMock(side_effect=RuntimeError("network")))
    assert await broadcaster.post_bluesky_receipt(
        client, "at://root", "cid", [("One", "https://one.example/a")]
    ) is None


@pytest.mark.asyncio
async def test_receipt_stage_updates_result_and_settled_ledger(mocker):
    object.__setattr__(settings, "enable_source_receipts_bsky", True)
    object.__setattr__(settings, "is_dry_run", False)
    state = {"published_posts": [{
        "url": "https://lead.example/story",
        "posts": {"bluesky": {"uri": "at://root", "cid": "cid", "receipt_uri": None}},
    }]}
    results = [BroadcastResult("Bluesky", True, post_id="at://root", post_cid="cid")]
    mocker.patch("bot.post_bluesky_receipt", new_callable=AsyncMock, return_value="at://receipt")
    save = mocker.patch("bot.save_seen_articles", side_effect=lambda data, **_: (True, data))

    updated_state, updated_results = await bot.source_receipt_stage(
        state, _article(), results, MagicMock()
    )

    assert updated_state["published_posts"][0]["posts"]["bluesky"]["receipt_uri"] == "at://receipt"
    assert updated_results[0].success is True
    assert updated_results[0].receipt_id == "at://receipt"
    save.assert_called_once()


@pytest.mark.asyncio
async def test_receipt_post_failure_preserves_root_success(mocker):
    object.__setattr__(settings, "enable_source_receipts_bsky", True)
    object.__setattr__(settings, "is_dry_run", False)
    result = BroadcastResult("Bluesky", True, post_id="at://root", post_cid="cid")
    mocker.patch("bot.post_bluesky_receipt", new_callable=AsyncMock, return_value=None)

    _, returned = await bot.source_receipt_stage({}, _article(), [result], MagicMock())

    assert returned == [result]
    assert returned[0].success is True


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["flag", "dry", "synergy", "client", "failed", "cid", "pairs"])
async def test_receipt_stage_skip_conditions(mocker, case):
    object.__setattr__(settings, "enable_source_receipts_bsky", case != "flag")
    object.__setattr__(settings, "is_dry_run", case == "dry")
    article = _article(
        consensus_synergy=case != "synergy",
        supporting_links=[] if case == "pairs" else ["https://one.example/report"],
        supporting_sources=[] if case == "pairs" else ["One"],
    )
    client = None if case == "client" else MagicMock()
    result = BroadcastResult(
        "Bluesky", case != "failed", post_id="at://root", post_cid=None if case == "cid" else "cid"
    )
    post = mocker.patch("bot.post_bluesky_receipt", new_callable=AsyncMock)

    _, returned = await bot.source_receipt_stage({}, article, [result], client)

    post.assert_not_awaited()
    assert returned == [result]
