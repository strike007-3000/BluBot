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

def _prompt_key(env_var, label):
    """Prompt for an API key if not set in environment. Returns the key or None."""
    key = os.getenv(env_var)
    # DRY_RUN injects mock values — treat those as missing
    if key and key.startswith("mock_"):
        key = None
    if not key:
        print(f"\n--- {env_var} not found ---")
        key = input(f"Please enter your {label} (or press enter to skip): ").strip()
        if key:
            os.environ[env_var] = key
            from src.settings import settings
            field = env_var.lower()
            object.__setattr__(settings, field, key)
    return key


async def _test_pollinations(prompt):
    import httpx
    from src.curator import generate_pollinations_image

    print(f"\nRunning Pollinations image generation...")
    try:
        async with httpx.AsyncClient() as client:
            res = await generate_pollinations_image(prompt, client)
        if res:
            out_path = "pollinations_test.png"
            with open(out_path, "wb") as f:
                f.write(res)
            print(f"✅ Success! Pollinations image saved to: {out_path} ({len(res)} bytes)")
        else:
            print("❌ Failure: Pollinations generation returned no bytes.")
    except Exception as e:
        print(f"❌ Failure: Pollinations generation failed: {e}")


async def _test_huggingface(prompt):
    import httpx
    from src.curator import generate_huggingface_image

    key = _prompt_key("HUGGINGFACE_API_KEY", "Hugging Face API Key")
    if not key:
        print("Skipping Hugging Face test (no key).")
        return

    print(f"\nRunning Hugging Face image generation...")
    try:
        async with httpx.AsyncClient() as client:
            res = await generate_huggingface_image(prompt, client)
        if res:
            out_path = "huggingface_test.png"
            with open(out_path, "wb") as f:
                f.write(res)
            print(f"✅ Success! Hugging Face image saved to: {out_path} ({len(res)} bytes)")
        else:
            print("❌ Failure: Hugging Face generation returned no bytes.")
    except Exception as e:
        print(f"❌ Failure: Hugging Face generation failed: {e}")


async def _test_imagen(prompt):
    from google import genai
    from src.curator import generate_imagen_image

    key = _prompt_key("GEMINI_KEY", "Gemini API Key")
    if not key:
        print("Skipping Gemini Imagen test (no key).")
        return

    print(f"\nRunning Gemini Imagen image generation...")
    try:
        genai_client = genai.Client(api_key=key)
        res = await generate_imagen_image(genai_client, prompt)
        if res:
            out_path = "gemini_imagen_test.png"
            with open(out_path, "wb") as f:
                f.write(res)
            print(f"✅ Success! Gemini Imagen image saved to: {out_path} ({len(res)} bytes)")
        else:
            print("❌ Failure: Gemini Imagen generation returned no bytes.")
    except Exception as e:
        print(f"❌ Failure: Gemini Imagen generation failed: {e}")


PROVIDER_TESTS = {
    "1": ("Pollinations (free, no key)", _test_pollinations),
    "2": ("Hugging Face (requires HF key)", _test_huggingface),
    "3": ("Gemini Imagen (requires Gemini key)", _test_imagen),
    "a": ("All providers", None),
}


async def test_image_generation():
    import httpx
    from src.config import POLLINATIONS_API_URL, HF_IMAGE_MODEL

    print(f"\n{'='*20}")
    print(f"DIAGNOSTIC: LIVE IMAGE GENERATION TEST")
    print(f"{'='*20}")

    # --- Endpoint Connectivity Pre-Check ---
    print(f"\n--- Endpoint Connectivity Check ---")
    endpoints = {
        "Pollinations": POLLINATIONS_API_URL.rstrip("/") + "/test",
        "Hugging Face": f"https://router.huggingface.co/hf-inference/models/{HF_IMAGE_MODEL}",
    }
    async with httpx.AsyncClient() as check_client:
        for name, url in endpoints.items():
            try:
                resp = await check_client.head(url, timeout=10.0, follow_redirects=True)
                print(f"  {name}: {url} → HTTP {resp.status_code} ✓")
            except Exception as e:
                print(f"  {name}: {url} → UNREACHABLE ({e})")

    # --- Provider Selection ---
    print(f"\nSelect provider to test:")
    for key, (label, _) in PROVIDER_TESTS.items():
        print(f"  {key}. {label}")

    choice = input("\nEnter choice: ").strip().lower()
    prompt = "A minimalist icon of a blue bird holding a newspaper, clean digital art, simple illustration"

    if choice == "a":
        for _, (_, fn) in PROVIDER_TESTS.items():
            if fn:
                await fn(prompt)
    elif choice in PROVIDER_TESTS and PROVIDER_TESTS[choice][1]:
        await PROVIDER_TESTS[choice][1](prompt)
    else:
        print("Invalid choice. Running all providers.")
        for _, (_, fn) in PROVIDER_TESTS.items():
            if fn:
                await fn(prompt)

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
