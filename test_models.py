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

async def test_full_dry_run():
    print(f"\n{'='*20}")
    print(f"FULL PIPELINE DRY RUN (v3.5.11)")
    print(f"{'='*20}")
    
    os.environ["DEBUG"] = "true"
    import bot
    
    with patch("bot.post_to_bluesky", new_callable=AsyncMock) as mock_bsky, \
         patch("bot.post_to_mastodon", new_callable=AsyncMock), \
         patch("bot.post_to_threads", new_callable=AsyncMock), \
         patch("bot.update_live_status", new_callable=AsyncMock), \
         patch("bot.save_seen_articles"), \
         patch("bot.load_session_string", return_value=None), \
         patch("bot.AsyncClient"):
        
        mock_bsky.return_value = "Mocked Success"
        print("Executing full bot orchestration (Offline Mode)...")
        await bot.main()
        print(f"\n{'='*20}\nDRY RUN COMPLETE\n{'='*20}")

async def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_KEY")
    if not api_key:
        api_key = input("Please enter your Gemini API Key: ").strip()
        os.environ["GEMINI_KEY"] = api_key

    if not validate_gemini_model_priority():
        print("ERROR: Gemini validation failed.")
        return
    
    print("\nSelect Test Mode:")
    print("1. Quick Diagnostic")
    print("2. AI Model Validation")
    print("3. FULL PIPELINE DRY RUN (v3.5.11)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    if choice == "3":
        await test_full_dry_run()
    else:
        print("Diagnostic modes skipped for restoration check.")

if __name__ == "__main__":
    asyncio.run(main())
