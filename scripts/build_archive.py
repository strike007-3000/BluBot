#!/usr/bin/env python3
"""Build static HTML archive and RSS 2.0 feed from published_posts ledger in GitHub Gist."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import email.utils
import hashlib
import html
import ipaddress
import os
import sys
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

# Ensure imports from src work
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.logger import SafeLogger
from src.settings import settings
from src.utils import _is_public_ip, _load_gist_state_with_status, sanitize_and_migrate_state

ARCHIVE_CAP_NOTICE = "Archive displays up to the last 500 published stories from the durable ledger."
FEED_MAX_ITEMS = 50

CATEGORY_DISPLAY_MAP = {
    "open_source": "Open Source",
    "model_release": "Models",
    "models": "Models",
    "research": "Research",
    "research_lab": "Research",
    "enterprise": "Enterprise",
    "policy": "Policy",
    "roundup": "Roundup",
    "general": "General",
}


def at_uri_to_bsky_url(uri: Optional[str]) -> Optional[str]:
    """Convert at://did:plc:xxx/app.bsky.feed.post/rkey to https://bsky.app/profile/.../post/..."""
    if not isinstance(uri, str) or not uri.startswith("at://"):
        return None
    parts = uri[5:].split("/")
    if len(parts) >= 3 and parts[1] == "app.bsky.feed.post" and parts[0] and parts[2]:
        return f"https://bsky.app/profile/{parts[0]}/post/{parts[2]}"
    return None


def is_valid_public_http_url(url: Optional[str]) -> bool:
    """Return True if url is a valid public http(s) URL with hostname (rejects generated: IDs, at://, local IPs)."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            return _is_public_ip(str(ip))
        except ValueError:
            return True
    except Exception:
        return False


def compute_guid(entry: dict) -> str:
    """Stable GUID: Bluesky AT URI or sha256(url + published_at)."""
    bsky_uri = ((entry.get("posts") or {}).get("bluesky") or {}).get("uri")
    if isinstance(bsky_uri, str) and bsky_uri.startswith("at://"):
        return bsky_uri
    key = f"{entry.get('url', '')}_{entry.get('published_at', '')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_date_safe(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parse an ISO datetime string into an aware UTC datetime object."""
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def format_human_date(date_str: Optional[str]) -> str:
    """Format ISO timestamp as '17 Oct 2026 · 23:14 UTC', falling back safely."""
    dt = parse_date_safe(date_str)
    if not dt:
        return "Unknown date"
    return f"{dt.day} {dt.strftime('%b %Y')} · {dt.strftime('%H:%M')} UTC"


def parse_rfc822_date(date_str: Optional[str]) -> Optional[str]:
    """Convert ISO datetime string to RFC 822 format."""
    dt = parse_date_safe(date_str)
    if not dt:
        return None
    try:
        return email.utils.format_datetime(dt)
    except Exception:
        return None


def extract_display_domain(url: Optional[str]) -> str:
    """Extract a clean, displayable hostname domain from URL."""
    if not isinstance(url, str) or not url.strip():
        return "Unknown source"
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc if netloc else "Unknown source"
    except Exception:
        return "Unknown source"


def _hostname_matches(hostname: str, expected: str) -> bool:
    """Match an exact hostname or its subdomains, never URL text or lookalikes."""
    return hostname == expected or hostname.endswith(f".{expected}")


def get_independent_support_domains(entry: dict) -> List[str]:
    """Return unique, public supporting domains that differ from the lead source."""
    lead_domain = extract_display_domain(entry.get("url")).lower()
    if lead_domain in ("unknown source", "blubot"):
        return []

    domains = []
    seen = set()
    links = entry.get("supporting_links")
    if not isinstance(links, list):
        return domains

    for link in links:
        if not is_valid_public_http_url(link):
            continue
        domain = extract_display_domain(link).lower()
        if domain in ("unknown source", "blubot", lead_domain) or domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains


def classify_content_type(entry: dict) -> str:
    """
    Classify entry into: 'Roundup', 'Repository', 'Model', 'Follow-up', or 'News'.
    Historical fallbacks:
    - kind == 'roundup' classifies as Roundup
    - github.com URLs classify as Repository
    - huggingface.co URLs classify as Model
    """
    kind = str(entry.get("kind") or "").lower()
    url = str(entry.get("url") or "")
    source_id = str(entry.get("source_id") or "").lower()
    hostname = extract_display_domain(url).lower()

    if kind == "roundup" or source_id == "weekly_roundup" or url.startswith("generated:roundup"):
        return "Roundup"
    if kind == "follow_up" or kind == "followup":
        return "Follow-up"
    if _hostname_matches(hostname, "github.com") or source_id == "github_rising":
        return "Repository"
    if _hostname_matches(hostname, "huggingface.co") or source_id == "hf_trending":
        return "Model"
    return "News"


