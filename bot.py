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
    "https://export.arxiv.org/rss/cs.AI"
]

BLUESKY_HANDLE = os.getenv("USERNAME")
BLUESKY_PASSWORD = os.getenv("PASS")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")

SYSTEM_INSTRUCTION = """
You are a professional AI news curator for Bluesky. 
Your task is to summarize the latest AI news into a single, engaging post.

Rules:
1. Maximum 300 characters.
2. Provide a substantive summary (at least 2-3 sentences) of the key updates.
3. CRITICAL: Your response MUST end with 1-2 relevant hashtags (e.g., #AI #Tech).
4. Be exciting but professional.
5. Provide ONLY the post content. No preambles like "Here is the summary".
6. Do not use excessive symbols, repeating characters, or emojis.
7. NEVER include literal URLs.

Format Template:
[Summary of the news items]

#Hashtag1 #Hashtag2
"""

def validate_summary(text):
    if not text:
        return False, "Empty output"
    
    # Check for excessive repetition (e.g. + 9 + 9 + 9)
    if re.search(r'(.)\1{4,}', text) or re.search(r'(\+\s*\d\s*){4,}', text):
        return False, "Detected repetitive patterns or gibberish"
    
    # Check for reasonable length (lowered slightly to 30)
    if len(text) < 30:
        return False, "Post too short"
    
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
                    all_entries.append({
                        "title": entry.title,
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

    news_text = "\n".join([f"- {item['title']} (Source: {item['source']})" for item in news_items[:10]])
    
    user_prompt = f"Summarize these news items into a single Bluesky post. You MUST include at least one hashtag (like #AI) in your response:\n\n{news_text}"
    
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.3,
        max_output_tokens=150
    )
    
    max_retries = 3
    last_summary = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=user_prompt,
                config=config
            )
            summary = response.text.strip()
            last_summary = summary
            
            # Post-generation validation
            is_valid, reason = validate_summary(summary)
            if is_valid:
                return summary
            else:
                print(f"Validation failed (Attempt {attempt + 1}): {reason}. Text: {summary[:50]}...", flush=True)
                time.sleep(2)
        except Exception as e:
            error_msg = str(e)
            if ("429" in error_msg or "503" in error_msg or "UNAVAILABLE" in error_msg) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 30
                print(f"Transient error detected. Retrying in {wait_time}s...", flush=True)
                time.sleep(wait_time)
            else:
                print(f"Error during summarization: {e}", flush=True)
                return None
    
    # Rescue logic: If we failed primarily due to missing hashtags, append them manually
    if last_summary:
        is_valid, reason = validate_summary(last_summary)
        if reason == "Missing hashtags":
            print("Applying Hashtag Rescue...", flush=True)
            rescued_summary = last_summary.strip() + " #AI #Tech"
            # Final check on character limit
            if len(rescued_summary) > 300:
                rescued_summary = rescued_summary[:297] + "..."
            return rescued_summary

    print("Failed to generate a valid summary after multiple attempts.", flush=True)
    return None

def post_to_bluesky(text):
    if not text:
        print("Nothing to post.", flush=True)
        return

    print("Posting to Bluesky...", flush=True)
    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    
    if len(text) > 300:
        text = text[:297] + "..."
        
    client.send_post(text=text)
    print("Successfully posted!", flush=True)

def main():
    if not all([BLUESKY_HANDLE, BLUESKY_PASSWORD, GEMINI_API_KEY]):
        print("Missing environment variables.", flush=True)
        return

    news = fetch_news()
    if not news:
        print("No new AI news found in the last 24 hours.", flush=True)
        return

    summary = summarize_news(news)
    if summary:
        post_to_bluesky(summary)
    else:
        print("Quality validation failed or error occurred. Post aborted for safety.", flush=True)

if __name__ == "__main__":
    main()
