from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional
from src.config import RSS_FEEDS, URL_TO_ID, ID_TO_NAME
from src.utils import SafeLogger, load_vanguard_state, save_vanguard_state

class VanguardManager:
    """Manages RSS feed health and identifies problematic sources for soft-disable."""

    def __init__(self):
        self.blacklist = load_vanguard_state()

    def get_active_feeds(self) -> List[str]:
        """Returns the list of feeds that are eligible to be fetched."""
        active = []
        now = datetime.now(timezone.utc)

        for url in RSS_FEEDS:
            source_id = URL_TO_ID.get(url, "unknown")
            name = ID_TO_NAME.get(source_id, url)

            if url not in self.blacklist:
                active.append(url)
                continue

            data = self.blacklist[url]
            status = data.get("status", "PENALIZED")

            # WARNING status (1st failure) remains active immediately without recovery logging
            if status == "WARNING":
                active.append(url)
                continue

            # PENALIZED / TERMINAL: check retry gate
            retry_at_str = data.get("retry_at")
            retry_at = datetime.fromisoformat(retry_at_str) if retry_at_str else now

            if now >= retry_at:
                SafeLogger.info(f"Vanguard: Retry window opened: {name}")
                active.append(url)
            else:
                retry_time_str = retry_at.strftime('%H:%M')
                SafeLogger.info(f"Vanguard: Skipping penalized feed (until {retry_time_str}): {name}")

        return active

    def apply_feed_outcomes(self, outcomes: List[Tuple[str, bool, Optional[str]]]) -> bool:
        """
        Processes single-fetch health outcomes, updates in-memory blacklist,
        and saves updated state via save_vanguard_state.
        """
        now = datetime.now(timezone.utc)
        healthy_count = 0
        warned_count = 0
        penalized_count = 0
        recovered_count = 0

        for url, is_healthy, error_msg in outcomes:
            source_id = URL_TO_ID.get(url, "unknown")
            name = ID_TO_NAME.get(source_id, url)

            if is_healthy:
                healthy_count += 1
                if url in self.blacklist:
                    SafeLogger.info(f"Vanguard: Feed recovered: {name}")
                    del self.blacklist[url]
                    recovered_count += 1
            else:
                count = self.blacklist.get(url, {}).get("fail_count", 0) + 1

                # Soft-Backoff Strategy:
                # 1 fail: Warning only (retry_at = now)
                # 2 fails: 1 hour silence
                # 3 fails: 12 hours silence
                # 4+ fails: Exponential (24h, 48h, 72h max)
                if count == 1:
                    backoff_delay = 0
                elif count == 2:
                    backoff_delay = 1
                else:
                    backoff_delay = min(72, 12 * (2**(min(count - 2, 3) - 1)))

                retry_at = now + timedelta(hours=backoff_delay)
                status = "TERMINAL" if count >= 6 else ("WARNING" if count == 1 else "PENALIZED")

                self.blacklist[url] = {
                    "fail_count": count,
                    "last_error": error_msg,
                    "last_seen": now.isoformat(),
                    "retry_at": retry_at.isoformat(),
                    "status": status
                }

                if count >= 6:
                    SafeLogger.warn(f"Vanguard: Feed marked TERMINAL after 6 failures: {name}")
                    penalized_count += 1
                elif count == 1:
                    SafeLogger.info(f"Vanguard: Feed warning; keeping active: {name}")
                    warned_count += 1
                else:
                    SafeLogger.info(f"Vanguard: Feed penalized ({count} fails, backoff {backoff_delay}h): {name}")
                    penalized_count += 1

        total_evaluated = len(outcomes)
        SafeLogger.info(
            f"Vanguard: Evaluated {total_evaluated} feeds "
            f"({healthy_count} healthy, {warned_count} warned, {penalized_count} penalized, {recovered_count} recovered)."
        )
        return save_vanguard_state(self.blacklist)
