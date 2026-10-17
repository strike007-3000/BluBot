"""Unit tests for ledger helper and GitHub Pages / RSS archive builder."""
import email.utils
import html
import subprocess
import sys
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from scripts.build_archive import (
    at_uri_to_bsky_url,
    build_html,
    build_rss,
    compute_guid,
    is_valid_public_http_url,
    parse_rfc822_date,
)
from src.utils import PUBLISHED_POSTS_CAP, append_published_post, sanitize_and_migrate_state


def test_append_published_post_fields_and_defaults():
    state = {}
    entry = append_published_post(
        state,
        url="https://example.com/ai-news",
        title="Sample Breakthrough",
        topic="Robotics",
        posts={"bluesky": {"uri": "at://did:plc:123/app.bsky.feed.post/abc"}},
        published_at="2026-10-15T12:00:00Z",
    )
    assert entry["url"] == "https://example.com/ai-news"
    assert entry["title"] == "Sample Breakthrough"
    assert entry["topic"] == "Robotics"
    assert entry["kind"] == "post"
    assert entry["published_at"] == "2026-10-15T12:00:00Z"
    assert len(state["published_posts"]) == 1
    assert state["published_posts"][0]["topic"] == "Robotics"


def test_append_published_post_enforces_capacity():
    state = {
        "published_posts": [
            {"url": f"https://example.com/{i}", "title": f"T{i}", "published_at": f"2026-01-01T00:{i:02d}:00Z"}
            for i in range(PUBLISHED_POSTS_CAP)
        ]
    }
    append_published_post(
        state,
        url="https://example.com/latest",
        title="Latest",
        published_at="2026-10-17T00:00:00Z",
    )
    assert len(state["published_posts"]) == PUBLISHED_POSTS_CAP
    assert state["published_posts"][-1]["url"] == "https://example.com/latest"


def test_at_uri_to_bsky_url_conversions():
    assert (
        at_uri_to_bsky_url("at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3lbd443y")
        == "https://bsky.app/profile/did:plc:z72i7hdynmk6r22z27h6tvur/post/3lbd443y"
    )
    assert at_uri_to_bsky_url("https://example.com") is None
    assert at_uri_to_bsky_url("at://malformed") is None
    assert at_uri_to_bsky_url(None) is None


def test_is_valid_public_http_url():
    assert is_valid_public_http_url("https://github.com/org/repo") is True
    assert is_valid_public_http_url("http://example.com/article") is True
    assert is_valid_public_http_url("http://8.8.8.8/test") is True  # Public IP
    # Reject private / internal IP literals
    assert is_valid_public_http_url("http://127.0.0.1/test") is False
    assert is_valid_public_http_url("http://192.168.1.1/test") is False
    assert is_valid_public_http_url("http://10.0.0.1/test") is False
    # Reject non-http, ledger generated IDs, and empty values
    assert is_valid_public_http_url("generated:roundup:2026-W42") is False
    assert is_valid_public_http_url("at://did:plc:123/app.bsky.feed.post/abc") is False
    assert is_valid_public_http_url("") is False
    assert is_valid_public_http_url(None) is False


def test_build_html_escaping_and_fallbacks():
    entries = [
        {
            "url": "https://example.com/clean",
            "title": "Clean <script>alert(1)</script> Title",
            "topic": None,  # Falls back to General
            "published_at": "2026-10-17T12:00:00Z",
            "posts": {"bluesky": {"uri": "at://did:plc:user/app.bsky.feed.post/post1"}},
        },
        {
            "url": "generated:roundup:2026-W42",  # Should render as plain text, not a link
            "title": "Roundup Week 42",
            "topic": "Roundup",
            "published_at": "2026-10-17T18:00:00Z",
        },
    ]

    html_out = build_html(entries)
    # Check escaping
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_out
    # Check fallback topic
    assert '<span class="topic">General</span>' in html_out
    # Check Bluesky URL conversion
    assert "https://bsky.app/profile/did:plc:user/post/post1" in html_out
    # Check generated key is NOT rendered as an <a href=
    assert '<a href="generated:roundup:2026-W42"' not in html_out
    assert "generated:roundup:2026-W42" in html_out
    # Check cap notice presence
    assert "Archive displays up to the last 500 published stories" in html_out


def test_build_rss_structure_and_cap():
    entries = []
    for i in range(60):
        entries.append({
            "url": f"https://example.com/{i}",
            "title": f"Story {i}",
            "topic": "LLMs",
            "published_at": f"2026-10-10T12:{i:02d}:00Z",
            "posts": {"bluesky": {"uri": f"at://did:plc:u/app.bsky.feed.post/rkey{i}"}},
        })
    # Add an entry with an unparseable published_at to ensure it's skipped from RSS
    entries.append({
        "url": "https://example.com/bad-date",
        "title": "Bad Date",
        "published_at": "invalid-date",
    })

    rss_xml = build_rss(entries)
    root = ET.fromstring(rss_xml)
    assert root.tag == "rss"
    channel = root.find("channel")
    items = channel.findall("item")

    # Bounded to max 50 items
    assert len(items) == 50

    # Validate first item structure
    first = items[0]
    assert first.find("title") is not None
    assert first.find("link") is not None
    assert first.find("guid") is not None
    assert first.find("guid").attrib.get("isPermaLink") == "false"
    assert first.find("pubDate") is not None

    # Verify pubDate roundtrips RFC 822 format
    parsed_dt = email.utils.parsedate_to_datetime(first.find("pubDate").text)
    assert parsed_dt is not None


def test_compute_guid_stability():
    entry1 = {
        "url": "https://example.com/test",
        "published_at": "2026-10-17T12:00:00Z",
        "posts": {"bluesky": {"uri": "at://did:plc:x/app.bsky.feed.post/123"}},
    }
    entry2 = {
        "url": "https://example.com/test",
        "published_at": "2026-10-17T12:00:00Z",
    }
    # With AT URI, guid is the exact AT URI
    assert compute_guid(entry1) == "at://did:plc:x/app.bsky.feed.post/123"
    # Without AT URI, guid is stable sha256 hash
    g1 = compute_guid(entry2)
    g2 = compute_guid(entry2)
    assert g1 == g2
    assert len(g1) == 64


def test_build_archive_fail_closed_without_gist_credentials():
    """build_archive.py MUST exit non-zero when Gist state is unavailable."""
    from src.settings import settings
    object.__setattr__(settings, "gist_id", None)
    object.__setattr__(settings, "gist_token", None)

    with patch("sys.exit") as mock_exit, patch("src.logger.SafeLogger.error") as mock_log:
        from scripts import build_archive
        build_archive.main(argv=[])
        mock_exit.assert_called_once_with(1)
        mock_log.assert_called_once()
        assert "Archive build failed-closed" in mock_log.call_args[0][0]
