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
Your task is to transform technical news into insightful, punchy, and professional updates.
Avoid just repeating the title; instead, explain WHY the news matters or what the specific impact is.

Rules:
1. Maximum 300 characters.
2. Provide a substantive, high-density summary (2-3 detailed sentences).
3. CRITICAL: Your response MUST end with 1-2 relevant hashtags (e.g., #AI #Tech).
4. Do not use preambles like "Here is the summary" or "Today's news".
5. NEVER include literal URLs.

Gold Standard Examples:
Example 1 (Insightful): Sam Altman's recent comments on AI safety signal a shift toward proactive red-teaming. This likely means OpenAI will prioritize long-term alignment over immediate model scaling in the next GPT cycle, a major win for AI ethics. #AI #Tech
Example 2 (Insightful): Hugging Face's new open-weight release lowers the barrier for edge computing. By optimizing for 4-bit quantization, it enables real-time LLM inference on consumer hardware, challenging the dominance of closed-source giants. #OpenSource #AI
"""

def validate_summary(text):
    if not text:
        return False, "Empty output"
    
    # Check for excessive repetition (e.g. + 9 + 9 + 9)
    if re.search(r'(.)\1{4,}', text) or re.search(r'(\+\s*\d\s*){4,}', text):
        return False, "Detected repetitive patterns or gibberish"
    
    # Check for reasonable length (Raised to 80 to ensure insightfulness)
    if len(text) < 80:
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

    # Include summary context for better output
    news_text = "\n".join([f"- {item['title']} (Source: {item['source']})\n  Context: {item['summary']}" for item in news_items[:10]])
    
    user_prompt = f"""
    Curation Task: Synthesize the following news into one professional and insightful Bluesky post.
    Do NOT just repeat the headlines. Extract one specific technical detail or impact point from the "Context" and explain why it matters to the industry.
    
    Ensure the result feels like a mini-analysis, not just a news flash.
    
    News Data to Curate:
    {news_text}
    """
    
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
        max_output_tokens=150
    )
    
    max_retries = 3
    best_candidate = None # Best one regardless of hashtags
    longest_fallback = "" # Longest one found if everything is too short
    model_id = 'gemini-2.5-flash'

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
        return rescued[:300]
    
    if len(longest_fallback) >= 20: # If it's almost long enough, we can rescue it
        print("Applying Length Rescue (Expansion)...", flush=True)
        rescued = longest_fallback.strip()
        if "#" not in rescued:
            rescued += " #AI #Tech"
        if len(rescued) < 40: # If still too short, add a generic relevant sentence
            rescued = "Latest updates in AI: " + rescued
        return rescued[:300]

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
