"""Unit tests for ledger helper, GitHub Pages Source Trust Dashboard, and RSS archive builder."""
from datetime import datetime, timezone
import email.utils
import html
import subprocess
import sys
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.build_archive import (
    at_uri_to_bsky_url,
    build_html,
    build_rss,
    classify_content_type,
    compute_guid,
    compute_trust_stats,
    extract_display_domain,
    fetch_metrics_best_effort,
    format_human_date,
    get_independent_support_domains,
    get_display_category,
    get_display_source_and_domain,
    is_valid_public_http_url,
    parse_date_safe,
    parse_rfc822_date,
)
from src.utils import PUBLISHED_POSTS_CAP, append_published_post, sanitize_and_migrate_state


# --- Required Coverage 1: New ledger metadata is stored ---
def test_append_published_post_stores_new_metadata():
    state = {}
    entry = append_published_post(
        state,
        url="https://github.com/fast/repo",
        title="Fast Rising Repo",
        topic="Open Source",
        source="GitHub Fast-Rising Repositories",
        source_id="github_rising",
        category="open_source",
        supporting_sources=["TechCrunch", "Meta AI"],
        published_at="2026-10-15T12:00:00Z",
    )
    assert entry["source"] == "GitHub Fast-Rising Repositories"
    assert entry["source_id"] == "github_rising"
    assert entry["category"] == "open_source"
    assert entry["supporting_sources"] == ["TechCrunch", "Meta AI"]
    assert state["published_posts"][0]["source_id"] == "github_rising"
    assert state["published_posts"][0]["supporting_sources"] == ["TechCrunch", "Meta AI"]


# --- Required Coverage 2: Existing ledger entries without new fields remain valid ---
def test_existing_ledger_entries_without_new_fields_remain_valid():
    legacy_entry = {
        "url": "https://example.com/legacy",
        "title": "Legacy Story",
        "topic": "Robotics",
        "published_at": "2026-10-10T10:00:00Z",
        "posts": {"bluesky": {"uri": "at://did:plc:x/app.bsky.feed.post/1"}},
    }
    state = sanitize_and_migrate_state({"published_posts": [legacy_entry]})
    assert len(state["published_posts"]) == 1
    assert "source" not in state["published_posts"][0]
    assert "source_id" not in state["published_posts"][0]
    assert "category" not in state["published_posts"][0]

    # Appending a new post to legacy state preserves legacy entry and enforces cap
    append_published_post(state, url="https://example.com/new", title="New Story")
    assert len(state["published_posts"]) == 2
    assert state["published_posts"][0]["url"] == "https://example.com/legacy"


# --- Required Coverage 3: Roundups classify correctly ---
def test_roundups_classify_correctly():
    assert classify_content_type({"kind": "roundup"}) == "Roundup"
    assert classify_content_type({"source_id": "weekly_roundup"}) == "Roundup"
    assert classify_content_type({"url": "generated:roundup:2026-W42"}) == "Roundup"
    assert get_display_category({"kind": "roundup"}) == "Roundup"


# --- Required Coverage 4: GitHub URLs classify as repositories ---
def test_github_urls_classify_as_repositories():
    entry = {"url": "https://github.com/facebookresearch/llama"}
    assert classify_content_type(entry) == "Repository"
    assert get_display_category(entry) == "Open Source"


# --- Required Coverage 5: Hugging Face URLs classify as models ---
def test_huggingface_urls_classify_as_models():
    entry = {"url": "https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct"}
    assert classify_content_type(entry) == "Model"
    assert get_display_category(entry) == "Models"


def test_content_type_classification_uses_hostname_not_url_text():
    assert classify_content_type({"url": "https://news.example/story?source=github.com"}) == "News"
    assert classify_content_type({"url": "https://github.com.evil.example/repo"}) == "News"
    assert classify_content_type({"url": "https://api.github.com/repos/org/repo"}) == "Repository"


# --- Required Coverage 6: Human-readable timestamp output ---
def test_human_readable_timestamp_output():
    iso_ts = "2026-10-17T23:14:00Z"
    formatted = format_human_date(iso_ts)
    assert formatted == "17 Oct 2026 · 23:14 UTC"
    assert format_human_date("invalid-date") == "Unknown date"
    assert format_human_date(None) == "Unknown date"


