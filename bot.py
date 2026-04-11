from google.genai import types
import os
import feedparser
from google import genai
from atproto import Client, client_utils
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import time
import socket
import re
from mastodon import Mastodon
import requests

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
    "https://arstechnica.com/tag/ai/feed/"
]

BLUESKY_HANDLE = os.getenv("BSKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

SYSTEM_INSTRUCTION = """
You are a high-engagement AI news curator for Bluesky with a focus on constructive optimism.
Your goal is to turn technical news into "must-read" updates that highlight the growth, maturation, and potential of AI.

Writing Style Guidelines:
1. THE HOOK: Start with a punchy, interesting first sentence that highlights a major shift.
2. THE IMPACT: Briefly explain the "So What?" – focusing on how this advances the industry.
3. THE INSIGHT: Offer a professional, constructive observation. Avoid "doom and gloom" or overly negative framing.
4. POSITIVE ALIGNMENT: Even when news is about "scratches" or "bans," frame it as the industry maturing, becoming safer, or refining its boundaries. 
5. BREVITY: Keep it under 300 characters. Density is key. 
6. NO REPETITION: Do not just list headlines. Curate the meaning.

Gold Standard Examples:
Example 1: AI safety is maturing fast. Altman's latest comments on "proactive red-teaming" signal a new era of responsible development. By prioritizing alignment over raw scaling, OpenAI is building the trust needed for mass adoption. Is this the blueprint for the next decade of AI ethics? #AI #OpenAI
Example 2: Local AI just got a massive performance boost. Hugging Face's 4-bit quantization breakthrough means you can now run professional-grade LLMs on consumer hardware. This is a huge win for privacy and standardizes high-power AI at the edge. #OpenSource #EdgeComputing
"""

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

def fetch_news():
    print("Fetching news from RSS feeds...", flush=True)
    all_entries = []
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)

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
                
                if pub_date and pub_date > one_day_ago:
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
    
    return all_entries

def summarize_news(news_items):
    if not news_items:
        return None

    print(f"Summarizing {len(news_items)} news items...", flush=True)
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_id = 'gemini-3.1-flash-lite-preview'

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
                return summary
            
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
            return rescued[:297] + "..."
        return rescued
    
    if len(longest_fallback) >= 20: # If it's almost long enough, we can rescue it
        print("Applying Length Rescue (Expansion)...", flush=True)
        rescued = longest_fallback.strip()
        if "#" not in rescued:
            rescued += " #AI #Tech"
        if len(rescued) < 40: # If still too short, add a generic relevant sentence
            rescued = "Latest updates in AI: " + rescued
        
        if len(rescued) > 300:
            return rescued[:297] + "..."
        return rescued

    print("Failed to generate a valid summary after internal retries.", flush=True)
    return None

MASTODON_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
MASTODON_BASE_URL = os.getenv("MASTODON_BASE_URL")

def post_to_bluesky(text):
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
            
        client.send_post(text=final_text)
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

    news = fetch_news()
    if not news:
        print("No new AI news found in the last 24 hours.", flush=True)
        return

    summary = summarize_news(news)
    if summary:
        # Post to all enabled platforms
        post_to_bluesky(summary)
        post_to_mastodon(summary)
        post_to_threads(summary)
    else:
        print("Quality validation failed or error occurred. Post aborted for safety.", flush=True)

if __name__ == "__main__":
    main()
