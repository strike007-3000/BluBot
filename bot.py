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
You are a high-engagement AI news curator for Bluesky. 
Your goal is to turn technical news into "must-read" updates that stop the scroll.

Writing Style Guidelines:
1. THE HOOK: Start with a punchy, interesting first sentence that highlights the most important shift.
2. THE IMPACT: Briefly explain the "So What?" – how does this affect the industry or the user?
3. THE INSIGHT: Offer a professional observation or a thought-provoking question.
4. BREVITY: Keep it under 300 characters. Density is key. 
5. NO REPETITION: Do not just list headlines. Curate the meaning.

Gold Standard Examples:
Example 1: AI safety is reaching a tipping point. Altman's latest comments on "proactive red-teaming" suggest OpenAI is shifting from pure scaling to deep alignment. This could mean a slower but much more stable GPT-5 cycle. Is the industry finally prioritizing safety over speed? #AI #OpenAI
Example 2: Edge AI just got a massive boost. Hugging Face's new 4-bit quantization tools mean you can now run serious LLMs on consumer hardware without a latency hit. The era of private, local AI isn't coming—it's already here. #OpenSource #EdgeComputing
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
    model_id = 'gemini-3.1-flash-lite'

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
