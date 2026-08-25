import pytest
import os
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from src.feed_vanguard import VanguardManager
from src.utils import load_vanguard_state, save_vanguard_state

def test_vanguard_gating_and_status_distinctions():
    """Verify WARNING remains eligible without log noise, and PENALIZED/TERMINAL honors retry_at."""
    now = datetime.now(timezone.utc)

    mock_state = {
        "https://warning.com/feed": {
            "fail_count": 1,
            "status": "WARNING",
            "retry_at": now.isoformat()
        },
        "https://penalized_active.com/feed": {
            "fail_count": 2,
            "status": "PENALIZED",
            "retry_at": (now - timedelta(minutes=5)).isoformat() # Window expired
        },
        "https://penalized_skipped.com/feed": {
            "fail_count": 2,
            "status": "PENALIZED",
            "retry_at": (now + timedelta(hours=1)).isoformat() # Still penalized
        }
    }

    with patch("src.feed_vanguard.load_vanguard_state", return_value=mock_state):
        with patch("src.feed_vanguard.RSS_FEEDS", [
            "https://healthy.com/feed",
            "https://warning.com/feed",
            "https://penalized_active.com/feed",
            "https://penalized_skipped.com/feed"
        ]):
            vanguard = VanguardManager()
            active_feeds = vanguard.get_active_feeds()

            # Healthy feed is active
            assert "https://healthy.com/feed" in active_feeds
            # WARNING feed is active immediately
            assert "https://warning.com/feed" in active_feeds
            # Expired PENALIZED feed is active (retry window opened)
            assert "https://penalized_active.com/feed" in active_feeds
            # Active PENALIZED feed is excluded
            assert "https://penalized_skipped.com/feed" not in active_feeds

def test_vanguard_apply_outcomes_and_recovery():
    """Verify single-fetch outcomes update blacklist and clear recovered feeds."""
    initial_state = {
        "https://failing.com/feed": {
            "fail_count": 2,
            "status": "PENALIZED",
            "retry_at": "2026-08-25T12:00:00+00:00"
        }
    }

    saved_states = []
    def mock_save(state):
        saved_states.append(dict(state))
        return True

    with patch("src.feed_vanguard.load_vanguard_state", return_value=initial_state):
        with patch("src.feed_vanguard.save_vanguard_state", side_effect=mock_save):
            vanguard = VanguardManager()

            # Outcome 1: failing.com recovered!
            # Outcome 2: new feed failed (1st fail -> WARNING)
            outcomes = [
                ("https://failing.com/feed", True, None),
                ("https://newwarn.com/feed", False, "HTTP 500")
            ]

            save_ok = vanguard.apply_feed_outcomes(outcomes)
            assert save_ok is True
            assert "https://failing.com/feed" not in vanguard.blacklist
            assert "https://newwarn.com/feed" in vanguard.blacklist
            assert vanguard.blacklist["https://newwarn.com/feed"]["status"] == "WARNING"
            assert vanguard.blacklist["https://newwarn.com/feed"]["fail_count"] == 1

def test_vanguard_gist_authoritative_persistence(tmp_path):
    """Verify Gist persistence load/save semantics and local fallback caching."""
    from src.settings import settings
    orig_gist_id = settings.gist_id
    orig_gist_token = settings.gist_token
    orig_dry_run = settings.is_dry_run
    object.__setattr__(settings, "gist_id", "mock-gist-id")
    object.__setattr__(settings, "gist_token", "mock-gist-token")
    object.__setattr__(settings, "is_dry_run", False)

    cache_file = tmp_path / "broken_feeds.json"

    gist_state = {
        "https://gist-broken.com/feed": {
            "fail_count": 3,
            "status": "PENALIZED"
        }
    }

    try:
        with patch("src.utils.VANGUARD_STATE_PATH", str(cache_file)):
            # 1. Successful Gist load overrides local
            with patch("src.utils._load_gist_state_with_status", return_value=("FOUND", gist_state)):
                loaded = load_vanguard_state()
                assert loaded == gist_state
                # Assert local cache was written atomically
                assert cache_file.exists()
                with open(cache_file, "r") as f:
                    assert json.load(f) == gist_state

            # 2. Network error on Gist load falls back to existing local cache
            with patch("src.utils._load_gist_state_with_status", return_value=("NETWORK_ERROR", None)):
                loaded_fallback = load_vanguard_state()
                assert loaded_fallback == gist_state

            # 3. Gist save failure returns False and logs cross-run unsynchronized
            with patch("src.utils._save_gist_state", return_value=False):
                save_res = save_vanguard_state({"test": 1})
                assert save_res is False
                # Local cache is still written
                with open(cache_file, "r") as f:
                    assert json.load(f) == {"test": 1}

            # 4. Gist save success returns True
            with patch("src.utils._save_gist_state", return_value=True):
                save_ok = save_vanguard_state({"test": 2})
                assert save_ok is True
    finally:
        object.__setattr__(settings, "gist_id", orig_gist_id)
        object.__setattr__(settings, "gist_token", orig_gist_token)
        object.__setattr__(settings, "is_dry_run", orig_dry_run)