# --- Required Coverage 7: Source-domain normalization ---
def test_source_domain_normalization():
    assert extract_display_domain("https://www.technologyreview.com/article/1") == "technologyreview.com"
    assert extract_display_domain("http://github.com/trending") == "github.com"
    assert extract_display_domain("https://sub.domain.co.uk:8080/path") == "sub.domain.co.uk"
    assert extract_display_domain("invalid-url") == "Unknown source"
    assert extract_display_domain("") == "Unknown source"


def test_independent_support_domains_are_public_distinct_and_unique():
    entry = {
        "url": "https://news.example/story",
        "supporting_links": [
            "https://news.example/follow-up",
            "https://support.example/report",
            "https://support.example/second",
            "http://127.0.0.1/private",
            "not-a-url",
        ],
    }
    assert get_independent_support_domains(entry) == ["support.example"]


# --- Required Coverage 8: Trust-stat calculations ---
def test_trust_stat_calculations():
    fixed_now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    entries = [
        {
            "url": "https://techcrunch.com/story1",
            "published_at": "2026-10-17T12:00:00Z",
            "supporting_links": ["https://sup1.com"],
            "posts": {"bluesky": {"uri": "at://1", "receipt_uri": "at://rec1"}},
        },
        {
            "url": "https://github.com/repo1",
            "published_at": "2026-10-16T12:00:00Z",
            "supporting_links": [],
            "posts": {"bluesky": {"uri": "at://2"}},
        },
    ]
    stats = compute_trust_stats(entries, now=fixed_now)
    assert stats["total_posts"] == 2
    assert stats["posts_last_7d"] == 2
    assert stats["unique_sources"] == 2
    assert stats["corroborated_posts"] == 1
    assert stats["eligible_corroboration_count"] == 2
    assert stats["corroboration_rate"] == 50.0
    assert stats["source_receipts"] == 1
    assert stats["eligible_receipt_count"] == 1
    assert stats["receipt_coverage"] == 100.0


# --- Required Coverage 9: Roundups excluded from corroboration denominator ---
def test_roundups_excluded_from_corroboration_denominator():
    fixed_now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    entries = [
        # Normal post: not corroborated
        {
            "url": "https://example.com/p1",
            "published_at": "2026-10-17T12:00:00Z",
            "supporting_links": [],
        },
        # Normal post: corroborated
        {
            "url": "https://example.com/p2",
            "published_at": "2026-10-17T12:00:00Z",
            "supporting_links": ["https://sup1.com"],
        },
        # Roundup post: has 5 links, but must be excluded from rate calculation
        {
            "url": "generated:roundup:2026-W42",
            "published_at": "2026-10-17T12:00:00Z",
            "kind": "roundup",
            "supporting_links": ["https://s1.com", "https://s2.com"],
        },
    ]
    stats = compute_trust_stats(entries, now=fixed_now)
    # Total posts is 3 (roundup included in total archive count)
    assert stats["total_posts"] == 3
    # Corroborated posts = 1, eligible denominator = 2 (roundup excluded), rate = 50.0%
    assert stats["corroborated_posts"] == 1
    assert stats["corroboration_rate"] == 50.0


# --- Required Coverage 10: Receipt-coverage calculation ---
def test_receipt_coverage_calculation():
    entries = [
        # Post with Bluesky post and corroboration, but no receipt
        {
            "url": "https://example.com/1",
            "supporting_links": ["https://sup.com"],
            "posts": {"bluesky": {"uri": "at://b1"}},
        },
        # Post with Bluesky post, corroboration, AND receipt
        {
            "url": "https://example.com/2",
            "supporting_links": ["https://sup.com"],
            "posts": {"bluesky": {"uri": "at://b2", "receipt_uri": "at://rec2"}},
        },
    ]
    stats = compute_trust_stats(entries)
    assert stats["source_receipts"] == 1
    # 2 eligible posts on bluesky with corroboration, 1 has receipt -> 50.0%
    assert stats["receipt_coverage"] == 50.0


