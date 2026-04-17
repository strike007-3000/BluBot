import os
import asyncio
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from dotenv import load_dotenv

# Set DRY_RUN before any other imports that might trigger validation
os.environ["DRY_RUN"] = "true"

# Ensure we can import from src
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from src.curator import fetch_news, summarize_news
from src.logger import SafeLogger
from src.config import validate_gemini_model_priority, IMAGE_PROVIDER

async def test_scoring():
    print(f"\n{'='*20}")
    print(f"DIAGNOSTIC: SCORING ENGINE (v3.6.5)")
    print(f"{'='*20}")
    
    import httpx
    async with httpx.AsyncClient() as client:
        # P1 Badge: Use production curator logic for scoring diagnostic
        top_news = await fetch_news(client)
    
    if not top_news:
        print("No news items found. Check RSS feeds or internet connection.")
        return

    for i, item in enumerate(top_news):
        print(f"{i+1}. {item['title']}")
        print(f"   Source: {item['source']} | Score: {item.get('score', 0):.1f}")
        debug = item.get('_score_debug', {})
        print(f"   Breakdown: [Src: {debug.get('source')} | Sig: {debug.get('signal')} | Mom: {debug.get('momentum')} | Pen: {debug.get('penalty')} | Dec: {debug.get('decay')}]")
        print("-" * 10)

async def test_full_dry_run():
    print(f"\n{'='*20}")
    print(f"FULL PIPELINE DRY RUN (v3.6.5)")
    print(f"{'='*20}")
    
    os.environ["DEBUG"] = "true"
    import bot
    
    # Unified Mocking Strategy (Aligned with pytest suite)
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
            print(f"\n{'='*20}\nDRY RUN COMPLETE (v3.6.5)\n{'='*20}")

async def main():
    load_dotenv()
    SafeLogger.configure(mode="Diagnostic")
    
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

    # Validate models with user keys
    if not validate_gemini_model_priority():
        print("ERROR: Gemini validation failed with provided key.")
        return
    
    print("\nSelect Diagnostic Mode:")
    print("1. Quick Diagnostic (Scoring Breakdown)")
    print("2. FULL PIPELINE DRY RUN (AI Generation + Mock Broadcast)")
    
    try:
        choice = input("\nEnter choice (1-2) or 'q' to quit: ").strip().lower()
        if choice == "1":
            await test_scoring()
        elif choice == "2":
            await test_full_dry_run()
        elif choice == "q":
            print("Exiting.")
        else:
            print("Defaulting to Full Dry Run.")
            await test_full_dry_run()
    except EOFError:
        # Handle non-interactive environments
        await test_scoring()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user.")

if __name__ == "__main__":
    asyncio.run(main())
