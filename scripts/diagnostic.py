import os
import asyncio
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from dotenv import load_dotenv

# Set DRY_RUN before any other imports that might trigger validation
os.environ["DRY_RUN"] = "true"

# Ensure we can import from src
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

async def test_image_generation():
    print(f"\n{'='*20}")
    print(f"DIAGNOSTIC: LIVE IMAGE GENERATION TEST")
    print(f"{'='*20}")
    
    import httpx
    from google import genai
    from src.curator import generate_pollinations_image, generate_huggingface_image, generate_imagen_image
    
    prompt = "A minimalist icon of a blue bird holding a newspaper, clean digital art, simple illustration"
    
    # 1. Pollinations Test
    print(f"\nRunning Pollinations image generation...")
    try:
        async with httpx.AsyncClient() as client:
            res = await generate_pollinations_image(prompt, client)
        if res:
            out_path = "pollinations_test.png"
            with open(out_path, "wb") as f:
                f.write(res)
            print(f"✅ Success! Pollinations image generated and saved to: {out_path} ({len(res)} bytes)")
        else:
            print("❌ Failure: Pollinations generation returned no bytes.")
    except Exception as e:
        print(f"❌ Failure: Pollinations generation failed: {e}")
        
    # 2. Hugging Face Test
    hf_key = os.getenv("HUGGINGFACE_API_KEY")
    if not hf_key:
        print("\n--- HUGGINGFACE_API_KEY not found ---")
        hf_key = input("Please enter your Hugging Face API Key (or press enter to skip): ").strip()
        if hf_key:
            os.environ["HUGGINGFACE_API_KEY"] = hf_key
            from src.settings import settings
            object.__setattr__(settings, "huggingface_api_key", hf_key)

    if os.getenv("HUGGINGFACE_API_KEY"):
        print(f"\nRunning Hugging Face image generation...")
        try:
            async with httpx.AsyncClient() as client:
                res = await generate_huggingface_image(prompt, client)
            if res:
                out_path = "huggingface_test.png"
                with open(out_path, "wb") as f:
                    f.write(res)
                print(f"✅ Success! Hugging Face image generated and saved to: {out_path} ({len(res)} bytes)")
            else:
                print("❌ Failure: Hugging Face generation returned no bytes.")
        except Exception as e:
            print(f"❌ Failure: Hugging Face generation failed: {e}")
    else:
        print("\nHUGGINGFACE_API_KEY not available, skipping Hugging Face test.")
        
    # 3. Gemini/Imagen Test
    gemini_key = os.getenv("GEMINI_KEY")
    if not gemini_key:
        print("\n--- GEMINI_KEY not found ---")
        gemini_key = input("Please enter your Gemini API Key (or press enter to skip): ").strip()
        if gemini_key:
            os.environ["GEMINI_KEY"] = gemini_key
            from src.settings import settings
            object.__setattr__(settings, "gemini_key", gemini_key)

    if os.getenv("GEMINI_KEY"):
        print(f"\nRunning Gemini Imagen image generation...")
        try:
            genai_client = genai.Client(api_key=os.getenv("GEMINI_KEY"))
            res = await generate_imagen_image(genai_client, prompt)
            if res:
                out_path = "gemini_imagen_test.png"
                with open(out_path, "wb") as f:
                    f.write(res)
                print(f"✅ Success! Gemini Imagen image generated and saved to: {out_path} ({len(res)} bytes)")
            else:
                print("❌ Failure: Gemini Imagen generation returned no bytes.")
        except Exception as e:
            print(f"❌ Failure: Gemini Imagen generation failed: {e}")
    else:
        print("\nGEMINI_KEY not available, skipping Gemini Imagen test.")

async def main():
    load_dotenv()
    SafeLogger.configure(mode="Diagnostic")
    
    print("\nSelect Diagnostic Mode:")
    print("1. Quick Diagnostic (Scoring Breakdown)")
    print("2. FULL PIPELINE DRY RUN (AI Generation + Mock Broadcast)")
    print("3. Live Image Generation Test (Pollinations, Hugging Face, & Gemini Imagen)")
    
    try:
        choice = input("\nEnter choice (1-3) or 'q' to quit: ").strip().lower()
        if choice == "1":
            await test_scoring()
        elif choice == "2":
            # Prompt for Gemini key since full dry run needs it
            gemini_key = os.getenv("GEMINI_KEY")
            if not gemini_key:
                print("\n--- GEMINI_KEY not found ---")
                gemini_key = input("Please enter your Gemini API Key: ").strip()
                os.environ["GEMINI_KEY"] = gemini_key
                from src.settings import settings
                object.__setattr__(settings, "gemini_key", gemini_key)
            if validate_gemini_model_priority():
                await test_full_dry_run()
        elif choice == "3":
            await test_image_generation()
        elif choice == "q":
            print("Exiting.")
        else:
            print("Defaulting to Scoring Breakdown.")
            await test_scoring()
    except EOFError:
        # Handle non-interactive environments
        await test_scoring()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user.")