# --- Required Coverage 11: Cross-platform count ---
def test_cross_platform_count():
    entries = [
        # 1 platform: only bluesky
        {
            "url": "https://example.com/1",
            "posts": {"bluesky": {"uri": "at://b1"}},
        },
        # 2 platforms: bluesky and mastodon
        {
            "url": "https://example.com/2",
            "posts": {"bluesky": {"uri": "at://b2"}, "mastodon": {"id": "123"}},
        },
        # 3 platforms: bluesky, mastodon, and threads
        {
            "url": "https://example.com/3",
            "posts": {"bluesky": {"uri": "at://b3"}, "mastodon": {"id": "456"}, "threads": {"id": "789"}},
        },
    ]
    stats = compute_trust_stats(entries)
    assert stats["cross_platform_posts"] == 2


# --- Required Coverage 12: HTML escaping for every new field ---
def test_html_escaping_for_every_new_field():
    entries = [
        {
            "url": "https://example.com/safe",
            "title": "Title with <img src=x onerror=alert(1)>",
            "source": "Injected <script>evil()</script>",
            "category": "Cat <b onmouseover=alert(2)>",
            "topic": "Topic <script>",
            "supporting_sources": ["<script>source1</script>", "Safe Source"],
            "published_at": "2026-10-17T12:00:00Z",
        }
    ]
    html_out = build_html(entries)
    assert "<script>evil()</script>" not in html_out
    assert "&lt;script&gt;evil()&lt;/script&gt;" in html_out
    assert "<img src=x onerror=alert(1)>" not in html_out
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_out
    assert "<script>source1</script>" not in html_out


def test_search_index_escapes_title_exactly_once():
    html_out = build_html([{"url": "https://example.com", "title": "AI's next step"}])
    assert "ai&#x27;s next step" in html_out
    assert "ai&amp;#x27;s next step" not in html_out


def test_roundup_does_not_gain_corroboration_sort_score():
    html_out = build_html([{
        "url": "generated:roundup:2026-W42",
        "kind": "roundup",
        "supporting_links": ["https://one.example", "https://two.example"],
    }])
    assert 'data-corroborated="0"' in html_out


# --- Required Coverage 13: Search/filter controls and accessible labels exist ---
def test_search_filter_controls_and_accessible_labels():
    html_out = build_html([])
    assert 'id="search-input"' in html_out
    assert '<label for="search-input"' in html_out
    assert 'id="filter-type"' in html_out
    assert '<label for="filter-type"' in html_out
    assert 'id="filter-trust"' in html_out
    assert '<label for="filter-trust"' in html_out
    assert 'id="sort-select"' in html_out
    assert '<label for="sort-select"' in html_out


def test_editorial_navigation_uses_real_destinations():
    html_out = build_html([])
    assert '<a href="#stories" class="nav-link">Stories</a>' in html_out
    assert '<a href="#trust-dashboard" class="nav-link">Source Trust</a>' in html_out
    assert '<a href="feed.xml" class="nav-link">RSS</a>' in html_out
    assert 'href="#"' not in html_out


def test_theme_toggle_is_accessible_persistent_and_no_js_safe():
    html_out = build_html([])
    assert 'id="theme-toggle"' in html_out
    assert 'aria-pressed="false"' in html_out
    assert 'aria-label="Switch to dark theme"' in html_out
    assert 'hidden>Dark mode</button>' in html_out
    assert "localStorage.getItem('blubot-theme')" in html_out
    assert "localStorage.setItem('blubot-theme', theme)" in html_out
    assert "matchMedia('(prefers-color-scheme: dark)')" in html_out
    assert "colorPreference.addEventListener('change'" in html_out
    assert 'root.style.colorScheme = theme;' in html_out
    assert ':root[data-theme="dark"]' in html_out
    assert '@media (prefers-color-scheme: dark)' in html_out


def test_zero_eligible_kpis_are_not_rendered_as_failure_percentages():
    html_out = build_html([])
    assert html_out.count('<div class="stat-value">Not yet measured</div>') == 2
    assert "No eligible non-roundup stories in the archive" in html_out
    assert "No corroborated Bluesky stories eligible for receipts" in html_out
    assert '<div class="stat-value">0.0%</div>' not in html_out


# --- Required Coverage 14: No raw ISO timestamps appear in rendered cards ---
def test_no_raw_iso_timestamps_in_rendered_cards():
    entries = [
        {
            "url": "https://example.com/time-test",
            "title": "Timestamp Check",
            "published_at": "2026-10-17T14:32:10Z",
        }
    ]
    html_out = build_html(entries)
    # The visible card text should have human format, datetime attribute may hold ISO safely
    assert "17 Oct 2026 · 14:32 UTC" in html_out
    assert 'class="card-date" datetime="2026-10-17T14:32:10Z">17 Oct 2026 · 14:32 UTC</time>' in html_out


