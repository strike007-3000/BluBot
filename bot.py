import os
import feedparser
from google import genai
from atproto import Client, client_utils
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import time

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

def fetch_news():
    print("Fetching news from RSS feeds...")
    all_entries = []
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Some feeds use published_parsed, others might vary
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
            print(f"Error parsing {url}: {e}")
    
    return all_entries

def summarize_news(news_items):
    if not news_items:
        return None

    print(f"Summarizing {len(news_items)} news items...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    news_text = "\n".join([f"- {item['title']} (Source: {item['source']})" for item in news_items[:10]])
    
    prompt = f"""
    You are an AI news curator. Below is a list of AI-related news from the last 24 hours.
    Create a single, engaging Bluesky post summarizing the most important updates.
    
    Rules:
    1. Maximum 300 characters.
    2. Use bullet points or a concise summary.
    3. Include 1-2 relevant hashtags (e.g., #AI #Tech).
    4. Make it sound exciting but professional.
    5. Do not include literal links in the text, just the summary.
    
    News Items:
    {news_text}
    """
    
    # Retry logic for rate limits or transient server errors
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            error_msg = str(e)
            # Retry on 429 (Rate Limit) or 503 (Service Unavailable)
            if ("429" in error_msg or "503" in error_msg or "UNAVAILABLE" in error_msg) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 30
                print(f"Transient error ({error_msg[:50]}...). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Error during summarization: {e}")
                return None
    return None

def post_to_bluesky(text):
    if not text:
        print("Nothing to post.")
        return

    print("Posting to Bluesky...")
    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    
    # Ensure text is within limit
    if len(text) > 300:
        text = text[:297] + "..."
        
    client.send_post(text=text)
    print("Successfully posted!")

def main():
    if not all([BLUESKY_HANDLE, BLUESKY_PASSWORD, GEMINI_API_KEY]):
        print("Missing environment variables. Please check your .env file or GitHub Secrets.")
        return

    news = fetch_news()
    if not news:
        print("No new AI news found in the last 24 hours. Skipping post.")
        # Optional: Post a 'Slow news day' update or just skip
        return

    summary = summarize_news(news)
    post_to_bluesky(summary)

if __name__ == "__main__":
    main()
