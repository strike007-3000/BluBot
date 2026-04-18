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
        vanguard = VanguardManager()
        
        print("\n[1/2] Probing 29-feed network for health and latency...")
        await vanguard.audit_and_update(client)
        
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
            
        # Display Active feeds
        for url in active:
            if url not in jail:
                display_url = (url[:47] + "...") if len(url) > 50 else url
                print(f"✅ ACTIVE    | {display_url:<50} | Latency: OK")

        print("-"*80)
        print(f"\nAUDIT SUMMARY:")
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
