import asyncio
import httpx
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.feed_vanguard import VanguardManager
from src.config import RSS_FEEDS
from src.utils import SafeLogger

# Ensure terminal supports emojis (UTF-8)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def run_standalone_audit():
    """Performs a comprehensive feed audit and displays a health report."""
    print("\n" + "="*80)
    print(f"📡 BLUBOT ELITE FEED AUDIT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        vanguard = await asyncio.to_thread(VanguardManager)

        print(f"\n[1/2] Probing {len(RSS_FEEDS)}-feed network for health and latency...")
        from src.curator import fetch_news
        active_feeds = vanguard.get_active_feeds()
        _, feed_outcomes = await fetch_news(client, feed_list=active_feeds, limit=None)
        await asyncio.to_thread(vanguard.apply_feed_outcomes, feed_outcomes)

        active = vanguard.get_active_feeds()
        jail = vanguard.blacklist

        print("\n" + "-"*80)
        print(f"{'STATUS':<10} | {'SOURCE':<50} | {'DETAILS'}")
        print("-"*80)

        # Display Jail first (Problematic feeds)
        for url, data in jail.items():
            status = data.get("status", "PENALIZED")
            icon = "🚨" if status == "TERMINAL" else "📉"
            error = data.get("last_error", "Unknown")
            fails = data.get("fail_count", 0)

            # Shorten URL for display
            display_url = (url[:47] + "...") if len(url) > 50 else url
            print(f"{icon} {status:<7} | {display_url:<50} | Fail Count: {fails} ({error})")

        from src.config import SOURCE_REGISTRY, URL_TO_ID, FEED_CATEGORY_MAP, ID_TO_NAME
        import feedparser, calendar

        category_stats = {}

        for url in active:
            if url not in jail:
                source_id = URL_TO_ID.get(url, "unknown")
                source_name = ID_TO_NAME.get(source_id, url)
                category = FEED_CATEGORY_MAP.get(source_id, "unknown")

                latest_str = "N/A"
                try:
                    resp = await client.get(url, timeout=10.0)
                    if resp.status_code == 200:
                        parsed = await asyncio.to_thread(feedparser.parse, resp.content)
                        if parsed.entries:
                            e = parsed.entries[0]
                            if hasattr(e, 'published_parsed') and e.published_parsed:
                                dt = datetime.fromtimestamp(calendar.timegm(e.published_parsed), timezone.utc)
                                latest_str = dt.isoformat()[:10]
                            elif hasattr(e, 'updated_parsed') and e.updated_parsed:
                                dt = datetime.fromtimestamp(calendar.timegm(e.updated_parsed), timezone.utc)
                                latest_str = dt.isoformat()[:10]
                except Exception:
                    pass

                if category not in category_stats:
                    category_stats[category] = []
                category_stats[category].append((source_name, latest_str))

                display_name = (source_name[:47] + "...") if len(source_name) > 50 else source_name
                print(f"✅ ACTIVE    | [{category:<14}] {display_name:<33} | Freshness: {latest_str}")

        print("-"*80)
        print(f"\nAUDIT SUMMARY BY CATEGORY:")
        for cat, items in sorted(category_stats.items()):
            print(f"  - {cat:<15}: {len(items)} active feed(s)")
        print(f"\nOVERALL STATS:")
        print(f"  - Total Configured: {len(RSS_FEEDS)}")
        print(f"  - Currently Healthy: {len(active) - len([u for u in active if u in jail])}")
        print(f"  - In Jail (Soft-Disable): {len(jail)}")
        print(f"  - Terminal Failure: {len([u for u in jail.values() if u['status'] == 'TERMINAL'])}")
        print("="*80 + "\n")

if __name__ == "__main__":
    try:
        asyncio.run(run_standalone_audit())
    except KeyboardInterrupt:
        print("\nAudit aborted by user.")
    except Exception as e:
        print(f"\nAudit failed with error: {e}")