def get_display_source_and_domain(entry: dict) -> Tuple[str, str]:
    """Return (display_source_name, display_domain) with robust historical fallback."""
    url = entry.get("url") or ""
    domain = extract_display_domain(url)
    kind = str(entry.get("kind") or "").lower()

    source = entry.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip(), domain

    # Fallbacks for roundups and URLs
    if kind == "roundup" or str(entry.get("source_id")) == "weekly_roundup":
        return "BluBot", "blubot"
    if domain != "Unknown source":
        return domain, domain
    return "BluBot", "blubot"


def get_display_category(entry: dict) -> str:
    """Return normalized display category for entry."""
    raw_cat = entry.get("category")
    if isinstance(raw_cat, str) and raw_cat.strip():
        cat_key = raw_cat.strip().lower()
        return CATEGORY_DISPLAY_MAP.get(cat_key, raw_cat.strip().replace("_", " ").title())

    # Fallbacks for historical entries
    c_type = classify_content_type(entry)
    if c_type == "Roundup":
        return "Roundup"
    if c_type == "Repository":
        return "Open Source"
    if c_type == "Model":
        return "Models"

    topic = entry.get("topic")
    if isinstance(topic, str) and topic.strip() and topic.strip().lower() != "general":
        return topic.strip()
    return "General"


def compute_trust_stats(entries: List[dict], now: Optional[datetime] = None) -> dict:
    """
    Compute trust and archive statistics.
    Metric definitions:
    - total_posts: total archive entries
    - posts_last_7d: posts published within the last 7 days
    - unique_sources: count of distinct normalized lead-source domains (excluding unknown/internal)
    - corroborated_posts: posts with at least one public supporting domain distinct from the lead (excluding roundups)
    - corroboration_rate: corroborated_posts / eligible_posts * 100 (excluding roundups from denominator)
    - source_receipts: posts eligible for a receipt that have posts.bluesky.receipt_uri
    - receipt_coverage: source_receipts / eligible_posts * 100
    - cross_platform_posts: successful post IDs recorded for at least two platforms
    - top_sources: top 5 lead-source domains with count and percentage
    - top_categories: top categories with count and percentage
    """
    ref_time = now or datetime.now(timezone.utc)
    cutoff_7d = ref_time - timedelta(days=7)

    total_posts = len(entries)
    posts_last_7d = 0
    unique_domains = set()
    domain_counts = Counter()
    category_counts = Counter()

    corroborated_posts = 0
    source_receipts = 0
    cross_platform_posts = 0
    eligible_corroboration_count = 0
    eligible_receipt_count = 0

    for e in entries:
        dt = parse_date_safe(e.get("published_at"))
        if dt and dt >= cutoff_7d:
            posts_last_7d += 1

        c_type = classify_content_type(e)
        cat = get_display_category(e)
        category_counts[cat] += 1

        _, domain = get_display_source_and_domain(e)
        norm_domain = domain.lower()
        if norm_domain and norm_domain not in ("unknown source", "blubot"):
            unique_domains.add(norm_domain)
            domain_counts[norm_domain] += 1
        elif norm_domain == "blubot":
            domain_counts["blubot"] += 1

        # Corroboration logic: exclude weekly roundups from corroboration rate
        is_roundup = (c_type == "Roundup")
        has_corroboration = bool(get_independent_support_domains(e))

        if not is_roundup:
            eligible_corroboration_count += 1
            if has_corroboration:
                corroborated_posts += 1

        # Receipt logic: eligible if Bluesky post exists (or corroborated story on Bluesky)
        bsky_info = (e.get("posts") or {}).get("bluesky") or {}
        has_receipt = bool(bsky_info.get("receipt_uri"))
        # An entry is eligible for a receipt if it was posted to Bluesky and has corroborating sources
        if not is_roundup and has_corroboration and bool(bsky_info.get("uri")):
            eligible_receipt_count += 1
            if has_receipt:
                source_receipts += 1

        # Cross-platform check: successful post IDs recorded for >= 2 platforms
        posts_map = e.get("posts")
        if isinstance(posts_map, dict):
            plat_count = 0
            for plat, data in posts_map.items():
                if isinstance(data, dict) and (data.get("id") or data.get("uri")):
                    plat_count += 1
            if plat_count >= 2:
                cross_platform_posts += 1

    corroboration_rate = (
        round((corroborated_posts / eligible_corroboration_count) * 100, 1)
        if eligible_corroboration_count > 0 else 0.0
    )
    receipt_coverage = (
        round((source_receipts / eligible_receipt_count) * 100, 1)
        if eligible_receipt_count > 0 else 0.0
    )

    # Calculate top 5 sources + other
    total_domain_tracked = sum(domain_counts.values())
    top_5_sources_raw = domain_counts.most_common(5)
    top_sources = []
    top_domain_sum = 0
    for dom, cnt in top_5_sources_raw:
        pct = round((cnt / total_domain_tracked * 100), 1) if total_domain_tracked > 0 else 0.0
        top_sources.append({"domain": dom, "count": cnt, "percentage": pct})
        top_domain_sum += cnt

    other_cnt = total_domain_tracked - top_domain_sum
    if other_cnt > 0:
        other_pct = round((other_cnt / total_domain_tracked * 100), 1) if total_domain_tracked > 0 else 0.0
        top_sources.append({"domain": "Other", "count": other_cnt, "percentage": other_pct})

    # Top categories
    top_categories = []
    for cat_name, cnt in category_counts.most_common():
        pct = round((cnt / total_posts * 100), 1) if total_posts > 0 else 0.0
        top_categories.append({"category": cat_name, "count": cnt, "percentage": pct})

    return {
        "total_posts": total_posts,
        "posts_last_7d": posts_last_7d,
        "unique_sources": len(unique_domains),
        "corroborated_posts": corroborated_posts,
        "corroboration_rate": corroboration_rate,
        "source_receipts": source_receipts,
        "receipt_coverage": receipt_coverage,
        "cross_platform_posts": cross_platform_posts,
        "top_sources": top_sources,
        "top_categories": top_categories,
    }


