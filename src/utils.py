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
from .config import MAX_API_RETRIES, BACKOFF_FACTOR, JITTER_RANGE, SEEN_FILE_PATH

class SafeLogger:
    """Utility to log messages while masking sensitive tokens and secrets."""
    
    # Pre-compiled list of regexes for common token patterns
    FORBIDDEN_PATTERNS = [
        r"(access_token=)[^&]+",
        r"(access_token\":\s*\")[^\"]+",
        r"(password\":\s*\")[^\"]+",
        r"(THREADS_ACCESS_TOKEN=)[^&]+"
    ]

    @staticmethod
    def sanitize(message):
        text = str(message)
        # 1. Static pattern masking
        for pattern in SafeLogger.FORBIDDEN_PATTERNS:
            text = re.sub(pattern, r"\1[MASKED]", text, flags=re.IGNORECASE)
        
        # 2. Dynamic environment variable masking
        sensitive_keys = ["KEY", "TOKEN", "PASSWORD", "SECRET"]
        for k, v in os.environ.items():
            if any(s in k.upper() for s in sensitive_keys) and v and len(v) > 5:
                text = text.replace(v, "[MASKED]")
        return text

    @staticmethod
    def info(message):
        print(f"INFO: {SafeLogger.sanitize(message)}", flush=True)

    @staticmethod
    def warn(message):
        print(f"WARNING: {SafeLogger.sanitize(message)}", flush=True)

    @staticmethod
    def error(message):
        print(f"ERROR: {SafeLogger.sanitize(message)}", flush=True)

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
                SafeLogger.warn(f"Retry {retries}/{MAX_API_RETRIES} for {func.__name__} in {wait_time:.2f}s... (Error: {str(e)[:100]})")
                await asyncio.sleep(wait_time)
    return wrapper

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
        SafeLogger.error(f"Failed to compress image: {e}")
        return image_bytes

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
        except Exception as e:
            SafeLogger.error(f"Error loading seen articles: {e}")
    return {"links": [], "recent_topics": []}

def save_seen_articles(data):
    """Saves updated memory to the absolute SEEN_FILE_PATH."""
    try:
        # Retention management
        data["links"] = data["links"][-500:]
        data["recent_topics"] = data["recent_topics"][-20:]
        with open(SEEN_FILE_PATH, "w") as f:
            json.dump(data, f, indent=4)
        SafeLogger.info(f"Saved {len(data['links'])} seen articles.")
    except Exception as e:
        SafeLogger.error(f"Error saving seen articles: {e}")

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
        
        if image_url:
            # Resolve relative URLs (common on arXiv and others)
            image_url = urljoin(url, image_url)

        image_data = None
        if image_url:
            try:
                # Use browser-like headers for the image request as well
                img_res = await client.get(image_url, headers=headers, timeout=5, follow_redirects=True)
                if img_res.status_code == 200:
                    image_data = img_res.content
            except Exception as e:
                SafeLogger.warn(f"Failed to fetch thumbnail data: {e}")

        return {
            "title": title[:100],
            "description": description[:200],
            "image": image_data,
            "url": url
        }
    except Exception as e:
        SafeLogger.warn(f"Partial metadata extraction for {url}: {type(e).__name__} - {e}")
        # Expert Review Fix: Return at least the URL instead of None
        return {"title": "News Update", "description": "", "image": None, "url": url}
