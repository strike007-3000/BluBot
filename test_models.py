import os
import asyncio
import feedparser
import sys
from unittest.mock import AsyncMock, patch
from dotenv import load_dotenv

# Set DRY_RUN before any other imports that might trigger validation
os.environ["DRY_RUN"] = "true"

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.curator import summarize_news, generate_mentor_insight
from src.logger import SafeLogger
from src.config import RSS_FEEDS, GEMINI_MODEL_PRIORITY, validate_gemini_model_priority

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
    for url in RSS_FEEDS[:5]: # Test first 5 for speed
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

async def test_scoring():
    print(f"\n{'='*20}")
    print(f"DIAGNOSTIC: SCORING ENGINE")
    print(f"{'='*20}")
    from src.curator import fetch_news
    import httpx
    
    async with httpx.AsyncClient() as client:
        top_news = await fetch_news(client)
        
    print(f"Top {len(top_news)} News Selection (Ranked by Score):")
    for i, item in enumerate(top_news):
        debug = item.get('_score_debug', {})
        print(f"\n{i+1}. {item['title']} ({item['source']})")
        print(f"   Score: {item.get('score', 0):.1f}")
        print(f"   Components: Source+{debug.get('source')}, Signal+{debug.get('signal')}, "
              f"Momentum+{debug.get('momentum')}, Synergy+{debug.get('synergy')}, "
              f"DiversityPenalty-{debug.get('diversity_penalty', 0)}, Decay-{debug.get('decay')}")

    
    # Force DEBUG mode to see session/cache logs
    os.environ["DEBUG"] = "true"
    
    import bot
    
    # Mock broadcasters and session logic to prevent external side effects
    with patch("bot.post_to_bluesky", new_callable=AsyncMock) as mock_bsky, \
         patch("bot.post_to_mastodon", new_callable=AsyncMock) as mock_masto, \
         patch("bot.post_to_threads", new_callable=AsyncMock) as mock_threads, \
         patch("bot.update_live_status", new_callable=AsyncMock), \
         patch("bot.save_seen_articles"), \
         patch("bot.load_session_string", return_value=None), \
         patch("bot.AsyncClient"): # Mock atproto client completely
        
        mock_bsky.return_value = "Mocked Success"
        mock_masto.return_value = "Mocked Success"
        mock_threads.return_value = "Mocked Success"
        
        print("Executing full bot orchestration (Offline Mode)...")
        await bot.main()
        
        print(f"\n{'='*20}")
        print(f"DRY RUN PAYLOAD REVIEW")
        print(f"{'='*20}")
        
        if mock_bsky.called:
            args = mock_bsky.call_args[0]
            summary = args[2]
            link = args[3]
            img = args[4]
            print(f"\n[BLUESKY DRAFT]")
            print(f"Content: {summary}")
            print(f"Link: {link}")
            print(f"Image: {'[ATTACHED]' if img else '[NONE]'}")
        
        if mock_masto.called:
            args = mock_masto.call_args[0]
            print(f"\n[MASTODON DRAFT]")
            print(f"Content: {args[0]}")
            print(f"Image: {'[ATTACHED]' if args[1] else '[NONE]'}")

async def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_KEY")
    
    if not api_key:
        print("\n--- GEMINI_KEY not found in environment ---")
        api_key = input("Please enter your Gemini API Key: ").strip()
        if not api_key:
            print("ERROR: API Key is required to run tests.")
            return
        os.environ["GEMINI_KEY"] = api_key

    if not validate_gemini_model_priority():
        print("ERROR: Gemini validation failed.")
        return
    
    print("\nSelect Test Mode:")
    print("1. Quick Diagnostic (RSS + Scoring)")
    print("2. AI Model Validation")
    print("3. FULL PIPELINE DRY RUN (v3.5.9)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        await test_rss()
        await test_scoring()
    elif choice == "2":
        for model in GEMINI_MODEL_PRIORITY:
            await test_model(model)
    elif choice == "3":
        await test_full_dry_run()
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    asyncio.run(main())