def fetch_metrics_best_effort(entries: List[dict]) -> Dict[str, Dict[str, int]]:
    """Safely fetch public Bluesky metrics; return empty dict on any failure."""
    try:
        import httpx
        from src.engagement import fetch_bluesky_metrics, recent_entries

        recent = recent_entries({"published_posts": entries}, days=7)

        async def _fetch():
            async with httpx.AsyncClient() as client:
                return await fetch_bluesky_metrics(client, recent)

        return asyncio.run(_fetch())
    except Exception as exc:
        SafeLogger.warn(f"Best-effort engagement metrics skipped: {exc}")
        return {}


def render_svg_icon(name: str) -> str:
    """Return inline SVG icon markup with accessibility attributes."""
    if name == "logo":
        return (
            '<svg class="icon icon-logo" width="28" height="28" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><rect x="3" y="11" width="18" height="10" rx="2"></rect>'
            '<circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path>'
            '<line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line></svg>'
        )
    elif name == "external":
        return (
            '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>'
            '<polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>'
        )
    elif name == "check":
        return (
            '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>'
        )
    elif name == "receipt":
        return (
            '<svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16l3-2 3 2 3-2 3 2 3-2 3 2V8z"></path>'
            '<polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line>'
            '<line x1="16" y1="17" x2="8" y2="17"></line></svg>'
        )
    return ""


