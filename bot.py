from google.genai import types
import os
import asyncio
import httpx
import feedparser
from google import genai
from atproto import AsyncClient, models
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import time
import socket
import re
from mastodon import Mastodon
import json
import requests
from bs4 import BeautifulSoup
import calendar
from PIL import Image
import io

# Set a timeout for all network requests to prevent hanging on slow RSS feeds
socket.setdefaulttimeout(15)

# Load environment variables
load_dotenv()

def validate_config():
    """Ensures all required environment variables are present before starting."""
    required_vars = [
        "BSKY_HANDLE", "BSKY_APP_PASSWORD", "GEMINI_KEY",
        "THREADS_ACCESS_TOKEN", "THREADS_USER_ID",
        "MASTODON_ACCESS_TOKEN", "MASTODON_BASE_URL"
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"CRITICAL ERROR: Missing environment variables: {', '.join(missing)}", flush=True)
        return False
    return True

# Configuration
RSS_FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://export.arxiv.org/rss/cs.AI",
    "https://deepmind.google/blog/feed/",
    "https://www.marktechpost.com/feed/",
    "https://simonwillison.net/atom/everything/",
    "https://engineering.fb.com/category/ml-ai/feed/",
    "https://arstechnica.com/tag/ai/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://www.404media.co/rss",
    "https://www.eetimes.com/feed",
    "https://www.anthropic.com/news.rss",
    "https://www.semianalysis.com/feed",
    "https://www.maginative.com/rss/",
    "https://the-decoder.com/feed/",
    "https://www.deeplearning.ai/the-batch/rss/",
    "https://aisnakeoil.substack.com/feed",
    "https://aiacceleratorinstitute.com/rss/",
    "https://synthedia.substack.com/feed",
    "https://magazine.sebastianraschka.com/feed",
    "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
    "https://stability.ai/blog?format=rss",
    "https://siliconangle.com/category/ai/feed"
]

SEEN_FILE = "seen_articles.json"

