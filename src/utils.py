import os
import json
import asyncio
import functools
import random
import io
import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin
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
                    SafeLogger.error(f"Forbidden (403) error in {func.__name__}. Skipping retries.")
                    raise e
                elif "invalidrequest" in err_msg:
                    # Narrowed check (Codex): Only skip retries for explicit atproto validation errors
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
        SafeLogger.debug("BlueSky session string persisted.")
    except Exception as e:
        SafeLogger.error(f"Failed to save session string: {e}")

def load_session_string() -> str:
    """Loads the BlueSky session string from the private file."""
    try:
        if os.path.exists(SESSION_FILE_PATH):
            with open(SESSION_FILE_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        SafeLogger.error(f"Failed to load session string: {e}")
    return None

def compress_image(image_bytes: bytes, max_size=900000) -> bytes:
    """Compresses an image to stay under the specified max_size (default <1MB for Bluesky)."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        quality = 85
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        
        attempt = 0
        while buffer.tell() > max_size and attempt < 5:
            attempt += 1
            quality -= 15
            width, height = img.size
            img = img.resize((int(width * 0.8), int(height * 0.8)), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=max(quality, 30), optimize=True)
            
        return buffer.getvalue()
    except Exception as e:
        SafeLogger.error(f"Failed to compress image (skipping thumbnail): {e}")
        return None

def get_image_mime(image_bytes: bytes) -> str:
    """Detects the MIME type of image data using Pillow."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        fmt = img.format.lower() if img.format else 'jpeg'
        if fmt == 'jpg': fmt = 'jpeg'
        return f"image/{fmt}"
    except Exception:
        return None 

def truncate_bytes(text: str, limit: int) -> str:
    """UTF-8 byte-safe truncation to avoid splitting multi-byte characters."""
    encoded = text.encode('utf-8')
    if len(encoded) <= limit:
        return text
    
    # Truncate and decode, ignoring errors (dropping partial trailing char)
    return encoded[:limit].decode('utf-8', errors='ignore')

def load_seen_articles():
    """Loads processing memory using absolute paths."""
    if os.path.exists(SEEN_FILE_PATH):
        try:
            with open(SEEN_FILE_PATH, "r") as f:
                data = json.load(f)
                if "recent_topics" not in data:
                    data["recent_topics"] = []
                # Performance fix: ensure we store seen as a set for O(1) in-memory lookups later
                return data
        except (json.JSONDecodeError, IOError) as e:
            SafeLogger.error(f"Corruption or read error in seen articles: {e}")
    return {"links": [], "recent_topics": []}

def save_seen_articles(data):
    """Saves updated memory to the absolute SEEN_FILE_PATH using atomic writing."""
    try:
        # Retention management
        data["links"] = data["links"][-500:]
        data["recent_topics"] = data["recent_topics"][-20:]
        
        # Atomic Write: Write to temp file then rename
        temp_path = f"{SEEN_FILE_PATH}.tmp"
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=4)
        
        # Expert Review Fix: Atomic swap to prevent truncation corruption
        os.replace(temp_path, SEEN_FILE_PATH)
        
        SafeLogger.info(f"Saved {len(data['links'])} seen articles (Atomic).")
    except Exception as e:
        SafeLogger.error(f"Error saving seen articles: {e}")
        if os.path.exists(f"{SEEN_FILE_PATH}.tmp"):
            os.remove(f"{SEEN_FILE_PATH}.tmp")

async def get_link_metadata(client, url):
    """Scrapes OpenGraph metadata using a shared httpx client with modern browser headers."""
    SafeLogger.info(f"Scraping metadata: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Ch-Ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
    try:
        # Ensure we follow redirects (OpenAI often redirects to a trailing slash version)
        response = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()
        
        # Expert Review Fix: Wrap CPU-bound Beautiful Soup in to_thread
        soup = await asyncio.to_thread(BeautifulSoup, response.text, 'html.parser')

        og_title = soup.find("meta", property="og:title")
        og_description = soup.find("meta", property="og:description")
        og_image = soup.find("meta", property="og:image")

        title = og_title['content'] if og_title else (soup.title.string if soup.title else "News Update")
        description = og_description['content'] if og_description else ""
        image_url = og_image['content'] if og_image else None
        
        # Expert Review Fix: Generic Image Filtering
        is_generic = False
        original_image_url = None
        if image_url:
            original_image_url = urljoin(url, image_url)
            image_url_lower = original_image_url.lower()
            if any(p.lower() in image_url_lower for p in GENERIC_IMAGE_PATTERNS):
                SafeLogger.info(f"Generic logo detected: {image_url_lower}. Searching for fallback...")
                is_generic = True

        if not original_image_url or is_generic:
            # Fallback: Find the first substantial image on the page
            found_fallback = False
            for img in soup.find_all("img"):
                fallback_url = img.get("src")
                if fallback_url:
                    abs_fallback = urljoin(url, fallback_url)
                    # Skip if this also looks generic
                    if not any(p.lower() in abs_fallback.lower() for p in GENERIC_IMAGE_PATTERNS):
                        original_image_url = abs_fallback
                        found_fallback = True
                        break
            if is_generic and not found_fallback:
                original_image_url = None # Force AI generation later

        image_data = None
        if original_image_url:
            try:
                # Use browser-like headers for the image request as well
                img_res = await client.get(original_image_url, headers=headers, timeout=5, follow_redirects=True)
                if img_res.status_code == 200:
                    # Expert Review Fix: Validate image data immediately
                    try:
                        test_img = Image.open(io.BytesIO(img_res.content))
                        test_img.verify() # Verify file integrity
                        image_data = img_res.content
                    except Exception as e:
                        SafeLogger.warn(f"Fetched thumbnail content is not a valid image: {e}")
            except Exception as e:
                SafeLogger.warn(f"Failed to fetch thumbnail data: {e}")

        return {
            "title": title[:100],
            "description": description[:200],
            "image": image_data,
            "image_url": original_image_url, # Pass back the public URL for Threads
            "url": url
        }
    except (httpx.HTTPError, asyncio.TimeoutError) as e:
        SafeLogger.warn(f"Network error extracting metadata for {url}: {type(e).__name__}")
        return {"title": "News Update", "description": "", "image": None, "url": url}
    except Exception as e:
        SafeLogger.warn(f"Unexpected metadata error for {url}: {type(e).__name__} - {e}")
        # Expert Review Fix: Return at least the URL instead of None
        return {"title": "News Update", "description": "", "image": None, "url": url}
