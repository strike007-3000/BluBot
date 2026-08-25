import os
import json
from typing import Optional, List, Set, Tuple
import asyncio
import functools
import random
import io
import re
import httpx
import socket
import ipaddress
from contextlib import contextmanager
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from PIL import Image
Image.MAX_IMAGE_PIXELS = 10_000_000  # Prevent decompression bomb DoS attacks
from .config import (
    MAX_API_RETRIES, BACKOFF_FACTOR, JITTER_RANGE,
    SEEN_FILE_PATH, SESSION_FILE_PATH, GENERIC_IMAGE_PATTERNS,
    INTERACTIONS_STATE_PATH, VANGUARD_STATE_PATH
)

from .logger import SafeLogger
from .settings import settings

try:
    import fcntl
except ImportError:
    fcntl = None

async def human_delay(min_sec: int, max_sec: int):
    """Wait for a random duration to simulate human activity."""
    delay = random.uniform(min_sec, max_sec)
    SafeLogger.info(f"Applying natural pause: {delay:.1f}s...")
    await asyncio.sleep(delay)

try:
    import msvcrt
except ImportError:
    msvcrt = None

def retry_with_backoff(func):
    """Decorator to retry an async function with exponential backoff and jitter."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        retries = 0
        while retries < MAX_API_RETRIES:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if getattr(e, "skip_backoff_retry", False):
                    SafeLogger.warn(f"Skipping retry loop for {func.__name__}: {e}")
                    raise
                retries += 1
                if retries == MAX_API_RETRIES:
                    SafeLogger.error(f"Ultimate failure in {func.__name__} after {MAX_API_RETRIES} attempts: {e}")
                    raise e

                # Calculate sleep with jitter
                wait_time = (BACKOFF_FACTOR ** retries) + random.uniform(0, JITTER_RANGE)

                # Expert Review Fix: Better logging for rate limits
                err_msg = str(e).lower()
                if "rate limit" in err_msg or "429" in err_msg:
                    SafeLogger.warn(f"Rate limited. Waiting {wait_time:.2f}s before retry {retries}/{MAX_API_RETRIES}...")
                elif "forbidden" in err_msg or "403" in err_msg or "unauthorized" in err_msg or "401" in err_msg:
                    # P1 Badge: 403 / 401 is usually permanent (permission/scope/token issue)
                    SafeLogger.error(f"Authentication/Permission error (403/401) in {func.__name__}. Skipping retries.")
                    raise e
                elif "invalidrequest" in err_msg:
                    # P1 Badge Restrict 400 matching: Only skip retries for explicit atproto validation errors
                    SafeLogger.error(f"Permanent validation error (InvalidRequest) in {func.__name__}. Skipping retries.")
                    raise e
                else:
                    SafeLogger.warn(f"Retry {retries}/{MAX_API_RETRIES} for {func.__name__} in {wait_time:.2f}s... (Error: {str(e)[:100]})")

                await asyncio.sleep(wait_time)
    return wrapper

def save_session_string(session_string: str):
    """Saves the BlueSky session string to a private file."""
    try:
        with open(SESSION_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(session_string)
        # Hidden log (debug level only)
        SafeLogger.debug("Session string cache updated.")
    except Exception as e:
        SafeLogger.error(f"Failed to cache session string: {e}")

def load_session_string():
    """Loads the cached BlueSky session string if it exists."""
    if os.path.exists(SESSION_FILE_PATH):
        try:
            with open(SESSION_FILE_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            SafeLogger.error(f"Failed to read session cache: {e}")
    return None

class FileLock:
    """Cross-platform advisory file lock context manager."""
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock_file = f"{file_path}.lock"
        self.handle = None

    def __enter__(self):
        self.handle = open(self.lock_file, "w")
        if fcntl:
            fcntl.flock(self.handle, fcntl.LOCK_EX)
        elif msvcrt:
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if fcntl:
                fcntl.flock(self.handle, fcntl.LOCK_UN)
            elif msvcrt:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            self.handle.close()
        except Exception:
            pass

def _load_gist_state_with_status(filename: str) -> Tuple[str, Optional[dict]]:
    """Helper to pull state from a private GitHub Gist with status categorization."""
    if not settings.gist_id or not settings.gist_token:
        return "NOT_CONFIGURED", None

    try:
        url = f"https://api.github.com/gists/{settings.gist_id}"
        headers = {
            "Authorization": f"token {settings.gist_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            files = resp.json().get("files", {})
            if filename not in files:
                return "NOT_FOUND", None
            content = files[filename].get("content")
            if not content:
                return "NOT_FOUND", None
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return "FOUND", parsed
                return "CORRUPT", None
            except Exception:
                return "CORRUPT", None
    except Exception as e:
        SafeLogger.warn(f"Failed to load state from Gist ({filename}): {e}")
        return "NETWORK_ERROR", None

def _load_gist_state(filename: str) -> Optional[dict]:
    """Helper to pull state from a private GitHub Gist (preserves dict | None signature)."""
    _, data = _load_gist_state_with_status(filename)
    return data

def _save_gist_state(filename: str, data: dict) -> bool:
    """Helper to push state to a private GitHub Gist."""
    if not settings.gist_id or not settings.gist_token:
        return False

    try:
        url = f"https://api.github.com/gists/{settings.gist_id}"
        headers = {
            "Authorization": f"token {settings.gist_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "files": {
                filename: {"content": json.dumps(data, indent=2)}
            }
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.patch(url, headers=headers, json=payload)
            resp.raise_for_status()
            return True
    except Exception as e:
        SafeLogger.error(f"Failed to save state to Gist ({filename}): {e}")
        return False

def load_vanguard_state() -> dict:
    """
    Loads feed health state from authoritative GitHub Gist (feed_vanguard.json)
    with local cache fallback and synchronization.
    """
    local_state = {}
    if os.path.exists(VANGUARD_STATE_PATH):
        try:
            with FileLock(VANGUARD_STATE_PATH):
                raw = load_json_state(VANGUARD_STATE_PATH)
                if isinstance(raw, dict):
                    local_state = raw
        except Exception as e:
            SafeLogger.warn(f"Vanguard: Local state cache corrupted: {e}")

    if settings.gist_id and settings.gist_token:
        status, gist_data = _load_gist_state_with_status("feed_vanguard.json")
        if status == "FOUND" and isinstance(gist_data, dict):
            SafeLogger.info("Vanguard: Loaded authoritative feed-health state from GitHub Gist.")
            try:
                with FileLock(VANGUARD_STATE_PATH):
                    temp_path = f"{VANGUARD_STATE_PATH}.tmp"
                    save_json_state(temp_path, gist_data, indent=2)
                    os.replace(temp_path, VANGUARD_STATE_PATH)
            except Exception as e:
                SafeLogger.warn(f"Vanguard: Failed to cache Gist state locally: {e}")
            return gist_data
        elif status == "NOT_FOUND":
            SafeLogger.info("Vanguard: Clean initial run; feed_vanguard.json not found on Gist. Using local baseline.")
            return local_state
        elif status == "CORRUPT":
            SafeLogger.warn("Vanguard: Gist feed_vanguard.json corrupted; falling back to local cache.")
            return local_state
        else:
            SafeLogger.warn("Vanguard: Gist request failed; cross-run persistence is degraded, falling back to local cache.")
            return local_state

    return local_state

def save_vanguard_state(state: dict) -> bool:
    """
    Persists feed health state to authoritative GitHub Gist (feed_vanguard.json)
    and atomic local cache.
    """
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Skipping Vanguard state persistence.")
        return True

    local_ok = True
    try:
        with FileLock(VANGUARD_STATE_PATH):
            temp_path = f"{VANGUARD_STATE_PATH}.tmp"
            save_json_state(temp_path, state, indent=2)
            os.replace(temp_path, VANGUARD_STATE_PATH)
    except Exception as e:
        local_ok = False
        SafeLogger.warn(f"Vanguard: Failed to write local cache: {e}")

    if settings.gist_id and settings.gist_token:
        gist_ok = _save_gist_state("feed_vanguard.json", state)
        if gist_ok:
            SafeLogger.info("Vanguard: Authoritative Gist feed-health state saved.")
            if not local_ok:
                SafeLogger.warn("Vanguard: Warning: Local recovery cache write failed, but remote Gist save succeeded.")
            return True
        else:
            SafeLogger.error("Vanguard: Failed to save feed-health state to GitHub Gist; cross-run persistence is unsynchronized.")
            return False

    return local_ok

def load_json_state(file_path: str):
    """Helper to load JSON data from a file path."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_state(file_path: str, data, indent=4):
    """Helper to save state to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)

def load_seen_interactions() -> List[str]:
    """Loads the list of social interaction IDs we've already responded to."""
    if os.path.exists(INTERACTIONS_STATE_PATH):
        try:
            return load_json_state(INTERACTIONS_STATE_PATH)
        except Exception:
            return []
    return []

