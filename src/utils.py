import os
import json
import asyncio
import functools
import random
import io
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from PIL import Image
from .config import MAX_API_RETRIES, BACKOFF_FACTOR, JITTER_RANGE

SEEN_ARTICLES_FILE = "seen_articles.json"

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
                    print(f"ERROR: Ultimate failure in {func.__name__} after {MAX_API_RETRIES} attempts: {e}", flush=True)
                    raise e
                
                # Calculate sleep with jitter
                wait_time = (BACKOFF_FACTOR ** retries) + random.uniform(0, JITTER_RANGE)
                print(f"WARNING: Retry {retries}/{MAX_API_RETRIES} for {func.__name__} in {wait_time:.2f}s... (Error: {str(e)[:100]})", flush=True)
                await asyncio.sleep(wait_time)
    return wrapper

def compress_image(image_bytes: bytes, max_size=900000) -> bytes:
    """Compresses an image to stay under the specified max_size (default <1MB for Bluesky)."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary
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
            
        print(f"Compressed image from {len(image_bytes)} to {buffer.tell()} bytes.", flush=True)
        return buffer.getvalue()
    except Exception as e:
        print(f"Failed to compress image: {e}. Returning original.", flush=True)
        return image_bytes

def load_seen_articles():
    """Loads the list of already processed article links and topic memory."""
    if os.path.exists(SEEN_ARTICLES_FILE):
        try:
            with open(SEEN_ARTICLES_FILE, "r") as f:
                data = json.load(f)
                # Migration check: Ensure recent_topics exists
                if "recent_topics" not in data:
                    data["recent_topics"] = []
                return data
        except Exception as e:
            print(f"Error loading seen articles: {e}")
    return {"links": [], "recent_topics": []}

def save_seen_articles(data):
    """Saves the updated seen articles and topic memory."""
    try:
        # Keep only the last 500 links to manage file size
        data["links"] = data["links"][-500:]
        # Keep only the last 20 topics
        data["recent_topics"] = data["recent_topics"][-20:]
        with open(SEEN_ARTICLES_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Saved {len(data['links'])} seen articles to {SEEN_ARTICLES_FILE}", flush=True)
    except Exception as e:
        print(f"Error saving seen articles: {e}")

def get_link_metadata(url):
    """Scrapes OpenGraph metadata from a URL."""
    print(f"Scraping metadata for: {url}", flush=True)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
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
                img_res = requests.get(image_url, headers=headers, timeout=5)
                if img_res.status_code == 200:
                    image_data = img_res.content
            except Exception:
                pass

        return {
            "title": title[:100],
            "description": description[:200],
            "image": image_data,
            "url": url
        }
    except Exception:
        return None
