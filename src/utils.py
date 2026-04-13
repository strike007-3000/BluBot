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
from PIL import Image
from .config import MAX_API_RETRIES, BACKOFF_FACTOR, JITTER_RANGE, SEEN_FILE_PATH

class SafeLogger:
    """Utility to log messages while masking sensitive tokens and secrets."""
    
    # Regex to catch access_token, app_password, or generic tokens in URLs/Strings
    FORBIDDEN_PATTERNS = [
        r"(access_token=)[^&]+",
        r"(access_token\":\s*\")[^\"]+",
        r"(password\":\s*\")[^\"]+",
        r"(THREADS_ACCESS_TOKEN=)[^&]+"
    ]

    @staticmethod
    def sanitize(message):
        text = str(message)
        for pattern in SafeLogger.FORBIDDEN_PATTERNS:
            text = re.sub(pattern, r"\1[MASKED]", text, flags=re.IGNORECASE)
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
    """Scrapes OpenGraph metadata using a shared httpx client."""
    SafeLogger.info(f"Scraping metadata: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = await client.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        og_title = soup.find("meta", property="og:title")
        og_description = soup.find("meta", property="og:description")
        og_image = soup.find("meta", property="og:image")

        title = og_title['content'] if og_title else (soup.title.string if soup.title else "News Update")
        description = og_description['content'] if og_description else ""
        image_url = og_image['content'] if og_image else None

        image_data = None
        if image_url:
            try:
                img_res = await client.get(image_url, headers=headers, timeout=5)
                if img_res.status_code == 200:
                    image_data = img_res.content
            except Exception: pass

        return {
            "title": title[:100],
            "description": description[:200],
            "image": image_data,
            "url": url
        }
    except Exception:
        return None