def save_seen_interactions(interacted_ids: List[str]):
    """Saves the list of social interaction IDs to persistent store."""
    try:
        save_json_state(INTERACTIONS_STATE_PATH, interacted_ids[-500:], indent=4)
    except Exception as e:
        SafeLogger.error(f"Failed to save interactions: {e}")

LEGACY_DEFAULT_UPDATED_AT = "1970-01-01T00:00:00Z"

def sanitize_and_migrate_state(data: Optional[dict]) -> dict:
    """
    Pure and idempotent function to validate and migrate seen_articles schema.
    Never reads the system clock or increments revision.
    Assigns sentinel '1970-01-01T00:00:00Z' if updated_at is missing in legacy state.
    """
    if not isinstance(data, dict):
        data = {}

    state = dict(data)

    schema_version = state.get("schema_version", 1)
    try:
        schema_version = int(schema_version)
    except (ValueError, TypeError):
        schema_version = 2
    state["schema_version"] = max(schema_version, 2)

    revision = state.get("revision", 1)
    try:
        state["revision"] = int(revision)
    except (ValueError, TypeError):
        state["revision"] = 1

    updated_at = state.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        state["updated_at"] = LEGACY_DEFAULT_UPDATED_AT
    else:
        state["updated_at"] = updated_at

    state["unsynced_gist"] = bool(state.get("unsynced_gist", False))

    for list_key in ("links", "recent_topics", "recent_categories", "recent_styles", "watch_topics", "recent_stories", "pending_stories"):
        val = state.get(list_key)
        if not isinstance(val, list):
            state[list_key] = []

    try:
        state["total_posts_curated"] = int(state.get("total_posts_curated", 0))
    except (ValueError, TypeError):
        state["total_posts_curated"] = 0

    if not isinstance(state.get("last_dialect"), str):
        state["last_dialect"] = None

    if not isinstance(state.get("start_date"), str) or not state.get("start_date"):
        state["start_date"] = "2026-03-31"

    return state

