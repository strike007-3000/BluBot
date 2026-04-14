import os
import feedparser
from dotenv import load_dotenv
from src.curator import summarize_news, generate_mentor_insight, SafeLogger
from src.config import RSS_FEEDS

# Mock data for testing
MOCK_NEWS = [
    {
        "title": "Gemma 3 27B-IT performance benchmarks released",
        "link": "https://example.com/gemma3",
        "source": "TechCrunch",
        "score": 100
    },
    {
        "title": "Gemini 3.1 Flash Lite becomes world's fastest compact model",
        "link": "https://example.com/gemini31",
        "source": "VentureBeat",
        "score": 95
    }
]

MOCK_CONTEXT = {
    "day": "Tuesday",
    "session": "Morning",
    "recent_topics": []
}

async def test_rss():
    print(f"\n{'='*20}")
    print(f"TESTING RSS FEEDS")
    print(f"{'='*20}")
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"[OK] {url}: found {len(feed.entries)} items")
        except Exception as e:
            print(f"[ERROR] {url}: Error: {e}")

async def test_model(model_name):
    print(f"\n{'='*20}")
    print(f"TESTING MODEL: {model_name}")
    print(f"{'='*20}")
    
    # Temporarily override priority to test specific model
    from src import curator
    original_priority = curator.GEMINI_MODEL_PRIORITY
    curator.GEMINI_MODEL_PRIORITY = [model_name]
    
    try:
        print(f"--- Calling summarize_news ---")
        summary, link, topic, failover = await summarize_news(MOCK_NEWS, MOCK_CONTEXT, mode="Curator")
        print(f"SUCCESS!")
        print(f"Topic: {topic}")
        print(f"Summary:\n{summary}")
        print(f"Internal Failover Occurred: {failover}")
        
    except Exception as e:
        print(f"FAILED with error: {e}")
    finally:
        curator.GEMINI_MODEL_PRIORITY = original_priority

async def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_KEY")
    
    if not api_key:
        print("\n--- GEMINI_KEY not found in environment ---")
        api_key = input("Please enter your Gemini API Key: ").strip()
        if not api_key:
            print("ERROR: API Key is required to run tests.")
            return
        # Inject into environment for the session
        os.environ["GEMINI_KEY"] = api_key
        # Refresh the key in the curator module
        from src import curator
        curator.GEMINI_API_KEY = api_key

    from src.config import GEMINI_MODEL_PRIORITY
    
    # 1. Test RSS Feeds
    await test_rss()

    # 2. Test AI Models
    print(f"\n{'='*20}")
    print(f"TESTING AI MODELS")
    print(f"{'='*20}")
    print(f"Current Priority List: {GEMINI_MODEL_PRIORITY}")
    
    for model in GEMINI_MODEL_PRIORITY:
        await test_model(model)

if __name__ == "__main__":
    asyncio.run(main())
