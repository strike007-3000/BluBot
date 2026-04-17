import os
import asyncio
import feedparser
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from dotenv import load_dotenv

# Set DRY_RUN before any other imports that might trigger validation
os.environ["DRY_RUN"] = "true"

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.curator import summarize_news, generate_mentor_insight
from src.logger import SafeLogger
from src.config import RSS_FEEDS, GEMINI_MODEL_PRIORITY, validate_gemini_model_priority, IMAGE_PROVIDER

async def test_scoring():
    print(f"\n{'='*20}")
    print(f"DIAGNOSTIC: SCORING ENGINE")
    print(f"{'='*20}")
    from src.curator import fetch_news
    import httpx
    async with httpx.AsyncClient() as client:
        top_news = await fetch_news(client)
    for i, item in enumerate(top_news):
        print(f"{i+1}. {item['title']} - Score: {item.get('score', 0):.1f}")

async def test_full_dry_run():
    print(f"\n{'='*20}")
    print(f"FULL PIPELINE DRY RUN (v3.6.0)")
    print(f"{'='*20}")
    
    os.environ["DEBUG"] = "true"
    import bot
    
    # Expert Review Fix: Robust AsyncClient mocking for v3.6.0
    with patch("bot.AsyncClient") as mock_client_class:
        mock_instance = mock_client_class.return_value
        mock_instance.login = AsyncMock(return_value=True)
        mock_instance.send_post = AsyncMock(return_value=True)
        mock_instance.upload_blob = AsyncMock()
        mock_instance.export_session_string = MagicMock(return_value="mock_session_str")
        
        with patch("bot.post_to_mastodon", new_callable=AsyncMock), \
             patch("bot.post_to_threads", new_callable=AsyncMock), \
             patch("bot.update_live_status", new_callable=AsyncMock), \
             patch("bot.save_seen_articles"):
            
            print(f"Executing full bot orchestration (Offline Mode - {IMAGE_PROVIDER} Image Gen)...")
            await bot.main()
            print(f"\n{'='*20}\nDRY RUN COMPLETE (v3.6.0)\n{'='*20}")

async def main():
    load_dotenv()
    
    # AI Model Key Management
    api_key = os.getenv("GEMINI_KEY")
    if not api_key:
        print("\n--- GEMINI_KEY not found ---")
        api_key = input("Please enter your Gemini API Key: ").strip()
        os.environ["GEMINI_KEY"] = api_key

    if IMAGE_PROVIDER == "nvidia":
        nv_key = os.getenv("NVIDIA_KEY")
        if not nv_key:
            print("\n--- NVIDIA_KEY not found ---")
            nv_key = input("Please enter your NVIDIA API Key: ").strip()
            os.environ["NVIDIA_KEY"] = nv_key

    if not validate_gemini_model_priority():
        print("ERROR: Gemini validation failed.")
        return
    
    print("\nSelect Test Mode:")
    print("1. Quick Diagnostic (Scoring)")
    print("2. FULL PIPELINE DRY RUN (v3.6.0)")
    
    choice = input("\nEnter choice (1-2): ").strip()
    if choice == "1":
        await test_scoring()
    elif choice == "2":
        await test_full_dry_run()
    else:
        print("Final Restoration: Defaulting to Full Dry Run.")
        await test_full_dry_run()

if __name__ == "__main__":
    asyncio.run(main())