def _merge_publication_states(state1: dict, state2: dict) -> dict:
    """
    Deterministically merges two state dictionaries with equal revisions.
    Uses canonical identity and timestamp order for publication collections.
    Uses state1's watch_topics (remote state) to avoid resurrecting deleted watch topics.
    """
    merged = sanitize_and_migrate_state(state1)

    seen_links = set(merged.get("links", []))
    for link in state2.get("links", []):
        if isinstance(link, str) and link and link not in seen_links:
            merged["links"].append(link)
            seen_links.add(link)

    story_map = {}
    for st in merged.get("recent_stories", []):
        if isinstance(st, dict) and "url" in st:
            story_map[st["url"]] = st
    for st in state2.get("recent_stories", []):
        if isinstance(st, dict) and "url" in st:
            if st["url"] not in story_map:
                story_map[st["url"]] = st
    merged["recent_stories"] = sorted(story_map.values(), key=lambda x: str(x.get("published_at", "")))

    pending_map = {}
    for ps in merged.get("pending_stories", []):
        if isinstance(ps, dict) and "url" in ps:
            pending_map[ps["url"]] = ps
    for ps in state2.get("pending_stories", []):
        if isinstance(ps, dict) and "url" in ps:
            if ps["url"] not in pending_map:
                pending_map[ps["url"]] = ps
    merged["pending_stories"] = sorted(pending_map.values(), key=lambda x: str(x.get("created_at", "")))

    merged["watch_topics"] = state1.get("watch_topics", [])

    if str(state2.get("updated_at", "")) > str(merged.get("updated_at", "")):
        merged["updated_at"] = state2.get("updated_at")

    return merged

