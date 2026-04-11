import os
import feedparser
from google import genai
from dotenv import load_dotenv
import time

load_dotenv()

RSS_FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://export.arxiv.org/rss/cs.AI"
]

def test_rss():
    print("--- Testing RSS Feeds ---")
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"[OK] {url}: found {len(feed.entries)} items")
        except Exception as e:
            print(f"[ERROR] {url}: Error: {e}")

def test_gemini():
    api_key = os.getenv("GEMINI_KEY")
    if not api_key:
        print("[ERROR] GEMINI_KEY not found in environment variables.")
        return

    print(f"\n--- Testing Gemini API (Model: gemini-2.0-flash) ---")
    client = genai.Client(api_key=api_key)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents="Say hello and tell me one fun fact about AI."
        )
        print(f"[OK] SUCCESS! Response: {response.text.strip()}")
    except Exception as e:
        print(f"[ERROR] FAILED! Full Error Message: {e}")
        print("\nPossible solutions:")
        if "429" in str(e):
            print("- You are hitting rate limits. Try gemini-1.5-flash-8b.")
        elif "API_KEY_INVALID" in str(e) or "403" in str(e):
            print("- Your API key is invalid or lacks permissions.")
        elif "503" in str(e) or "UNAVAILABLE" in str(e):
            print("- Google's servers are temporarily down or the model is overloaded.")

if __name__ == "__main__":
    test_rss()
    test_gemini()