# --- Required Coverage 15: No generated:* value is rendered as a link ---
def test_no_generated_value_rendered_as_link():
    entries = [
        {
            "url": "generated:roundup:2026-W42",
            "title": "Roundup Week 42",
            "kind": "roundup",
            "published_at": "2026-10-17T18:00:00Z",
            "posts": {"bluesky": {"uri": "at://did:plc:x/app.bsky.feed.post/rkey123"}},
        }
    ]
    html_out = build_html(entries)
    assert '<a href="generated:roundup:2026-W42"' not in html_out
    # Links to the social post instead
    assert "https://bsky.app/profile/did:plc:x/post/rkey123" in html_out


# --- Required Coverage 16: Metrics render when supplied ---
def test_metrics_render_when_supplied():
    entries = [
        {
            "url": "https://example.com/metric-story",
            "title": "Popular Post",
            "published_at": "2026-10-17T12:00:00Z",
            "posts": {"bluesky": {"uri": "at://did:plc:user/app.bsky.feed.post/p1"}},
        }
    ]
    metrics = {
        "at://did:plc:user/app.bsky.feed.post/p1": {
            "likes": 42,
            "reposts": 12,
            "replies": 5,
            "quotes": 2,
        }
    }
    html_out = build_html(entries, metrics=metrics)
    assert "42 likes" in html_out
    assert "12 reposts" in html_out
    assert "5 replies" in html_out
    assert "7-Day Engagement" in html_out
    assert '<option value="engagement">Most engaged (last 7 days)</option>' in html_out


# --- Required Coverage 17: Metrics absence does not break HTML generation ---
def test_metrics_absence_does_not_break_html_generation():
    entries = [
        {
            "url": "https://example.com/no-metrics",
            "title": "No Metrics Post",
            "published_at": "2026-10-17T12:00:00Z",
            "posts": {"bluesky": {"uri": "at://did:plc:user/app.bsky.feed.post/p2"}},
        }
    ]
    html_out = build_html(entries, metrics=None)
    assert "No Metrics Post" in html_out
    assert "7-Day Engagement" not in html_out
    assert '<option value="engagement">Most engaged (last 7 days)</option>' not in html_out


def test_engagement_sort_limits_results_to_recent_stories():
    entries = [
        {
            "url": "https://example.com/recent",
            "title": "Recent",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "posts": {"bluesky": {"uri": "at://recent"}},
        },
        {
            "url": "https://example.com/old",
            "title": "Old",
            "published_at": "2020-01-01T00:00:00Z",
            "posts": {"bluesky": {"uri": "at://old"}},
        },
    ]
    html_out = build_html(entries, metrics={"at://recent": {"likes": 1, "reposts": 0, "replies": 0}})
    assert 'data-recent="true"' in html_out
    assert 'data-recent="false"' in html_out
    assert "const matchesEngagementWindow = (sortVal !== 'engagement') || isRecent;" in html_out


def test_metrics_fetch_is_limited_to_recent_entries():
    recent = {"url": "https://example.com/recent"}
    with (
        patch("src.engagement.recent_entries", return_value=[recent]) as mock_recent,
        patch("src.engagement.fetch_bluesky_metrics", new_callable=AsyncMock, return_value={}) as mock_fetch,
    ):
        assert fetch_metrics_best_effort([recent, {"url": "https://example.com/old"}]) == {}
    mock_recent.assert_called_once_with({"published_posts": [recent, {"url": "https://example.com/old"}]}, days=7)
    assert mock_fetch.await_args.args[1] == [recent]


