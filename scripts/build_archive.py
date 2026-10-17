#!/usr/bin/env python3
"""Build static HTML archive and RSS 2.0 feed from published_posts ledger in GitHub Gist."""
import argparse
import email.utils
import hashlib
import html
import ipaddress
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

# Ensure imports from src work
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.logger import SafeLogger
from src.settings import settings
from src.utils import _is_public_ip, _load_gist_state_with_status, sanitize_and_migrate_state

ARCHIVE_CAP_NOTICE = "Archive displays up to the last 500 published stories from the durable ledger."
FEED_MAX_ITEMS = 50


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
        # If hostname is an IP address literal, it must be public
        try:
            ip = ipaddress.ip_address(hostname)
            return _is_public_ip(str(ip))
        except ValueError:
            # Domain name
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


def parse_rfc822_date(date_str: Optional[str]) -> Optional[str]:
    """Convert ISO datetime string to RFC 822 format."""
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return email.utils.format_datetime(dt)
    except Exception:
        return None


def build_html(entries: list) -> str:
    """Build single-page responsive static HTML archive (newest first)."""
    sorted_entries = sorted(entries, key=lambda e: str(e.get("published_at", "")), reverse=True)

    items_html = []
    for e in sorted_entries:
        title = html.escape(str(e.get("title") or "Untitled"))
        topic = html.escape(str(e.get("topic") or "General"))
        pub_at = html.escape(str(e.get("published_at") or ""))
        raw_url = e.get("url")
        raw_bsky_uri = ((e.get("posts") or {}).get("bluesky") or {}).get("uri")
        bsky_url = at_uri_to_bsky_url(raw_bsky_uri)

        # Source link: only if valid public HTTP(S) URL
        if is_valid_public_http_url(raw_url):
            url_link = f'<a href="{html.escape(raw_url)}" target="_blank" rel="noopener noreferrer">Source Article</a>'
        else:
            url_link = f'<span>{html.escape(str(raw_url or ""))}</span>'

        # Bluesky link: only if valid bsky.app URL
        if bsky_url:
            bsky_link = f' · <a href="{html.escape(bsky_url)}" target="_blank" rel="noopener noreferrer">Bluesky Post</a>'
        else:
            bsky_link = ""

        item_card = f"""
        <article class="card">
          <h2>{title}</h2>
          <div class="meta">
            <span class="topic">{topic}</span>
            <span class="date">{pub_at}</span>
          </div>
          <div class="links">
            {url_link}{bsky_link}
          </div>
        </article>"""
        items_html.append(item_card)

    rendered_items = "\n".join(items_html) if items_html else "<p>No published stories yet.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BluBot News Archive</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --link: #58a6ff;
      --accent: #1f6feb;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      margin: 0;
      padding: 2rem 1rem;
    }}
    .container {{
      max-width: 800px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 2rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 1rem;
    }}
    h1 {{
      margin: 0 0 0.5rem 0;
      color: #fff;
    }}
    .notice {{
      color: var(--text-muted);
      font-size: 0.9rem;
    }}
    .feed-link {{
      display: inline-block;
      margin-top: 0.5rem;
      color: var(--link);
      text-decoration: none;
      font-weight: 500;
    }}
    .feed-link:hover {{ text-decoration: underline; }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1.25rem;
      margin-bottom: 1rem;
    }}
    .card h2 {{
      margin: 0 0 0.5rem 0;
      font-size: 1.2rem;
      color: #fff;
    }}
    .meta {{
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 0.75rem;
    }}
    .topic {{
      background: rgba(31, 111, 235, 0.2);
      color: var(--link);
      padding: 0.15rem 0.5rem;
      border-radius: 12px;
      margin-right: 0.5rem;
    }}
    .links a {{
      color: var(--link);
      text-decoration: none;
      font-size: 0.9rem;
    }}
    .links a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>🤖 BluBot AI News Archive</h1>
      <p class="notice">{ARCHIVE_CAP_NOTICE}</p>
      <a class="feed-link" href="feed.xml">📡 Subscribe via RSS 2.0</a>
    </header>
    <main>
      {rendered_items}
    </main>
  </div>
</body>
</html>"""


def build_rss(entries: list) -> str:
    """Build valid RSS 2.0 XML feed (newest first, capped at 50)."""
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
        # Per specification: items with unparseable published_at are skipped from RSS
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

        i_desc = ET.SubElement(item, "description")
        topic = e.get("topic") or "General"
        i_desc.text = f"Topic: {topic}"

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

    os.makedirs(args.out, exist_ok=True)

    html_content = build_html(published_posts)
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    rss_content = build_rss(published_posts)
    with open(os.path.join(args.out, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(rss_content)

    SafeLogger.info(f"Archive build complete: {len(published_posts)} posts processed -> {args.out}")


if __name__ == "__main__":
    main()