_FP_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "new", "how",
    "why", "what", "via", "says", "said", "using", "first"
}

_FP_PUBLISHER_SUFFIX_RE = re.compile(r'\s+[\-\|\:\•]\s+([A-Za-z0-9\s]+)$')
_FP_VERSION_RE = re.compile(r'(?:v\d+(?:\.\d+)*|(?<![\$\d])\b[1-9]\d*\.\d+(?:\.\d+)*[a-z]?\b)', re.IGNORECASE)

def compute_story_fingerprint(title: str) -> str:
    """
    Computes a normalized semantic story fingerprint from a headline.
    Strips publisher suffixes, non-version numbers (prices, dates), and stopwords,
    preserving version tokens (e.g., v3.7, v3.6) for version boundary checks.
    """
    if not title or not isinstance(title, str):
        return ""

    cleaned = title.strip()
    match = _FP_PUBLISHER_SUFFIX_RE.search(cleaned)
    if match:
        cleaned = cleaned[:match.start()].strip()

    versions = set()
    for v in _FP_VERSION_RE.findall(cleaned):
        v_norm = v.lower()
        if not v_norm.startswith('v'):
            v_norm = f"v{v_norm}"
        versions.add(v_norm)

    words = re.findall(r'\b[a-zA-Z0-9\-\.]+\b', cleaned.lower())
    tokens = set()
    for w in words:
        w_clean = w.strip(".-")
        if not w_clean or w_clean in _FP_STOPWORDS or len(w_clean) < 2:
            continue

        if _FP_VERSION_RE.match(w_clean):
            v_norm = w_clean.lower()
            if not v_norm.startswith('v'):
                v_norm = f"v{v_norm}"
            tokens.add(v_norm)
            continue

        if re.match(r'^\d+(\.\d+)?$', w_clean):
            continue

        tokens.add(w_clean)

    tokens.update(versions)
    return " ".join(sorted(tokens))

def are_story_fingerprints_similar(fp1: str, fp2: str) -> bool:
    """
    Compares two story fingerprints conservatively.
    Enforces strict version boundary matching: if version tokens (e.g. v3.6 vs v3.7) differ, returns False.
    Returns True if Jaccard similarity >= 0.45 or 3+ tokens match.
    """
    if not fp1 or not fp2:
        return False

    t1 = set(fp1.split())
    t2 = set(fp2.split())

    if len(t1) < 2 or len(t2) < 2:
        return False

    v1 = {t for t in t1 if t.startswith('v') and re.match(r'^v\d+(\.\d+)+', t)}
    v2 = {t for t in t2 if t.startswith('v') and re.match(r'^v\d+(\.\d+)+', t)}

    if v1 and v2 and v1 != v2:
        return False

    intersection = t1 & t2
    union = t1 | t2
    if not union:
        return False

    jaccard = len(intersection) / len(union)
    return jaccard >= 0.45 or len(intersection) >= 3

def is_story_semantic_duplicate(title: str, state: dict) -> bool:
    """Checks if candidate title is semantically equivalent to any story in state."""
    if not title or not isinstance(title, str):
        return False

    candidate_fp = compute_story_fingerprint(title)
    if not candidate_fp:
        return False

    for st in state.get("recent_stories", []):
        if isinstance(st, dict):
            st_title = st.get("title", "")
            st_fp = st.get("fingerprint") or compute_story_fingerprint(st_title)
            if st_fp and (st_fp == candidate_fp or are_story_fingerprints_similar(candidate_fp, st_fp)):
                return True

    for ps in state.get("pending_stories", []):
        if isinstance(ps, dict):
            ps_title = ps.get("title", "")
            ps_fp = ps.get("fingerprint") or compute_story_fingerprint(ps_title)
            if ps_fp and (ps_fp == candidate_fp or are_story_fingerprints_similar(candidate_fp, ps_fp)):
                return True

    return False