def build_html(entries: list, metrics: Optional[Dict[str, Dict[str, int]]] = None) -> str:
    """Build single-page responsive static HTML editorial Source Trust Dashboard."""
    if metrics is None:
        metrics = {}

    sorted_entries = sorted(entries, key=lambda e: str(e.get("published_at", "")), reverse=True)
    stats = compute_trust_stats(sorted_entries)

    # Calculate 7-day engagement total if metrics exist
    now_utc = datetime.now(timezone.utc)
    cutoff_7d = now_utc - timedelta(days=7)
    eng_7d_total = 0
    has_metrics = bool(metrics and any(m for m in metrics.values()))
    if has_metrics:
        for e in sorted_entries:
            dt = parse_date_safe(e.get("published_at"))
            if dt and dt >= cutoff_7d:
                bsky_uri = ((e.get("posts") or {}).get("bluesky") or {}).get("uri")
                m = metrics.get(bsky_uri) if bsky_uri else None
                if m:
                    eng_7d_total += (m.get("likes", 0) + m.get("reposts", 0) + m.get("replies", 0))

    # Metric Cards
    engagement_card_html = ""
    if has_metrics:
        engagement_card_html = f"""
        <div class="stat-card">
          <div class="stat-label">7-Day Engagement</div>
          <div class="stat-value">{eng_7d_total:,}</div>
          <div class="stat-desc">Likes, reposts, and replies across recent Bluesky reports</div>
        </div>"""

    # Top Sources CSS bars
    source_bars_html = []
    for src in stats["top_sources"]:
        dom_esc = html.escape(src["domain"])
        pct = src["percentage"]
        cnt = src["count"]
        source_bars_html.append(f"""
        <div class="bar-row">
          <span class="bar-label">{dom_esc}</span>
          <div class="bar-track" role="progressbar" aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100" aria-label="{dom_esc} source percentage">
            <div class="bar-fill" style="width: {pct}%"></div>
          </div>
          <span class="bar-value">{pct}% <span class="bar-count">({cnt})</span></span>
        </div>""")
    sources_distribution_html = "\n".join(source_bars_html) if source_bars_html else "<p class='empty-text'>No source data recorded yet.</p>"

    # Coverage distribution
    category_chips_html = []
    for cat in stats["top_categories"]:
        cat_esc = html.escape(cat["category"])
        pct = cat["percentage"]
        cnt = cat["count"]
        category_chips_html.append(f"""
        <div class="category-stat">
          <span class="cat-name">{cat_esc}</span>
          <span class="cat-numbers">{cnt} <span class="cat-pct">({pct}%)</span></span>
        </div>""")
    coverage_distribution_html = "\n".join(category_chips_html) if category_chips_html else "<p class='empty-text'>No category data recorded yet.</p>"

    # Articles
    items_html = []
    for e in sorted_entries:
        raw_title = str(e.get("title") or "Untitled")
        title = html.escape(raw_title)
        raw_url = str(e.get("url") or "")
        pub_at_iso = str(e.get("published_at") or "")
        human_date = html.escape(format_human_date(pub_at_iso))

        content_type = classify_content_type(e)
        display_category = get_display_category(e)
        source_name, display_domain = get_display_source_and_domain(e)

        support_domains = get_independent_support_domains(e)
        num_corroborating = len(support_domains)
        is_corroborated = (num_corroborating > 0)
        is_roundup = (content_type == "Roundup")

        bsky_post = (e.get("posts") or {}).get("bluesky") or {}
        bsky_uri = bsky_post.get("uri")
        receipt_uri = bsky_post.get("receipt_uri")
        has_receipt = bool(receipt_uri) and is_corroborated and not is_roundup

        # Engagement metrics for this card
        post_metrics = metrics.get(bsky_uri) if bsky_uri else None
        eng_score = 0
        metrics_html = ""
        if post_metrics:
            likes = post_metrics.get("likes", 0)
            reposts = post_metrics.get("reposts", 0)
            replies = post_metrics.get("replies", 0)
            eng_score = likes + reposts + replies
            metrics_html = f"""
            <div class="card-metrics" aria-label="Bluesky engagement">
              <span title="{likes} likes">{likes} likes</span> ·
              <span title="{reposts} reposts">{reposts} reposts</span> ·
              <span title="{replies} replies">{replies} replies</span>
            </div>"""

        # Trust filter tag
        if has_receipt:
            trust_type = "receipt"
            trust_badge = f'<span class="badge badge-trust badge-receipt">{render_svg_icon("receipt")} Source Receipt</span>'
        elif is_corroborated and not is_roundup:
            trust_type = "corroborated"
            trust_badge = f'<span class="badge badge-trust badge-corroborated">{render_svg_icon("check")} Corroborated</span>'
        elif is_roundup:
            trust_type = "roundup"
            trust_badge = f'<span class="badge badge-trust badge-roundup">Curated Digest</span>'
        else:
            trust_type = "single-source"
            trust_badge = f'<span class="badge badge-trust badge-single">Single Source</span>'

        content_type_attr = content_type.lower()
        if content_type_attr == "repository":
            content_type_attr = "repositories"
        elif content_type_attr == "model":
            content_type_attr = "models"
        elif content_type_attr == "roundup":
            content_type_attr = "roundups"
        elif content_type_attr == "follow-up":
            content_type_attr = "follow-ups"

        # Content type badge
        content_badge = f'<span class="badge badge-type badge-type-{content_type_attr}">{html.escape(content_type)}</span>'

        # Supporting text
        if is_roundup:
            support_desc = "Weekly digest synthesized from community breakthroughs"
        elif is_corroborated:
            num_sup = num_corroborating
            sup_word = "source" if num_sup == 1 else "sources"
            sources_str = ", ".join(support_domains[:3])
            support_desc = f"Supported by {num_sup} additional {sup_word} ({sources_str})"
        else:
            support_desc = "Single lead report"

        # Action links
        actions = []
        if is_valid_public_http_url(raw_url):
            actions.append(
                f'<a href="{html.escape(raw_url)}" target="_blank" rel="noopener noreferrer" class="action-link">'
                f'Read source <span class="sr-only">for {title}</span>{render_svg_icon("external")}</a>'
            )

        bsky_url = at_uri_to_bsky_url(bsky_uri)
        if bsky_url:
            actions.append(
                f'<a href="{html.escape(bsky_url)}" target="_blank" rel="noopener noreferrer" class="action-link">'
                f'View Bluesky <span class="sr-only">post for {title}</span>{render_svg_icon("external")}</a>'
            )

        if receipt_uri:
            receipt_url = at_uri_to_bsky_url(receipt_uri)
            if receipt_url:
                actions.append(
                    f'<a href="{html.escape(receipt_url)}" target="_blank" rel="noopener noreferrer" class="action-link action-receipt">'
                    f'View Receipt <span class="sr-only">for {title}</span>{render_svg_icon("receipt")}</a>'
                )

        actions_html = ' <span class="link-sep" aria-hidden="true">·</span> '.join(actions) if actions else ""

        # Search index content
        search_terms = f"{raw_title} {source_name} {display_domain} {display_category} {content_type}".lower()
        corroboration_sort_score = 0 if is_roundup else num_corroborating

        card_html = f"""
        <article class="card" data-title="{title}" data-source="{html.escape(source_name)}" data-domain="{html.escape(display_domain)}" data-category="{html.escape(display_category)}" data-content-type="{content_type_attr}" data-trust="{trust_type}" data-published="{html.escape(pub_at_iso)}" data-corroborated="{corroboration_sort_score}" data-engagement="{eng_score}" data-search="{html.escape(search_terms)}">
          <header class="card-header">
            <div class="card-badges">
              {content_badge}
              {trust_badge}
            </div>
            <time class="card-date" datetime="{html.escape(pub_at_iso)}">{human_date}</time>
          </header>
          <h2 class="card-title">{title}</h2>
          <div class="card-meta">
            <span class="source-info">{html.escape(source_name)}</span>
            <span class="meta-dot" aria-hidden="true">·</span>
            <span class="topic">{html.escape(display_category)}</span>
          </div>
          <div class="card-support">{html.escape(support_desc)}</div>
          {metrics_html}
          <div class="card-actions">
            {actions_html}
          </div>
        </article>"""
        items_html.append(card_html)

    rendered_items = "\n".join(items_html) if items_html else "<div class='empty-state'><p>No published stories yet.</p></div>"

    most_engaged_option = '<option value="engagement">Most engaged</option>' if has_metrics else ''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="BluBot Signal Archive: AI developments and verified breakthrough stories checked against multiple sources.">
  <title>BluBot Signal Archive &amp; Source Trust Dashboard</title>
  <style>
    :root {{
      --bg: #07111f;
      --surface: #0e1a2b;
      --surface-raised: #132238;
      --border: #24344a;
      --text: #f5f7fa;
      --muted: #94a3b8;
      --signal: #38bdf8;
      --trusted: #34d399;
      --warning: #fbbf24;
      --focus: #7dd3fc;
      --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    *, *::before, *::after {{
      box-sizing: border-box;
    }}

    body {{
      font-family: var(--font-stack);
      font-size: 16px;
      line-height: 1.5;
      background-color: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 0;
      min-height: 100vh;
    }}

    /* Accessibility: Skip Link & Focus */
    .skip-link {{
      position: absolute;
      top: -40px;
      left: 0;
      background: var(--signal);
      color: #04101e;
      padding: 8px 16px;
      z-index: 1000;
      text-decoration: none;
      font-weight: 600;
      border-radius: 0 0 4px 0;
      transition: top 150ms ease;
    }}
    .skip-link:focus {{
      top: 0;
      outline: 3px solid var(--focus);
    }}

    :focus-visible {{
      outline: 2px solid var(--focus);
      outline-offset: 2px;
    }}

    .container {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 1.5rem 1rem 3rem 1rem;
    }}

    /* Typography & Base Links */
    a {{
      color: var(--signal);
      text-decoration: none;
      transition: color 150ms ease;
    }}
    a:hover {{
      text-decoration: underline;
    }}

    .sr-only {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }}

    /* Masthead */
    .masthead {{
      border-bottom: 1px solid var(--border);
      padding-bottom: 1.25rem;
      margin-bottom: 1.5rem;
    }}
    .masthead-inner {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}
    .brand-mark {{
      color: var(--signal);
      display: flex;
      align-items: center;
    }}
    .brand-title {{
      margin: 0;
      font-size: 1.35rem;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: -0.01em;
    }}
    .brand-sub {{
      margin: 0.2rem 0 0 0;
      font-size: 0.9rem;
      color: var(--muted);
    }}
    .masthead-nav {{
      display: flex;
      gap: 1.25rem;
      align-items: center;
    }}
    .nav-link {{
      color: var(--text);
      font-weight: 500;
      font-size: 0.95rem;
    }}
    .nav-link:hover {{
      color: var(--signal);
      text-decoration: none;
    }}

    /* Dashboard Grid */
    .dashboard {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      margin-bottom: 1.75rem;
    }}
    .dashboard-title {{
      font-size: 1.1rem;
      margin: 0 0 1rem 0;
      color: #ffffff;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .stat-card {{
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1rem;
    }}
    .stat-label {{
      font-size: 0.85rem;
      color: var(--muted);
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .stat-value {{
      font-size: 1.75rem;
      font-weight: 700;
      color: #ffffff;
      margin: 0.25rem 0;
    }}
    .stat-desc {{
      font-size: 0.8rem;
      color: var(--muted);
      line-height: 1.4;
    }}

    /* Distributions Section */
    .distributions {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 1.25rem;
      margin-bottom: 1.25rem;
    }}
    @media (min-width: 768px) {{
      .distributions {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
    .dist-panel {{
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1rem;
    }}
    .dist-heading {{
      font-size: 0.95rem;
      font-weight: 600;
      margin: 0 0 0.85rem 0;
      color: #ffffff;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 130px 1fr 70px;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
      font-size: 0.85rem;
    }}
    .bar-label {{
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .bar-track {{
      background: #091322;
      height: 8px;
      border-radius: 4px;
      overflow: hidden;
      border: 1px solid var(--border);
    }}
    .bar-fill {{
      background: var(--signal);
      height: 100%;
      border-radius: 4px;
      min-width: 2px;
    }}
    .bar-value {{
      text-align: right;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    .bar-count {{
      font-size: 0.75rem;
    }}

    .categories-list {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: 0.5rem;
    }}
    .category-stat {{
      background: #091322;
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.4rem 0.6rem;
      font-size: 0.85rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .cat-name {{
      color: var(--text);
    }}
    .cat-numbers {{
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      font-size: 0.8rem;
    }}
    .cat-pct {{
      font-size: 0.75rem;
    }}

    /* Trust Explanation Details */
    .trust-disclosure {{
      margin-top: 1rem;
      border-top: 1px solid var(--border);
      padding-top: 0.75rem;
    }}
    .trust-disclosure summary {{
      cursor: pointer;
      color: var(--signal);
      font-size: 0.9rem;
      font-weight: 500;
    }}
    .trust-disclosure summary:hover {{
      text-decoration: underline;
    }}
    .trust-explanation {{
      font-size: 0.85rem;
      color: var(--muted);
      line-height: 1.5;
      margin-top: 0.5rem;
    }}

    /* Sticky Toolbar */
    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 50;
      background: var(--bg);
      border-bottom: 1px solid var(--border);
      padding: 0.75rem 0;
      margin-bottom: 1.5rem;
    }}
    .toolbar-inner {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      justify-content: space-between;
    }}
    .toolbar-search {{
      flex: 1 1 240px;
    }}
    .toolbar-search input {{
      width: 100%;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 0.5rem 0.75rem;
      font-size: 0.9rem;
      font-family: inherit;
    }}
    .toolbar-filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
    }}
    .control-group {{
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }}
    .control-label {{
      font-size: 0.8rem;
      color: var(--muted);
      font-weight: 500;
    }}
    .control-select {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 0.45rem 0.65rem;
      font-size: 0.85rem;
      font-family: inherit;
      cursor: pointer;
    }}
    .results-status {{
      font-size: 0.85rem;
      color: var(--muted);
      margin-bottom: 1rem;
      min-height: 1.25rem;
    }}

    /* Card Grid & Cards */
    .cards-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 1rem;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.1rem;
      transition: border-color 150ms ease;
    }}
    .card:hover {{
      border-color: #3b4e6b;
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.4rem;
    }}
    .card-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      align-items: center;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
    }}
    .badge-type {{
      background: var(--surface-raised);
      color: var(--signal);
      border: 1px solid #1e385b;
    }}
    .badge-trust {{
      border: 1px solid transparent;
    }}
    .badge-receipt {{
      background: rgba(52, 211, 153, 0.15);
      color: var(--trusted);
      border-color: rgba(52, 211, 153, 0.3);
    }}
    .badge-corroborated {{
      background: rgba(56, 189, 248, 0.15);
      color: var(--signal);
      border-color: rgba(56, 189, 248, 0.3);
    }}
    .badge-single {{
      background: rgba(251, 191, 36, 0.12);
      color: var(--warning);
      border-color: rgba(251, 191, 36, 0.25);
    }}
    .badge-roundup {{
      background: rgba(167, 139, 250, 0.15);
      color: #c4b5fd;
      border-color: rgba(167, 139, 250, 0.3);
    }}
    .card-date {{
      font-size: 0.8rem;
      color: var(--muted);
      white-space: nowrap;
    }}
    .card-title {{
      margin: 0.3rem 0 0.5rem 0;
      font-size: 1.15rem;
      font-weight: 600;
      color: #ffffff;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .card-meta {{
      font-size: 0.85rem;
      color: var(--muted);
      margin-bottom: 0.4rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }}
    .source-info {{
      font-weight: 500;
      color: var(--text);
    }}
    .card-support {{
      font-size: 0.825rem;
      color: var(--muted);
      margin-bottom: 0.65rem;
    }}
    .card-metrics {{
      font-size: 0.8rem;
      color: var(--signal);
      margin-bottom: 0.65rem;
    }}
    .card-actions {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
      padding-top: 0.5rem;
      border-top: 1px solid #162438;
      font-size: 0.85rem;
    }}
    .action-link {{
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      font-weight: 500;
    }}
    .action-receipt {{
      color: var(--trusted);
    }}
    .link-sep {{
      color: var(--border);
    }}

    /* Footer */
    footer {{
      margin-top: 3rem;
      border-top: 1px solid var(--border);
      padding-top: 1.5rem;
      font-size: 0.85rem;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 1rem;
    }}
    .footer-note {{
      margin: 0;
    }}

    /* SVGs */
    .icon {{
      display: inline-block;
      vertical-align: middle;
      flex-shrink: 0;
    }}

    /* Empty state */
    .empty-state {{
      text-align: center;
      padding: 3rem 1rem;
      color: var(--muted);
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    .hidden {{
      display: none !important;
    }}

    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
      }}
    }}
  </style>
