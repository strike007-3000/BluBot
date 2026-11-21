import pytest
from unittest.mock import AsyncMock, MagicMock

from src.models import PlatformDrafts
from src.tagging import apply_tags, strip_tags, tag_state
from src.telegram_gateway import _build_telegram_markup


def test_tags_apply_strip_and_skip_when_no_room():
    d = PlatformDrafts(bluesky="Hello", threads="Hello", mastodon="Hello")
    tagged = apply_tags(d, "simon_willison")
    assert tagged.bluesky.endswith("cc @simonwillison.net")
    assert tagged.mastodon.endswith("cc @simon@simonwillison.net")
    assert tagged.threads == "Hello"  # Threads is out of scope
    assert tag_state(tagged, "simon_willison") is True
    assert apply_tags(tagged, "simon_willison") == tagged  # idempotent
    assert strip_tags(tagged, "simon_willison") == d
    assert tag_state(d, "simon_willison") is False
    assert tag_state(d, "openai_news") is None  # unverified source: no tag
    full = PlatformDrafts.from_single("x" * 290)
    assert apply_tags(full, "simon_willison").bluesky == "x" * 290  # no room


def test_tag_button_only_when_source_has_tag():
    def labels(**kw):
        return [b.text for row in _build_telegram_markup(**kw).inline_keyboard for b in row]
    assert not any("Source tag" in t for t in labels())
    assert "🏷 Source tag: ON ✅" in labels(tag_on=True)
    assert "🏷 Source tag: OFF" in labels(tag_on=False)


@pytest.mark.asyncio
async def test_mention_facets_resolve_and_degrade():
    from src.broadcaster import _mention_facets

    client = MagicMock()
    client.resolve_handle = AsyncMock(return_value=MagicMock(did="did:plc:abc123"))
    text = "Big news\n\ncc @simonwillison.net, mail me@example.com"
    facets = await _mention_facets(client, text)
    assert len(facets) == 1
    assert facets[0].features[0].did == "did:plc:abc123"
    start, end = facets[0].index.byte_start, facets[0].index.byte_end
    assert text.encode()[start:end] == b"@simonwillison.net"

    client.resolve_handle = AsyncMock(side_effect=RuntimeError("nope"))
    assert await _mention_facets(client, text) == []
