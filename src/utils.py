import os
import json
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
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from PIL import Image
from .config import (
    MAX_API_RETRIES, BACKOFF_FACTOR, JITTER_RANGE, 
    SEEN_FILE_PATH, SESSION_FILE_PATH, GENERIC_IMAGE_PATTERNS
)

from .logger import SafeLogger

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
                elif "forbidden" in err_msg or "403" in err_msg:
                    # P1 Badge: 403 is usually permanent (permission/scope issue)
                    SafeLogger.error(f"Forbidden (403) error in {func.__name__}. Skipping retries.")
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

def load_seen_articles():
    if os.path.exists(SEEN_FILE_PATH):
        try:
            with open(SEEN_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"links": [], "recent_topics": []}
    return {"links": [], "recent_topics": []}

def save_seen_articles(data):
    try:
        # P1 Bug Fix: Atomic write to avoid state corruption
        temp_path = f"{SEEN_FILE_PATH}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, SEEN_FILE_PATH)
    except Exception as e:
        SafeLogger.error(f"Critical error saving state: {e}")

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
            # Handle relative URLs
            if not img_url.startswith("http"):
                img_url = urljoin(url, img_url)

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
        
        # Convert RGBA to RGB if necessary
        if img.mode in ("RGBA", "P"):
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