</head>
<body>
  <a href="#stories" class="skip-link">Skip to stories</a>
  <div class="container">
    <header class="masthead">
      <div class="masthead-inner">
        <div class="brand">
          <div class="brand-mark">{render_svg_icon("logo")}</div>
          <div>
            <h1 class="brand-title">BluBot Signal Archive</h1>
            <p class="brand-sub">AI developments, checked against multiple sources</p>
          </div>
        </div>
        <nav class="masthead-nav" aria-label="Main Navigation">
          <a href="#stories" class="nav-link">Archive</a>
          <a href="#trust-dashboard" class="nav-link">Source trust</a>
          <a href="feed.xml" class="nav-link">RSS</a>
        </nav>
      </div>
    </header>

    <main>
      <!-- Source Trust Dashboard -->
      <section id="trust-dashboard" class="dashboard" aria-labelledby="dashboard-heading">
        <h2 id="dashboard-heading" class="dashboard-title">Source Trust &amp; Editorial Intelligence</h2>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">Published stories</div>
            <div class="stat-value">{stats['total_posts']}</div>
            <div class="stat-desc">Total verified editorial entries curated in durable ledger</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Unique sources</div>
            <div class="stat-value">{stats['unique_sources']}</div>
            <div class="stat-desc">Distinct normalized primary publication domains</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Corroborated percentage</div>
            <div class="stat-value">{stats['corroboration_rate']}%</div>
            <div class="stat-desc">{stats['corroborated_posts']} stories backed by independent corroborating links</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Source receipts</div>
            <div class="stat-value">{stats['receipt_coverage']}%</div>
            <div class="stat-desc">{stats['source_receipts']} posts linked to public proof thread on Bluesky</div>
          </div>
          {engagement_card_html}
        </div>

        <div class="distributions">
          <div class="dist-panel">
            <h3 class="dist-heading">Top Primary Sources</h3>
            <div class="sources-list">
              {sources_distribution_html}
            </div>
          </div>
          <div class="dist-panel">
            <h3 class="dist-heading">Coverage by Category</h3>
            <div class="categories-list">
              {coverage_distribution_html}
            </div>
          </div>
        </div>

        <div class="trust-disclosure">
          <details>
            <summary>How this is calculated</summary>
            <div class="trust-explanation">
              <p>Corroborated means BluBot recorded at least one independent supporting source. Source receipts link those supporting reports beneath the original Bluesky post.</p>
              <p>Weekly roundups synthesize community highlights and are included in total counts as their own content type, but excluded from corroboration rate denominators. Metrics are read directly from public decentralized endpoints with zero tracking or user profiling.</p>
            </div>
          </details>
        </div>
      </section>

      <!-- Search, Filtering, and Sorting Controls -->
      <div class="toolbar" role="region" aria-label="Archive filtering controls">
        <div class="toolbar-inner">
          <div class="toolbar-search">
            <label for="search-input" class="sr-only">Search stories</label>
            <input type="search" id="search-input" placeholder="Search by title, source, domain, or topic…" autocomplete="off">
          </div>
          <div class="toolbar-filters">
            <div class="control-group">
              <label for="filter-type" class="control-label">Type:</label>
              <select id="filter-type" class="control-select">
                <option value="all">All</option>
                <option value="news">News</option>
                <option value="repositories">Repositories</option>
                <option value="models">Models</option>
                <option value="roundups">Roundups</option>
                <option value="follow-ups">Follow-ups</option>
              </select>
            </div>
            <div class="control-group">
              <label for="filter-trust" class="control-label">Trust:</label>
              <select id="filter-trust" class="control-select">
                <option value="all">All</option>
                <option value="corroborated">Corroborated</option>
                <option value="receipt">Receipt available</option>
                <option value="single-source">Single-source</option>
              </select>
            </div>
            <div class="control-group">
              <label for="sort-select" class="control-label">Sort:</label>
              <select id="sort-select" class="control-select">
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="corroborated">Most corroborated</option>
                {most_engaged_option}
              </select>
            </div>
          </div>
        </div>
      </div>

      <div id="results-count" class="results-status" aria-live="polite">
        Showing all {stats['total_posts']} published stories
      </div>

      <!-- Story Cards -->
      <section id="stories" class="cards-grid" aria-label="Published Stories Archive">
        {rendered_items}
      </section>
      <div id="no-results-msg" class="empty-state hidden">
        <p>No stories match your search and filter criteria.</p>
      </div>
    </main>

    <footer>
      <p class="footer-note">{ARCHIVE_CAP_NOTICE}</p>
      <p class="footer-note">Built with zero external runtime dependencies · Fully static editorial product</p>
    </footer>
  </div>

  <script>
    (function() {{
      const searchInput = document.getElementById('search-input');
      const filterType = document.getElementById('filter-type');
      const filterTrust = document.getElementById('filter-trust');
      const sortSelect = document.getElementById('sort-select');
      const container = document.getElementById('stories');
      const noResultsMsg = document.getElementById('no-results-msg');
      const statusEl = document.getElementById('results-count');

      if (!container || !searchInput) return;

      const cards = Array.from(container.querySelectorAll('.card'));
      const totalStories = cards.length;

      function updateArchive() {{
        const query = searchInput.value.trim().toLowerCase();
        const typeVal = filterType.value;
        const trustVal = filterTrust.value;
        const sortVal = sortSelect.value;

        let visibleCount = 0;

        cards.forEach(card => {{
          const searchContent = card.getAttribute('data-search') || '';
          const cardType = card.getAttribute('data-content-type') || '';
          const cardTrust = card.getAttribute('data-trust') || '';

          const matchesSearch = !query || searchContent.includes(query);
          const matchesType = (typeVal === 'all') || (cardType === typeVal);
          
          let matchesTrust = true;
          if (trustVal === 'corroborated') {{
            matchesTrust = (cardTrust === 'corroborated' || cardTrust === 'receipt');
          }} else if (trustVal === 'receipt') {{
            matchesTrust = (cardTrust === 'receipt');
          }} else if (trustVal === 'single-source') {{
            matchesTrust = (cardTrust === 'single-source');
          }}

          const isVisible = matchesSearch && matchesType && matchesTrust;
          if (isVisible) {{
            card.classList.remove('hidden');
            visibleCount++;
          }} else {{
            card.classList.add('hidden');
          }}
        }});

        // Sort visible cards
        const sorted = cards.slice().sort((a, b) => {{
          if (sortVal === 'oldest') {{
            const da = a.getAttribute('data-published') || '';
            const db = b.getAttribute('data-published') || '';
            return da.localeCompare(db);
          }} else if (sortVal === 'corroborated') {{
            const ca = parseInt(a.getAttribute('data-corroborated') || '0', 10);
            const cb = parseInt(b.getAttribute('data-corroborated') || '0', 10);
            return cb - ca;
          }} else if (sortVal === 'engagement') {{
            const ea = parseInt(a.getAttribute('data-engagement') || '0', 10);
            const eb = parseInt(b.getAttribute('data-engagement') || '0', 10);
            return eb - ea;
          }} else {{
            // Default newest
            const da = a.getAttribute('data-published') || '';
            const db = b.getAttribute('data-published') || '';
            return db.localeCompare(da);
          }}
        }});

        sorted.forEach(card => container.appendChild(card));

        if (visibleCount === 0) {{
          noResultsMsg.classList.remove('hidden');
        }} else {{
          noResultsMsg.classList.add('hidden');
        }}

        if (statusEl) {{
          if (visibleCount === totalStories) {{
            statusEl.textContent = 'Showing all ' + totalStories + ' published stories';
          }} else {{
            statusEl.textContent = 'Showing ' + visibleCount + ' of ' + totalStories + ' stories';
          }}
        }}
      }}

      searchInput.addEventListener('input', updateArchive);
      filterType.addEventListener('change', updateArchive);
      filterTrust.addEventListener('change', updateArchive);
      sortSelect.addEventListener('change', updateArchive);
    }})();
  </script>