def filter_and_update_pending_stories(state: dict, now_utc: Optional[datetime] = None) -> Set[str]:
    """
    Transitions pending stories older than 24 hours to 'uncertain' stage.
    Prunes recent_stories older than 14 days and caps recent_stories/links at 500 entries.
    Returns a set of canonical URLs for all active 'pending', 'uncertain', and 'published' stories.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    seen_urls = set()
    cutoff_14d = now_utc - timedelta(days=14)

    fresh_recent = []
    for st in state.get("recent_stories", []):
        if isinstance(st, dict) and st.get("url"):
            pub_at_str = st.get("published_at")
            keep = True
            if pub_at_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_at_str)
                    if pub_dt < cutoff_14d:
                        keep = False
                except Exception:
                    pass
            if keep:
                fresh_recent.append(st)
                seen_urls.add(normalize_url(st["url"]))

    state["recent_stories"] = fresh_recent[-500:]

    if isinstance(state.get("links"), list):
        state["links"] = state["links"][-500:]

    pending_list = state.get("pending_stories", [])
    for ps in pending_list:
        if isinstance(ps, dict) and ps.get("url"):
            norm_u = normalize_url(ps["url"])
            created_str = ps.get("created_at")
            if created_str and ps.get("stage") == "pending":
                try:
                    created_dt = datetime.fromisoformat(created_str)
                    if (now_utc - created_dt) > timedelta(hours=24):
                        ps["stage"] = "uncertain"
                except Exception:
                    ps["stage"] = "uncertain"
            seen_urls.add(norm_u)

    return seen_urls

def load_seen_articles() -> dict:
    """
    Gist-Authoritative loading with revision tracking and local fallback.
    Loading state passes through sanitize_and_migrate_state and NEVER
    increments revision or changes updated_at.
    """
    with FileLock(SEEN_FILE_PATH):
        gist_state = None
        if settings.gist_id and settings.gist_token:
            gist_raw = _load_gist_state("seen_articles.json")
            if isinstance(gist_raw, dict):
                gist_state = sanitize_and_migrate_state(gist_raw)
                SafeLogger.info(f"Loaded Gist state (revision {gist_state['revision']}).")

        local_state = None
        if os.path.exists(SEEN_FILE_PATH):
            try:
                local_raw = load_json_state(SEEN_FILE_PATH)
                if isinstance(local_raw, dict):
                    local_state = sanitize_and_migrate_state(local_raw)
            except Exception as e:
                SafeLogger.warn(f"Primary local seen articles corrupted: {e}")

        if not local_state:
            bak_path = f"{SEEN_FILE_PATH}.bak"
            if os.path.exists(bak_path):
                try:
                    bak_raw = load_json_state(bak_path)
                    if isinstance(bak_raw, dict):
                        local_state = sanitize_and_migrate_state(bak_raw)
                except Exception:
                    SafeLogger.warn("Backup local seen articles corrupted as well.")

        if gist_state and local_state:
            if gist_state["revision"] > local_state["revision"]:
                selected_state = gist_state
            elif local_state["revision"] > gist_state["revision"]:
                selected_state = local_state
                SafeLogger.info(f"Local state revision ({local_state['revision']}) is higher than Gist revision ({gist_state['revision']}). Using local.")
            else:
                if gist_state == local_state:
                    selected_state = gist_state
                else:
                    SafeLogger.info("Gist and local state have equal revision but different content. Merging deterministically...")
                    selected_state = _merge_publication_states(gist_state, local_state)

            try:
                temp_path = f"{SEEN_FILE_PATH}.tmp"
                save_json_state(temp_path, selected_state, indent=2)
                os.replace(temp_path, SEEN_FILE_PATH)
            except Exception as e:
                SafeLogger.warn(f"Failed to sync primary local file on load: {e}")

            return selected_state

        if gist_state:
            try:
                temp_path = f"{SEEN_FILE_PATH}.tmp"
                save_json_state(temp_path, gist_state, indent=2)
                os.replace(temp_path, SEEN_FILE_PATH)
            except Exception as e:
                SafeLogger.warn(f"Failed to sync local file from Gist: {e}")
            return gist_state

        if local_state:
            return local_state

        return sanitize_and_migrate_state({})

def save_seen_articles(data: dict, is_reservation: bool = False) -> Tuple[bool, dict]:
    """
    Persists state with revision incrementing and updated_at assignment.
    Returns (success_flag, updated_state).
    Pre-broadcast reservation failure: memory rollback, leaves primary and .bak untouched, returns (False, data).
    Post-broadcast settlement failure: rotates primary into .bak, writes primary with unsynced_gist: True, returns (False, state).
    """
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Skip mutating state persistence.")
        return True, data

    state = sanitize_and_migrate_state(data)
    state["revision"] += 1
    state["updated_at"] = datetime.now(timezone.utc).isoformat()

    with FileLock(SEEN_FILE_PATH):
        gist_success = True
        if settings.gist_id and settings.gist_token:
            # A successful upload is authoritative, so clear the recovery marker
            # in the payload before serializing it to Gist.
            state["unsynced_gist"] = False
            gist_success = _save_gist_state("seen_articles.json", state)
            if gist_success:
                if is_reservation:
                    SafeLogger.info(f"Authoritative Gist pending reservation saved (revision {state['revision']}).")
                else:
                    SafeLogger.info(f"Authoritative Gist settlement saved (revision {state['revision']}).")
            else:
                SafeLogger.error("Failed to push state to GitHub Gist.")

        if is_reservation and settings.gist_id and settings.gist_token and not gist_success:
            SafeLogger.error("Authoritative Gist pending reservation failed. Rolling back reservation write.")
            return False, data

        if not gist_success:
            state["unsynced_gist"] = True

        local_success = True
        try:
            if os.path.exists(SEEN_FILE_PATH):
                bak_path = f"{SEEN_FILE_PATH}.bak"
                os.replace(SEEN_FILE_PATH, bak_path)

            temp_path = f"{SEEN_FILE_PATH}.tmp"
            save_json_state(temp_path, state, indent=2)
            os.replace(temp_path, SEEN_FILE_PATH)
        except Exception as e:
            SafeLogger.error(f"Failed writing local primary state file: {e}")
            local_success = False

        overall_success = gist_success and local_success
        return overall_success, state


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Normalizes a URL by resolving protocol-relative links, stripping fragments,
    standardizing hostnames, and removing tracking parameters (UTM, etc.).
    """
    if not url:
        return ""

    # 1. Handle protocol-relative URLs (e.g., //example.com)
    if url.strip().startswith("//"):
        # Assume https as the modern standard for protocol-relative links
        url = "https:" + url.strip()

    # 2. Resolve relative URLs against a base if provided
    if base_url and not urlparse(url).scheme:
        url = urljoin(base_url, url)

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url

        # 3. Standardize components
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path if parsed.path else "/"

        # 4. Strip tracking query parameters
        query_params = parse_qs(parsed.query)
        tracking_prefixes = ('utm_', 'ref', 'fbclid', 'gclid', '_ga', 'mc_cid', 'mc_eid')
        tracking_exact = ('s', 'igsh', 'feature')

        clean_params = {
            k: v for k, v in query_params.items()
            if not k.lower().startswith(tracking_prefixes)
            and k.lower() not in tracking_exact
        }

        # 5. Reconstruct without fragments (#)
        normalized = urlunparse((
            scheme,
            netloc,
            path,
            parsed.params,
            urlencode(clean_params, doseq=True),
            "" # Fragment is stripped
        ))

        return normalized
    except Exception:
        return url