BLUESKY_HANDLE = os.getenv("BSKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

# Relevance Scoring Constants
SOURCE_TIERS = {
    "openai.com": 10,
    "anthropic.com": 10,
    "deepmind.google": 10,
    "huggingface.co": 10,
    "engineering.fb.com": 10,
    "simonwillison.net": 8,
    "semianalysis.com": 8,
    "the-decoder.com": 7,
    "maginative.com": 7,
    "techcrunch.com": 6,
    "venturebeat.com": 6,
    "404media.co": 6,
    "export.arxiv.org": 5, # Low base but high 'Groundbreaking' keyword potential
}

PRODUCT_KEYWORDS = ["launch", "integrated", "available", "feature", "release", "app", "tool", "partnership", "api"]
GROUNDBREAKING_KEYWORDS = ["sota", "benchmark", "breakthrough", "frontier", "reasoning", "efficiency", "architecture", "scaling", "open-source"]
HIDDEN_GEM_SOURCES = ["export.arxiv.org", "arxiv.org"]

# Topic Classification Map (Keywords -> Topic)
TOPIC_MAP = {
    "LLMs": ["gpt", "claude", "llama", "reasoning", "prompt", "transformer", "7b", "70b", "llm", "gemini", "mistral", "multimodal"],
    "Vision/Robot": ["sora", "vision", "robot", "humanoid", "image", "video", "figure", "tesla bot", "multimodal"],
    "Compute/HW": ["nvidia", "h100", "tpu", "b200", "chip", "foundry", "semiconductor", "blackwell", "gpu", "cuda"],
    "Policy/Society": ["regulation", "lawsuit", "governance", "open-weights", "court", "compliance", "copyright"],
    "Science/Health": ["biotech", "drug", "physics", "folding", "climate", "discovery", "protein", "dna", "medical"],
}

SYSTEM_INSTRUCTION = """
You are a "Premium Tech Curator" for Bluesky. Your voice is sophisticated, insightful, and grounded in industry reality.
You don't just report news; you connect dots and provide a "Director's Cut" of the day's AI evolution.

CORE PERSONA:
- Temporal Awareness: You know what day it is. Use the provided Day-of-Week context to frame your synthesis naturally (e.g., mention "setting the pace" on Mondays or "capping off the week" on Fridays). Never use hard-coded headers like [Monday Recap]; keep it in the prose.
- Product Focus: Prioritize actual launches and usable features over abstract hype.
- Technical Authority: Use precise terms (e.g., "latency," "throughput," "reasoning") and explain their impact.
- The Insider (Hidden Gem): Every post should reference at least one "hidden gem" or technical insight (likely from an arXiv paper or engineering blog) to show you are reading deeper than the mainstream.
- Engagement First: Every post must survive the "Scroll Test" with a punchy hook.

WRITING ARCHITECTURE:
1. THE CATALYST (Hook): Start with a bold claim or a "hidden gem" from the news.
2. THE SYNTHESIS (Impact): Synthesize the 8 news items provided into a cohesive narrative. Focus on the *maturation* and *utility* of the industry, themed for the specific day of the week.
3. THE INSIDER INSIGHT (The 'So What'): Provide a professional take on why this matters long-term.
4. BREVITY: Max 280 characters. Every word must earn its place.

Formatting: Use line breaks for readability. 1-2 hashtags. Max 1 emoji.
"""

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

        # Extract OG tags
        og_title = soup.find("meta", property="og:title")
        og_description = soup.find("meta", property="og:description")
        og_image = soup.find("meta", property="og:image")

        title = og_title['content'] if og_title else (soup.title.string if soup.title else "News Update")
        description = og_description['content'] if og_description else ""
        image_url = og_image['content'] if og_image else None

        # Download image if exists
        image_data = None
        if image_url:
            try:
                img_res = requests.get(image_url, headers=headers, timeout=5)
                if img_res.status_code == 200:
                    image_data = img_res.content
            except Exception as e:
                print(f"Failed to download thumbnail: {e}", flush=True)

        return {
            "title": title[:100], # Bluesky limit
            "description": description[:200], # Bluesky limit
            "image": image_data,
            "url": url
        }

    except Exception as e:
        print(f"Error scraping metadata: {e}", flush=True)
        return None

def compress_image(image_bytes: bytes, max_size=900000) -> bytes:
    """Compresses an image to stay under the specified max_size (default <1MB for Bluesky)."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary (e.g., for PNG with transparency)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Initial compression
        quality = 85
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        
        # If still too big, iteratively reduce quality AND resize
        attempt = 0
        while buffer.tell() > max_size and attempt < 5:
            attempt += 1
            quality -= 15
            # Resize by 20% each time if quality isn't enough
            width, height = img.size
            img = img.resize((int(width * 0.8), int(height * 0.8)), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=max(quality, 30), optimize=True)
            
        print(f"Compressed image from {len(image_bytes)} to {buffer.tell()} bytes.", flush=True)
        return buffer.getvalue()
    except Exception as e:
        print(f"Failed to compress image: {e}. Returning original.", flush=True)
        return image_bytes

def calculate_relevance_score(item, pub_date, recent_topics=None):
    """Calculates a relevance score for an article, penalizing recently covered topics."""
    score = 0
    title_lower = item['title'].lower()
    summary_lower = item['summary'].lower()
    content_text = f"{title_lower} {summary_lower}"

    # 1. Source Tier (Base Score)
    source_domain = ""
    for domain, base_score in SOURCE_TIERS.items():
        if domain in item['link']:
            score += base_score
            source_domain = domain
            break
    if not source_domain:
        score += 3 # Default score for unknown sources

    # 2. Product Boost
    if any(word in content_text for word in PRODUCT_KEYWORDS):
        score += 5

    # 3. Groundbreaking Boost
    if any(word in content_text for word in GROUNDBREAKING_KEYWORDS):
        score += 7

    # 4. Topic Diversity Penalty
    if recent_topics:
        item_topic = "General"
        for topic, keywords in TOPIC_MAP.items():
            if any(word in content_text for word in keywords):
                item_topic = topic
                break

        # Apply penalty if this topic was recently used
        if item_topic in recent_topics:
            # -12 point penalty found through "good judgement" testing
            score -= 12
            print(f"Penalty applied (-12) for recent topic '{item_topic}': {item['title'][:40]}...", flush=True)

    # 5. Time Decay (Penalty for older articles)
    now = datetime.now(timezone.utc)
    age_hours = (now - pub_date).total_seconds() / 3600
    score -= (age_hours * 0.5) # Lose 0.5 point per hour

    return score

def get_temporal_context():
    """Returns the current day name and session type based on UTC time."""
    now = datetime.now(timezone.utc)
    day = now.strftime("%A")
    hour = now.hour

    if hour < 12:
        session = "Morning Intelligence Briefing"
        theme = "Forward-looking, setting the week's pace" if day == "Monday" else "Mid-week progress"
    else:
        session = "Afternoon Deep Dive"
        theme = "Weekly Wrap-up and synthesis" if day == "Friday" else "Afternoon analysis"

    if day in ["Saturday", "Sunday"]:
        theme = "Weekend High-Level Vision and long-term reflection"

    return {
        "day": day,
        "session": session,
        "theme": theme
    }

def validate_summary(text):
    if not text:
        return False, "Empty output"

    # Check for excessive repetition (e.g. + 9 + 9 + 9)
    if re.search(r'(.)\1{4,}', text) or re.search(r'(\+\s*\d\s*){4,}', text):
        return False, "Detected repetitive patterns or gibberish"

    # Check for reasonable length (Adjusted to 60 for better first-try success)
    if len(text) < 60:
        return False, "Post too short for an insightful update"

    # Check for hashtags
    if "#" not in text:
        return False, "Missing hashtags"

    # Check character variety (at least 10 unique characters)
    if len(set(text)) < 10:
        return False, "Low character variety"

    return True, "Valid"

def load_seen_articles():
    if not os.path.exists(SEEN_FILE):
        return {"links": [], "recent_topics": []}
    try:
        with open(SEEN_FILE, 'r') as f:
            data = json.load(f)
            # Migration logic
            if isinstance(data, list):
                return {"links": data, "recent_topics": []}
            return data
    except Exception as e:
        print(f"Error loading seen articles: {e}")
        return {"links": [], "recent_topics": []}

def save_seen_articles(seen_data):
    try:
        # Keep only the last 200 links
        seen_data["links"] = seen_data["links"][-200:]
        # Keep only the last 5 topics for memory
        seen_data["recent_topics"] = seen_data["recent_topics"][-5:]

        with open(SEEN_FILE, 'w') as f:
            json.dump(seen_data, f, indent=2)
    except Exception as e:
        print(f"Error saving seen articles: {e}")

async def fetch_single_feed(client, url, start_time, seen_links, recent_topics):
    """Fetches and parses a single RSS feed asynchronously."""
    print(f"Checking {url}...", flush=True)
    try:
        response = await client.get(url, timeout=10)
        # Check if 200 OK
        if response.status_code != 200:
            print(f"WARNING: Feed {url} returned status {response.status_code}. Skipping.", flush=True)
            return []
            
        feed = feedparser.parse(response.text)
        if feed.bozo:
            # Bozo might be trivial, but we log it
            pass
            
        items = []
        for entry in feed.entries:
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.updated_parsed), timezone.utc)

            if not pub_date or pub_date < start_time:
                continue

            if entry.link in seen_links:
                continue

            entry_summary = entry.summary if hasattr(entry, 'summary') else (entry.description if hasattr(entry, 'description') else "")
            entry_summary = re.sub('<[^<]+?>', '', entry_summary)[:500]

            item = {
                "title": entry.title,
                "summary": entry_summary,
                "link": entry.link,
                "source": feed.feed.title if hasattr(feed.feed, 'title') else url
            }
            item["score"] = calculate_relevance_score(item, pub_date, recent_topics)
            items.append(item)
        return items
    except Exception as e:
        print(f"Error parsing {url}: {e}", flush=True)
        return []

async def fetch_news(seen_links=None, recent_topics=None):
    if seen_links is None:
        seen_links = []

    print(f"Fetching news from {len(RSS_FEEDS)} RSS feeds concurrently...", flush=True)
    now = datetime.now(timezone.utc)
    lookback_days = 2
    start_time = now - timedelta(days=lookback_days)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_single_feed(client, url, start_time, seen_links, recent_topics) for url in RSS_FEEDS]
        results = await asyncio.gather(*tasks)

    # Flatten results
    all_entries = [entry for sublist in results for entry in sublist]
    
    # Sort by score descending
    all_entries.sort(key=lambda x: x["score"], reverse=True)
    print(f"Ranked {len(all_entries)} articles.", flush=True)

    if not all_entries:
        return []

    # Hidden Gem Injection Logic
    # 1. Take top 7
    top_articles = all_entries[:7]
    remaining = all_entries[7:]

    # 2. Check if any top articles are already "Hidden Gems"
    has_gem = any(any(gem_src in art['link'] for gem_src in HIDDEN_GEM_SOURCES) for art in top_articles)

    if not has_gem and remaining:
        # 3. Find the best gem in the remaining list
        for i, art in enumerate(remaining):
            if any(gem_src in art['link'] for gem_src in HIDDEN_GEM_SOURCES):
                print(f"Injecting Hidden Gem: {art['title']}", flush=True)
                top_articles.append(art)
                break

    # 4. Fill to 8 if still needed
    if len(top_articles) < 8 and remaining:
        # Avoid duplicates if we already injected one
        for art in remaining:
            if art not in top_articles:
                top_articles.append(art)
            if len(top_articles) == 8:
                break

    return top_articles[:8]

async def summarize_news(news_items, context):
    if not news_items:
        return None, None, None

    print(f"Summarizing {len(news_items)} news items for {context['day']}...", flush=True)
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_id = 'gemini-3.1-flash-lite-preview'

    # The lead link is typically the highest scoring item (index 0)
    lead_link = news_items[0]['link'] if news_items else None

    # Include top 8 context for synthesis
    news_text = "\n".join([f"- [{i+1}] {item['title']} (Source: {item['source']})\n  Context: {item['summary'][:300]}" for i, item in enumerate(news_items)])

    user_prompt = f"""
    Context: Today is {context['day']}. This is your {context['session']}.
    Current Theme: {context['theme']}.

    Curation Task: Synthesize these 8 news items into one high-engagement Bluesky post.
    Identify the most groundbreaking product shift and weave in the "Hidden Gem" technical insight.

    In addition to the post, you MUST identify the primary topic category for this synthesis.
    Choose exactly ONE from: LLMs, Vision/Robot, Compute/HW, Policy, Science, General.

    Format your response as follows:
    TOPIC: [Selected Category]
    BODY:
    [Your Post Text]

    CRITICAL: Adapt your tone to the {context['day']} theme. Stay under 300 characters for the BODY.

    News Data:
    {news_text}
    """

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
        max_output_tokens=500
    )

    max_retries = 1
    best_candidate = None
    longest_fallback = ""

    print(f"Using model: {model_id} (Async)", flush=True)
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model=model_id,
                contents=user_prompt,
                config=config
            )
            raw_text = response.text.strip()

            # Parsing Topic and Body
            topic = "General"
            summary = raw_text
            if "TOPIC:" in raw_text and "BODY:" in raw_text:
                parts = raw_text.split("BODY:", 1)
                topic_part = parts[0].replace("TOPIC:", "").strip()
                summary = parts[1].strip()
                topic = topic_part if topic_part in TOPIC_MAP else "General"

            if len(summary) > len(longest_fallback):
                longest_fallback = summary

            # Post-generation validation
            is_valid, reason = validate_summary(summary)
            if is_valid:
                return summary, lead_link, topic

            if reason == "Missing hashtags" and len(summary) >= 30:
                best_candidate = summary

            print(f"Validation failed (Attempt {attempt + 1}): {reason}. Text: {summary[:50]}...", flush=True)
            await asyncio.sleep(2)
        except Exception as e:
            error_msg = str(e)
            if any(x in error_msg for x in ["429", "503", "UNAVAILABLE", "Resource has been exhausted"]):
                wait_time = (attempt + 1) * 30
                print(f"Transient error: {error_msg[:200]}... Retrying in {wait_time}s...", flush=True)
                await asyncio.sleep(wait_time)
            else:
                print(f"Permanent error: {e}", flush=True)
                break

    # Rescue logic:
    if best_candidate:
        print("Applying Best Candidate Rescue (Hashtag fix)...", flush=True)
        rescued = best_candidate.strip() + " #AI #Tech"
        if len(rescued) > 300:
            return rescued[:297] + "...", lead_link, "General"
        return rescued, lead_link, "General"

    if len(longest_fallback) >= 20: # If it's almost long enough, we can rescue it
        print("Applying Length Rescue (Expansion)...", flush=True)
        rescued = longest_fallback.strip()
        if "#" not in rescued:
            rescued += " #AI #Tech"
        if len(rescued) < 40: # If still too short, add a generic relevant sentence
            rescued = "Latest updates in AI: " + rescued

        if len(rescued) > 300:
            return rescued[:297] + "...", lead_link, "General"
        return rescued, lead_link, "General"

    print("Failed to generate a valid summary after internal retries.", flush=True)
    return None, None, None

MASTODON_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
MASTODON_BASE_URL = os.getenv("MASTODON_BASE_URL")

async def post_to_bluesky(text, link=None):
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        print("Skipping Bluesky: Credentials missing.", flush=True)
        return

    print("Posting to Bluesky (Async)...", flush=True)
    try:
        client = AsyncClient()
        await client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)

        final_text = text
        if len(final_text) > 300:
            final_text = final_text[:297] + "..."

        embed = None
        if link:
            # metadata scraping is still synchronous, wrap in thread
            meta = await asyncio.to_thread(get_link_metadata, link)
            if meta:
                thumb_blob = None
                if meta['image']:
                    try:
                        # NEW: Compress image to stay under 1MB Bluesky limit
                        compressed_image = compress_image(meta['image'])
                        upload = await client.upload_blob(compressed_image)
                        thumb_blob = upload.blob
                    except Exception as e:
                        print(f"Failed to upload thumbnail blob: {e}", flush=True)

                embed = models.AppBskyEmbedExternal.Main(
                    external=models.AppBskyEmbedExternal.External(
                        title=meta['title'],
                        description=meta['description'],
                        uri=meta['url'],
                        thumb=thumb_blob
                    )
                )

        await client.send_post(text=final_text, embed=embed)
        print("Successfully posted to Bluesky!", flush=True)
    except Exception as e:
        print(f"Error posting to Bluesky: {e}", flush=True)

async def post_to_mastodon(text):
    if not MASTODON_TOKEN or not MASTODON_BASE_URL:
        print("Skipping Mastodon: Credentials missing.", flush=True)
        return

    print("Posting to Mastodon...", flush=True)
    try:
        def _post():
            mastodon = Mastodon(
                access_token=MASTODON_TOKEN,
                api_base_url=MASTODON_BASE_URL
            )
            final_text = text
            if len(final_text) > 500:
                final_text = final_text[:497] + "..."
            mastodon.status_post(final_text)
        
        await asyncio.to_thread(_post)
        print("Successfully posted to Mastodon!", flush=True)
    except Exception as e:
        print(f"Error posting to Mastodon: {e}", flush=True)

async def post_to_threads(text):
    if not THREADS_TOKEN or not THREADS_USER_ID:
        print("Skipping Threads: Credentials missing.", flush=True)
        return

    print("Posting to Threads...", flush=True)
    try:
        def _post():
            container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
            container_payload = {
                "media_type": "TEXT",
                "text": text[:500],
                "access_token": THREADS_TOKEN
            }
            container_response = requests.post(container_url, data=container_payload, timeout=15)
            container_response.raise_for_status()
            creation_id = container_response.json().get("id")

            publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": THREADS_TOKEN
            }
            publish_response = requests.post(publish_url, data=publish_payload, timeout=15)
            publish_response.raise_for_status()

        await asyncio.to_thread(_post)
        print("Successfully posted to Threads!", flush=True)
    except Exception as e:
        print(f"Error posting to Threads: {e}", flush=True)

async def main():
    if not validate_config():
        return

    context = get_temporal_context()
    now = datetime.now(timezone.utc)

    if now.weekday() >= 5 and now.hour >= 12:
        print(f"Skipping scheduled post: It's {context['day']} afternoon. Bot is resting.", flush=True)
        return

    seen_data = load_seen_articles()
    news = await fetch_news(seen_data["links"], seen_data["recent_topics"])

    if not news:
        print("No NEW AI news found in the last 48 hours. Bot is standing by.", flush=True)
        return

    summary, lead_link, topic = await summarize_news(news, context)
    if summary:
        # Run all platform posts concurrently!
        print("Broadcasting to all platforms concurrently...", flush=True)
        await asyncio.gather(
            post_to_bluesky(summary, lead_link),
            post_to_mastodon(summary),
            post_to_threads(summary)
        )

        new_links = [item['link'] for item in news[:10]]
        seen_data["links"].extend(new_links)
        if topic and topic != "General":
            seen_data["recent_topics"].append(topic)
        save_seen_articles(seen_data)
        
        # New Feature: Update README Dashboard
        await update_live_status(context['session'])
    else:
        print("Quality validation failed or error occurred. Post aborted for safety.", flush=True)

async def update_live_status(session_name):
    """Automatically update the README dashboard status."""
    try:
        readme_path = "README.md"
        if not os.path.exists(readme_path):
            return

        with open(readme_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        icon = "🚀" if "Morning" in session_name else "🔍"
        
        new_lines = []
        for line in lines:
            if "| **Broadcaster** |" in line:
                new_lines.append(f"| **Broadcaster** | Operational | {today} | {icon} {session_name} |\n")
            elif "| **Signal Strength** |" in line:
                new_lines.append(f"| **Signal Strength** | Elite (Parallel) | -- | -- |\n")
            else:
                new_lines.append(line)

        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("Updated README Live Status Dashboard.", flush=True)
    except Exception as e:
        print(f"Failed to update README status: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