</body>
</html>"""


def build_rss(entries: list) -> str:
    """Build valid RSS 2.0 XML feed (newest first, capped at 50) with enhanced plain-text descriptions."""
    sorted_entries = sorted(entries, key=lambda e: str(e.get("published_at", "")), reverse=True)

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    title_el = ET.SubElement(channel, "title")
    title_el.text = "BluBot AI News Archive"

    link_el = ET.SubElement(channel, "link")
    link_el.text = "https://strike007-3000.github.io/BluBot/"

    desc_el = ET.SubElement(channel, "description")
    desc_el.text = "Curated AI breakthroughs, open-source models, and developer research."

    count = 0
    for e in sorted_entries:
        if count >= FEED_MAX_ITEMS:
            break

        pub_rfc = parse_rfc822_date(e.get("published_at"))
        if not pub_rfc:
            continue

        item = ET.SubElement(channel, "item")

        i_title = ET.SubElement(item, "title")
        i_title.text = str(e.get("title") or "Untitled")

        i_link = ET.SubElement(item, "link")
        raw_url = e.get("url")
        raw_bsky_uri = ((e.get("posts") or {}).get("bluesky") or {}).get("uri")
        bsky_url = at_uri_to_bsky_url(raw_bsky_uri)
        if is_valid_public_http_url(raw_url):
            i_link.text = raw_url
        elif bsky_url:
            i_link.text = bsky_url
        else:
            i_link.text = "https://strike007-3000.github.io/BluBot/"

        i_guid = ET.SubElement(item, "guid", isPermaLink="false")
        i_guid.text = compute_guid(e)

        i_pubdate = ET.SubElement(item, "pubDate")
        i_pubdate.text = pub_rfc

        # Enhanced plain-text description with Topic, Source, Corroboration, Content Type
        category = get_display_category(e)
        source_name, _ = get_display_source_and_domain(e)
        c_type = classify_content_type(e)
        support_domains = get_independent_support_domains(e)
        corroboration_text = f"{len(support_domains)} sources" if support_domains else "single source"

        i_desc = ET.SubElement(item, "description")
        i_desc.text = f"Topic: {category} | Lead Source: {source_name} | Content Type: {c_type} | Corroboration: {corroboration_text}"

        count += 1

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build BluBot static site and RSS feed.")
    parser.add_argument("--out", default="site", help="Output directory path (default: site)")
    args = parser.parse_args(argv)

    # Fail closed: must load successfully from Gist
    status, state_data = _load_gist_state_with_status("seen_articles.json")
    if status != "FOUND" or not isinstance(state_data, dict):
        SafeLogger.error(f"Archive build failed-closed: Gist state unavailable (status={status})")
        sys.exit(1)

    migrated = sanitize_and_migrate_state(state_data)
    published_posts = migrated.get("published_posts", [])

    # Fetch best-effort engagement metrics
    metrics = fetch_metrics_best_effort(published_posts)

    os.makedirs(args.out, exist_ok=True)

    html_content = build_html(published_posts, metrics=metrics)
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    rss_content = build_rss(published_posts)
    with open(os.path.join(args.out, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(rss_content)

    SafeLogger.info(f"Archive build complete: {len(published_posts)} posts processed -> {args.out}")


if __name__ == "__main__":
    main()