def _is_public_ip(ip_str: str) -> bool:
    """Checks if an IP address is a routable public address."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return not (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        )
    except ValueError:
        return False

def _resolve_public_ip_candidates(hostname: str) -> Optional[List[str]]:
    """Resolves a hostname and returns only public IP candidates."""
    try:
        resolved = socket.getaddrinfo(hostname, None)
        ips = list(set(res[4][0] for res in resolved))
        # If any resolved IP is private, we block the whole host for safety
        if any(not _is_public_ip(ip) for ip in ips):
            return None
        return ips
    except Exception:
        return None

def is_safe_url(url: str) -> bool:
    """Validates if a URL is safe from SSRF without sending a request."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname or hostname.lower() == 'localhost':
            return False

        ips = _resolve_public_ip_candidates(hostname)
        if not ips:
            return False

        return True
    except Exception:
        return False

@contextmanager
def _resolver_pinned_to_ips(hostname: str, allowed_ips: List[str]):
    """
    Temporarily constrains DNS resolution for one hostname to a prevalidated set.
    Prevents DNS rebinding attacks.
    """
    original_getaddrinfo = socket.getaddrinfo
    canonical_hostname = hostname.lower()
    allowed_set = set(allowed_ips)

    def guarded_getaddrinfo(host: str, *args, **kwargs):
        if str(host).lower() != canonical_hostname:
            return original_getaddrinfo(host, *args, **kwargs)

        current = original_getaddrinfo(host, *args, **kwargs)
        current_ips = {entry[4][0] for entry in current}

        if current_ips - allowed_set:
            raise socket.gaierror(f"SSRF Prevention: Resolver returned unexpected address for {host}")

        return [entry for entry in current if entry[4][0] in allowed_set]

    socket.getaddrinfo = guarded_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo

async def get_with_safe_redirects(client, url, timeout=10.0, max_redirects=5, headers=None):
    """Fetches a URL while validating every hop in the redirect chain."""
    current_url = url
    initial_scheme = urlparse(url).scheme

    for _ in range(max_redirects + 1):
        parsed = urlparse(current_url)
        if parsed.scheme not in ('http', 'https'):
            SafeLogger.warn(f"SSRF Prevention: Blocked non-HTTP scheme: {parsed.scheme}", "unsafe_url_blocked")
            return None

        hostname = parsed.hostname
        if not hostname or hostname.lower() == 'localhost':
            SafeLogger.warn(f"SSRF Prevention: Blocked local hostname: {hostname}", "unsafe_url_blocked")
            return None

        ips = _resolve_public_ip_candidates(hostname)
        if not ips:
            SafeLogger.warn(f"SSRF Prevention: Blocked non-public or unresolvable host: {hostname}", "unsafe_url_blocked")
            return None

        try:
            with _resolver_pinned_to_ips(hostname, ips):
                response = await client.get(current_url, timeout=timeout, follow_redirects=False, headers=headers)
        except Exception as e:
            SafeLogger.warn(f"Request blocked by safety guards: {e}", "unsafe_url_blocked")
            return None

        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                return response
            next_url = urljoin(current_url, location)

            # Prevent scheme downgrade (https -> http)
            if initial_scheme == 'https' and urlparse(next_url).scheme == 'http':
                SafeLogger.warn("SSRF Prevention: Blocked downgrade redirect", "unsafe_url_blocked")
                return None

            current_url = next_url
            continue

        return response

    return None

