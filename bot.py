from google.genai import types
import os
import feedparser
from google import genai
from atproto import Client, client_utils, models
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import time
import socket
import re
from mastodon import Mastodon
import json
import requests
from bs4 import BeautifulSoup
import io

# Set a timeout for all network requests to prevent hanging on slow RSS feeds
socket.setdefaulttimeout(15)

# Load environment variables
load_dotenv()

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

SYSTEM_INSTRUCTION = """
You are a "Premium Tech Curator" for Bluesky. Your voice is sophisticated, insightful, and slightly ahead of the curve.
You don't just report news; you connect dots and provide a "Director's Cut" of the day's AI evolution.

CORE PERSONA:
- Constructive Optimism: Every technical shift is a step toward a more capable future. 
- Technical Authority: Use precise terms (e.g., "latency," "throughput," "alignment") but explain their weight.
- Engagement First: Every post must survive the "Scroll Test."

WRITING ARCHITECTURE:
1. THE CATALYST (Hook): Start with a bold claim or a "hidden gem" from the news. Avoid generic "Latest news..." starts.
2. THE SYNTHESIS (Impact): Synthesize news into a narrative. Focus on the *maturation* of the industry.
3. THE INSIDER INSIGHT (The 'So What'): Provide a professional take on why this matters long-term.
4. BREVITY: Max 280 characters. Every word must earn its place.

Formatting: Use line breaks for readability. 1-2 hashtags. Max 1 emoji.

Example 1: "The era of 'massive' AI is giving way to 'efficient' AI. With TriAttention boosting throughput by 2.5x, the focus has shifted to deployment at the edge. We're moving from model-building to model-application. This is where value is actually unlocked. ⚡ #AI #TechTrends"
Example 2: "AI safety is maturing into AI governance. Recent 'proactive red-teaming' standards highlight a shift from reactive patches to systematic alignment. By setting these boundaries now, the industry is paving the way for enterprise-grade trust. Professionalization is here. #AISafety #Tech"
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
        return []
    try:
        with open(SEEN_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading seen articles: {e}")
        return []

def save_seen_articles(seen_links):
    try:
        # Keep only the last 200 links to manage file size
        with open(SEEN_FILE, 'w') as f:
            json.dump(seen_links[-200:], f, indent=2)
    except Exception as e:
        print(f"Error saving seen articles: {e}")

def fetch_news(seen_links=None):
    if seen_links is None:
        seen_links = []
        
    print("Fetching news from RSS feeds...", flush=True)
    all_entries = []
    now = datetime.now(timezone.utc)
    lookback_days = 2 # Increased from 1 to 2 for better coverage with dedup
    start_time = now - timedelta(days=lookback_days)

    for url in RSS_FEEDS:
        print(f"Checking {url}...", flush=True)
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed), timezone.utc)
                
                if entry.link in seen_links:
                    continue

                if pub_date and pub_date > start_time:
                    entry_summary = entry.summary if hasattr(entry, 'summary') else (entry.description if hasattr(entry, 'description') else "")
                    # Clean HTML tags if any from summary
                    entry_summary = re.sub('<[^<]+?>', '', entry_summary)[:300]
                    
                    all_entries.append({
                        "title": entry.title,
                        "summary": entry_summary,
                        "link": entry.link,
                        "source": feed.feed.title if hasattr(feed.feed, 'title') else url
                    })
        except Exception as e:
            print(f"Error parsing {url}: {e}", flush=True)

    print(f"Found {len(all_entries)} articles after filtering.", flush=True)
    return all_entries

def summarize_news(news_items):
    if not news_items:
        return None, None

    print(f"Summarizing {len(news_items)} news items...", flush=True)
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_id = 'gemini-3.1-flash-lite-preview'

    # The lead link is typically the first item (highest signal)
    lead_link = news_items[0]['link'] if news_items else None
    
    # Include summary context for better output
    news_text = "\n".join([f"- {item['title']} (Source: {item['source']})\n  Context: {item['summary']}" for item in news_items[:10]])
    
    user_prompt = f"""
    Curation Task: Synthesize the following news into one high-engagement Bluesky post.
    Start with a hook, explain the impact, and offer a specific insight.
    
    CRITICAL: Stay under 300 characters. End with 1-2 hashtags.
    
    News Data:
    {news_text}
    """
    
    # Re-enabling system instructions for Gemini models
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
        max_output_tokens=300
    )
    
    max_retries = 1 # Minimal retries to protect quota
    best_candidate = None # Best one regardless of hashtags
    longest_fallback = "" # Longest one found if everything is too short

    print(f"Using model: {model_id}", flush=True)
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=user_prompt,
                config=config
            )
            summary = response.text.strip()
            
            if len(summary) > len(longest_fallback):
                longest_fallback = summary

            # Post-generation validation
            is_valid, reason = validate_summary(summary)
            if is_valid:
                return summary, lead_link
            
            # Tracking "best candidate" (Valid length/quality except for missing hashtags)
            if reason == "Missing hashtags" and len(summary) >= 30:
                best_candidate = summary
            
            print(f"Validation failed (Attempt {attempt + 1}): {reason}. Text: {summary[:50]}...", flush=True)
            time.sleep(2)
        except Exception as e:
            error_msg = str(e)
            if any(x in error_msg for x in ["429", "503", "UNAVAILABLE", "Resource has been exhausted"]):
                wait_time = (attempt + 1) * 30
                print(f"Transient error: {error_msg[:200]}... Retrying in {wait_time}s...", flush=True)
                time.sleep(wait_time)
            else:
                print(f"Permanent error: {e}", flush=True)
                break 

    # Rescue logic:
    if best_candidate:
        print("Applying Best Candidate Rescue (Hashtag fix)...", flush=True)
        rescued = best_candidate.strip() + " #AI #Tech"
        if len(rescued) > 300:
            return rescued[:297] + "...", lead_link
        return rescued, lead_link
    
    if len(longest_fallback) >= 20: # If it's almost long enough, we can rescue it
        print("Applying Length Rescue (Expansion)...", flush=True)
        rescued = longest_fallback.strip()
        if "#" not in rescued:
            rescued += " #AI #Tech"
        if len(rescued) < 40: # If still too short, add a generic relevant sentence
            rescued = "Latest updates in AI: " + rescued
        
        if len(rescued) > 300:
            return rescued[:297] + "...", lead_link
        return rescued, lead_link

    print("Failed to generate a valid summary after internal retries.", flush=True)
    return None, None

MASTODON_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
MASTODON_BASE_URL = os.getenv("MASTODON_BASE_URL")

def post_to_bluesky(text, link=None):
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        print("Skipping Bluesky: Credentials missing.", flush=True)
        return

    print("Posting to Bluesky...", flush=True)
    try:
        client = Client()
        client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        
        # Bluesky has a 300 character limit
        final_text = text
        if len(final_text) > 300:
            final_text = final_text[:297] + "..."
            
        embed = None
        if link:
            meta = get_link_metadata(link)
            if meta:
                thumb_blob = None
                if meta['image']:
                    try:
                        upload = client.com.atproto.repo.upload_blob(meta['image'])
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

        client.send_post(text=final_text, embed=embed)
        print("Successfully posted to Bluesky!", flush=True)
    except Exception as e:
        print(f"Error posting to Bluesky: {e}", flush=True)

def post_to_mastodon(text):
    if not MASTODON_TOKEN or not MASTODON_BASE_URL:
        print("Skipping Mastodon: Credentials missing.", flush=True)
        return

    print("Posting to Mastodon...", flush=True)
    try:
        mastodon = Mastodon(
            access_token=MASTODON_TOKEN,
            api_base_url=MASTODON_BASE_URL
        )
        # Mastodon standard limit is 500 characters
        final_text = text
        if len(final_text) > 500:
            final_text = final_text[:497] + "..."
            
        mastodon.status_post(final_text)
        print("Successfully posted to Mastodon!", flush=True)
    except Exception as e:
        print(f"Error posting to Mastodon: {e}", flush=True)

def post_to_threads(text):
    if not THREADS_TOKEN or not THREADS_USER_ID:
        print("Skipping Threads: Credentials missing.", flush=True)
        return

    print("Posting to Threads...", flush=True)
    try:
        # Step 1: Create Media Container
        container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
        container_payload = {
            "media_type": "TEXT",
            "text": text[:500], # Threads limit is 500
            "access_token": THREADS_TOKEN
        }
        
        container_response = requests.post(container_url, data=container_payload)
        container_response.raise_for_status()
        creation_id = container_response.json().get("id")
        
        # Step 2: Publish Container
        publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": THREADS_TOKEN
        }
        
        # Threads recommends waiting a bit, but for text-only it's usually instant
        publish_response = requests.post(publish_url, data=publish_payload)
        publish_response.raise_for_status()
        print("Successfully posted to Threads!", flush=True)
        
    except Exception as e:
        print(f"Error posting to Threads: {e}", flush=True)
        if hasattr(e, 'response') and e.response is not None:
             print(f"Threads API Error Trace: {e.response.text}", flush=True)

def main():
    if not GEMINI_API_KEY:
        print("Missing Gemini API Key.", flush=True)
        return

    seen_links = load_seen_articles()
    news = fetch_news(seen_links)
    
    if not news:
        print("No NEW AI news found in the last 48 hours. Bot is standing by.", flush=True)
        return

    summary, lead_link = summarize_news(news)
    if summary:
        # Post to all enabled platforms
        post_to_bluesky(summary, lead_link)
        post_to_mastodon(summary)
        post_to_threads(summary)
        
        # Save the new articles to seen list
        new_links = [item['link'] for item in news[:10]]
        seen_links.extend(new_links)
        save_seen_articles(seen_links)
    else:
        print("Quality validation failed or error occurred. Post aborted for safety.", flush=True)

if __name__ == "__main__":
    main()