# --- Required Coverage 18: RSS remains valid and capped ---
def test_rss_remains_valid_and_capped():
    entries = []
    for i in range(65):
        entries.append({
            "url": f"https://example.com/item{i}",
            "title": f"Item {i}",
            "published_at": f"2026-10-10T12:{i % 60:02d}:00Z",
            "category": "open_source",
            "source": "GitHub",
            "supporting_links": ["https://sup.com"],
            "posts": {"bluesky": {"uri": f"at://did:plc:x/app.bsky.feed.post/{i}"}},
        })
    entries.append({
        "url": "https://example.com/bad-date",
        "title": "Bad Date",
        "published_at": "not-a-date",
    })

    rss_xml = build_rss(entries)
    root = ET.fromstring(rss_xml)
    assert root.tag == "rss"
    channel = root.find("channel")
    items = channel.findall("item")
    assert len(items) == 50

    first_item = items[0]
    assert first_item.find("guid") is not None
    assert first_item.find("guid").attrib.get("isPermaLink") == "false"
    assert first_item.find("pubDate") is not None
    assert email.utils.parsedate_to_datetime(first_item.find("pubDate").text) is not None
    desc_text = first_item.find("description").text
    assert "Topic: Open Source" in desc_text
    assert "Lead Source: GitHub" in desc_text
    assert "Corroboration: 1 sources" in desc_text


# --- Required Coverage 19: Gist loading remains fail-closed ---
def test_gist_loading_remains_fail_closed(tmp_path):
    from src.settings import settings
    object.__setattr__(settings, "gist_id", None)
    object.__setattr__(settings, "gist_token", None)

    out_dir = tmp_path / "site_out"
    with patch("src.logger.SafeLogger.error") as mock_log:
        from scripts import build_archive
        with pytest.raises(SystemExit) as exc_info:
            build_archive.main(argv=["--out", str(out_dir)])
        assert exc_info.value.code == 1
        mock_log.assert_called_once()
        assert "Archive build failed-closed" in mock_log.call_args[0][0]

    assert not out_dir.exists()


# --- Required Coverage 20: Dashboard output contains no external asset dependencies ---
def test_dashboard_no_external_asset_dependencies():
    html_out = build_html([])
    # No external css, js, fonts, or images
    assert '<link rel="stylesheet"' not in html_out
    assert '<script src=' not in html_out
    assert 'fonts.googleapis.com' not in html_out
    assert 'cdn.jsdelivr.net' not in html_out


def test_public_url_validation_rejects_private_ips_and_non_http_values():
    assert is_valid_public_http_url("https://github.com/org/repo") is True
    assert is_valid_public_http_url("http://8.8.8.8/test") is True
    assert is_valid_public_http_url("http://127.0.0.1/test") is False
    assert is_valid_public_http_url("http://192.168.1.1/test") is False
    assert is_valid_public_http_url("http://10.0.0.1/test") is False
    assert is_valid_public_http_url("generated:roundup:2026-W42") is False
    assert is_valid_public_http_url("at://did:plc:123/app.bsky.feed.post/abc") is False
    assert is_valid_public_http_url(None) is False


def test_compute_guid_is_stable():
    with_uri = {
        "url": "https://example.com/test",
        "published_at": "2026-10-17T12:00:00Z",
        "posts": {"bluesky": {"uri": "at://did:plc:x/app.bsky.feed.post/123"}},
    }
    without_uri = {"url": "https://example.com/test", "published_at": "2026-10-17T12:00:00Z"}
    assert compute_guid(with_uri) == "at://did:plc:x/app.bsky.feed.post/123"
    assert compute_guid(without_uri) == compute_guid(without_uri)
    assert len(compute_guid(without_uri)) == 64


# --- Required Coverage 21: The page contains a skip link and visible focus styles ---
def test_page_contains_skip_link_and_focus_styles():
    html_out = build_html([])
    assert '<a href="#stories" class="skip-link">Skip to stories</a>' in html_out
    assert ':focus-visible' in html_out
    assert '--focus: #5b3fd3' in html_out
    assert '@media (prefers-reduced-motion: reduce)' in html_out


# --- Required Coverage 22: Search-result status uses aria-live ---
def test_search_result_status_uses_aria_live():
    html_out = build_html([])
    assert 'aria-live="polite"' in html_out
    assert 'id="results-count"' in html_out


# --- Required Coverage 23: SVG icons have accessible names or are correctly decorative ---
def test_svg_icons_accessibility():
    html_out = build_html([
        {
            "url": "https://example.com/story",
            "title": "Story with Icons",
            "published_at": "2026-10-17T12:00:00Z",
            "supporting_links": ["https://sup.com"],
            "posts": {"bluesky": {"uri": "at://b1", "receipt_uri": "at://r1"}},
        }
    ])
    assert 'aria-hidden="true"' in html_out
    assert '<span class="sr-only">' in html_out