async def get_link_metadata(client, url):
    """Fetches high-fidelity metadata (og:image, description) from a URL with SSRF protection."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 BluBot/3.6 (Security Hardened)'}
        resp = await get_with_safe_redirects(client, url, timeout=15, headers=headers)
        if resp is None or resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Meta Priority Matrix
        title = soup.find("meta", property="og:title")
        desc = soup.find("meta", property="og:description")
        image = soup.find("meta", property="og:image")

        # Expert Review Fix: Sanitize image URLs for platform limits
        img_url = image["content"] if image else None
        image_data = None

        if img_url:
            # P1 Badge: Use robust normalization for images (handles // and relative)
            img_url = normalize_url(img_url, base_url=url)

            # P1 Bug Fix: Filter out generic logos
            is_generic = any(p in img_url.lower() for p in GENERIC_IMAGE_PATTERNS)
            if is_generic:
                SafeLogger.info(f"Generic logo detected: {img_url}. Searching for fallback...")
                img_url = None
            else:
                try:
                    img_resp = await get_with_safe_redirects(client, img_url, timeout=10, headers=headers)
                    if img_resp and img_resp.status_code == 200:
                        image_data = img_resp.content
                except Exception:
                    SafeLogger.warn(f"Failed to fetch metadata image: {img_url}")

        return {
            "title": title["content"][:200] if title else soup.title.string[:200] if soup.title else "News Report",
            "description": desc["content"][:300] if desc else "No description available.",
            "url": url,
            "image": image_data,
            "image_url": img_url
        }
    except Exception as e:
        SafeLogger.warn(f"Metadata extraction failed: {e}")
        return None

def compress_image(image_bytes, max_size_kb=900):
    """Losslessly then lossily compresses image to stay within platform limits (e.g., Bluesky 1MB)."""
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Defensive Architecture: Force RGB for all platform-compatible JPEGs
        if img.mode != "RGB":
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)

        # Iterative Quality Downscaling
        quality = 80
        while output.tell() > max_size_kb * 1024 and quality > 30:
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            quality -= 10

        return output.getvalue()
    except Exception as e:
        SafeLogger.error(f"Image compression critical failure: {e}")
        return None

def get_image_mime(image_bytes):
    """Detects MIME type from image bytes for broadcaster fidelity."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return Image.MIME.get(img.format)
    except Exception:
        return None

def truncate_bytes(text, max_bytes):
    """Unicode-aware byte-level truncation to prevent Bluesky index errors."""
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode('utf-8', 'ignore')

def smart_truncate(text, max_chars, suffix='...'):
    """Truncates text at word boundaries within the limit, appending a suffix."""
    if not text or len(text) <= max_chars:
        return text

    # Reserve space for the suffix
    limit = max_chars - len(suffix)
    truncated = text[:limit]

    # Backtrack to the last whitespace to avoid mid-word cutoff
    last_space = truncated.rfind(' ')
    if last_space != -1:
        truncated = truncated[:last_space]

    return f"{truncated.rstrip()}{suffix}"

def smart_split(text, limit, max_chunks=None):
    """Splits text into chunks within the limit, prioritizing paragraph and sentence boundaries."""
    if not text:
        return []

    # If the text has double-newlines, it is explicitly structured as paragraphs/posts by the model.
    # We should split by \n\n first if present, then process each paragraph.
    if "\n\n" in text:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        final_chunks = []
        truncated = False
        for idx, p in enumerate(paragraphs):
            if max_chunks and len(final_chunks) >= max_chunks:
                truncated = True
                break
            remaining_budget = max_chunks - len(final_chunks) if max_chunks else None
            if len(p) <= limit:
                final_chunks.append(p)
            else:
                split_p = smart_split(p, limit, remaining_budget)
                if split_p and split_p[-1].endswith("..."):
                    truncated = True
                final_chunks.extend(split_p)
        if max_chunks and (len(final_chunks) > max_chunks or truncated):
            final_chunks = final_chunks[:max_chunks]
            if final_chunks:
                last = final_chunks[-1]
                if not last.endswith("..."):
                    final_chunks[-1] = last.rstrip() + "..."
        return final_chunks

    # Expert Review: If text fits in one part, return immediately
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        # Check if we've hit the thread cap
        if max_chunks and len(chunks) >= max_chunks:
            # Ensure the last chunk indicates truncation if there was more content
            if chunks:
                last = chunks[-1]
                if not last.endswith("..."):
                    chunks[-1] = last.rstrip() + "..."
            break

        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        # 1. Try splitting at paragraphs
        idx = remaining.rfind('\n\n', 0, limit)
        # 2. Try splitting at sentences
        if idx == -1:
            idx = remaining.rfind('. ', 0, limit)
            if idx != -1:
                idx += 1 # Include period
        # 3. Try splitting at words
        if idx == -1:
            idx = remaining.rfind(' ', 0, limit)

        # 4. Hard cut if no boundaries found (unlikely)
        if idx == -1:
            idx = limit

        chunk = remaining[:idx].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[idx:].strip()

    return chunks
