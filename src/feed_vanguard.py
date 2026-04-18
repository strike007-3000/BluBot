import asyncio
import json
import os
import httpx
import feedparser
from datetime import datetime, timezone, timedelta
from src.config import RSS_FEEDS, VANGUARD_STATE_PATH
from src.utils import SafeLogger

class VanguardManager:
    """Manages RSS feed health and identifies problematic sources for soft-disable."""
    
    def __init__(self, state_path=VANGUARD_STATE_PATH):
        self.state_path = state_path
        self.blacklist = self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                SafeLogger.warn(f"Vanguard: Failed to load state: {e}")
        return {}

    def _save_state(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.blacklist, f, indent=4)
        except Exception as e:
            SafeLogger.error(f"Vanguard: Failed to save state: {e}")

    def get_active_feeds(self):
        """Returns the list of feeds that are NOT currently blacklisted or have passed their retry gate."""
        active = []
        now = datetime.now(timezone.utc)
        
        for url in RSS_FEEDS:
            if url not in self.blacklist:
                active.append(url)
                continue
            
            # Check if retry gate is open
            data = self.blacklist[url]
            retry_at = datetime.fromisoformat(data["retry_at"])
            
            if now >= retry_at:
                SafeLogger.info(f"Vanguard: Attempting recovery for {url}")
                active.append(url)
            else:
                SafeLogger.info(f"Vanguard: Skipping blacklisted feed (until {retry_at.strftime('%H:%M')}): {url}")
                
        return active

    async def audit_and_update(self, client: httpx.AsyncClient):
        """Perform a full scan of all feeds and update the blacklist."""
        active_pool = self.get_active_feeds()
        tasks = [self._check_feed(client, url) for url in active_pool]
        results = await asyncio.gather(*tasks)
        
        updates_made = False
        for url, is_healthy, error_msg in results:
            if is_healthy:
                if url in self.blacklist:
                    SafeLogger.info(f"Vanguard: ✅ Feed recovered: {url}")
                    del self.blacklist[url]
                    updates_made = True
            else:
                # Add to blacklist or update failure count
                updates_made = True
                self._penalize_feed(url, error_msg)
        
        if updates_made:
            self._save_state()

    def _penalize_feed(self, url, error_msg):
        now = datetime.now(timezone.utc)
        count = self.blacklist.get(url, {}).get("fail_count", 0) + 1
        
        # Exponential Backoff for retries: 12h, 24h, 48h... up to a max of 72h
        backoff_delay = min(72, 12 * (2**(min(count, 3) - 1)))
        retry_at = now + timedelta(hours=backoff_delay)
        
        self.blacklist[url] = {
            "fail_count": count,
            "last_error": error_msg,
            "last_seen": now.isoformat(),
            "retry_at": retry_at.isoformat(),
            "status": "TERMINAL" if count >= 6 else "PENALIZED"
        }
        
        if count >= 6:
            SafeLogger.warn(f"Vanguard: 🚨 Feed marked TERMINAL after 6 failures: {url}")
        else:
            SafeLogger.info(f"Vanguard: 📉 Feed penalized ({count} fails, backoff {backoff_delay}h): {url}")

    async def _check_feed(self, client, url):
        """Helper to check a single feed's health."""
        try:
            resp = await client.get(url, timeout=15, follow_redirects=True)
            if resp.status_code != 200:
                return url, False, f"HTTP {resp.status_code}"
            
            # Parse check
            feed = await asyncio.to_thread(feedparser.parse, resp.text)
            if feed.bozo and not feed.entries:
                return url, False, "Parse error/Invalid RSS"
            
            if not feed.entries:
                return url, False, "Empty feed"
                
            return url, True, None
        except Exception as e:
            return url, False, str(e)

if __name__ == "__main__":
    # Standalone diagnostic mode
    async def diagnostic():
        async with httpx.AsyncClient() as client:
            v = VanguardManager()
            await v.audit_and_update(client)
    asyncio.run(diagnostic())
