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
from src.config import validate_gemini_model_priority, IMAGE_PROVIDER, VERSION, FEED_CATEGORY_MAP

async def test_scoring():
    print(f"\n{'='*20}")
    print(f"DIAGNOSTIC: SCORING ENGINE (v{VERSION})")
    print(f"{'='*20}")
    
    import httpx
    async with httpx.AsyncClient() as client:
        # Fetch all candidate items without limit to analyze overall source contributions
        all_candidates = await fetch_news(client, limit=None)
    
    if not all_candidates:
        print("No news items found. Check RSS feeds or internet connection.")
        return

    top_news = all_candidates[:8]

    # Source metrics aggregation
    source_stats = {}
    for item in all_candidates:
        src_id = item.get("source_id", item.get("source", "unknown"))
        if src_id not in source_stats:
            source_stats[src_id] = {
                "count": 0,
                "scores": [],
                "latest_pub": item.get("published", "")
            }
        source_stats[src_id]["count"] += 1
        source_stats[src_id]["scores"].append(item.get("score", 0))
        if item.get("published", "") > source_stats[src_id]["latest_pub"]:
            source_stats[src_id]["latest_pub"] = item.get("published", "")

    # Top selected metrics
    selected_sources = set()
    category_counts = {}
    for item in top_news:
        src_id = item.get("source_id", item.get("source", "unknown"))
        selected_sources.add(src_id)
        cat = FEED_CATEGORY_MAP.get(src_id, "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    zero_selection_sources = [src_id for src_id in source_stats if src_id not in selected_sources]

    print(f"\n📊 CANDIDATE & SELECTION SUMMARY:")
    print(f"   - Total Candidates Fetched: {len(all_candidates)}")
    print(f"   - Selected for Top Output:  {len(top_news)}")
    print(f"   - Active Contributing Feeds: {len(source_stats)}")
    print(f"   - Zero-Selection Feeds:     {len(zero_selection_sources)}")

    print(f"\n🏷️ CATEGORY DISTRIBUTION (Top Selected):")
    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {cat:<15}: {count}")

    print(f"\n📡 SOURCE CANDIDATE BREAKDOWN:")
    print(f"   {'SOURCE ID':<25} | {'CANDIDATES':<10} | {'AVG SCORE':<10} | {'LATEST ITEM DATE'}")
    print(f"   " + "-"*70)
    for src_id, data in sorted(source_stats.items(), key=lambda x: x[1]['count'], reverse=True):
        avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0.0
        pub_str = data["latest_pub"][:19] if data["latest_pub"] else "N/A"
        sel_flag = "★" if src_id in selected_sources else " "
        print(f" {sel_flag} {src_id:<24} | {data['count']:<10} | {avg_score:<10.1f} | {pub_str}")

    if zero_selection_sources:
        print(f"\n⚠️ SOURCES WITH CANDIDATES BUT NO TOP-EIGHT SELECTIONS:")
        print(f"   " + ", ".join(zero_selection_sources))

    print(f"\n🏆 TOP SELECTED ARTICLES:")
    print("-" * 70)
    for i, item in enumerate(top_news):
        print(f"{i+1}. {item['title']}")
        print(f"   Source: {item['source']} ({item.get('source_id', 'unknown')}) | Score: {item.get('score', 0):.1f}")
        debug = item.get('_score_debug', {})
        print(f"   Breakdown: [Src: {debug.get('source')} | Sig: {debug.get('signal')} | Mom: {debug.get('momentum')} | Pen: {debug.get('penalty')} | Dec: {debug.get('decay')}]")
        print("-" * 70)

async def test_full_dry_run():
    print(f"\n{'='*20}")
    print(f"FULL PIPELINE DRY RUN (v{VERSION})")
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
            print(f"\n{'='*20}\nDRY RUN COMPLETE (v{VERSION})\n{'='*20}")

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

async def test_gist_diagnostics():
    import uuid
    import httpx
    from src.settings import settings
    from src.utils import _load_gist_state, _save_gist_state

    print(f"\n{'='*20}")
    print(f"DIAGNOSTIC: GIST PERSISTENCE TEST")
    print(f"{'='*20}")

    gist_id = settings.gist_id
    gist_token = settings.gist_token

    if not gist_id or not gist_token:
        print("⚠️ GIST_ID or GIST_TOKEN not found in environment.")
        if not gist_id:
            gist_id = input("Enter GIST_ID: ").strip()
        if not gist_token:
            gist_token = input("Enter GIST_TOKEN (GitHub PAT): ").strip()

    if not gist_id or not gist_token:
        print("❌ Gist Status: Gist credentials not provided.")
        return

    object.__setattr__(settings, "gist_id", gist_id)
    object.__setattr__(settings, "gist_token", gist_token)

    print("✅ Gist Status: Configured.")
    print("Testing read access on production state file (seen_articles.json)...")
    prod_state = _load_gist_state("seen_articles.json")
    if prod_state is None:
        print("⚠️ Production Gist file read: Unavailable or invalid.")
    else:
        rev = prod_state.get("revision", "N/A")
        ver = prod_state.get("schema_version", "N/A")
        print(f"✅ Production Gist file read successful. (schema_version={ver}, revision={rev})")

    test_uuid = str(uuid.uuid4())
    test_filename = f"_diag_{test_uuid}.json"
    test_payload = {
        "diagnostic": True,
        "uuid": test_uuid,
        "timestamp": "2026-08-18T19:00:00Z"
    }

    print(f"\nInitiating safe write test with temporary file: {test_filename}")
    try:
        write_ok = _save_gist_state(test_filename, test_payload)
        if not write_ok:
            print("❌ Write Test: Failed to write test payload to Gist.")
            return

        print("✅ Write Test: Success. Testing read-back...")
        read_payload = _load_gist_state(test_filename)
        if read_payload == test_payload:
            print("✅ Read-back Test: Success. Content matches exactly.")
        else:
            print("❌ Read-back Test: Failed. Content mismatch.")
    finally:
        print(f"Cleaning up temporary file {test_filename} from Gist...")
        try:
            url = f"https://api.github.com/gists/{settings.gist_id}"
            headers = {
                "Authorization": f"token {settings.gist_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            payload = {"files": {test_filename: None}}
            with httpx.Client(timeout=10.0) as client:
                resp = client.patch(url, headers=headers, json=payload)
                resp.raise_for_status()
                print("✅ Cleanup Test: Success. Temporary file removed.")
        except Exception as e:
            print(f"❌ CLEANUP FAILURE: Failed to remove temporary file {test_filename} from Gist ({e}). Residual filename remains: {test_filename}")

async def main():
    load_dotenv()
    SafeLogger.configure(mode="Diagnostic")
    
    print("\nSelect Diagnostic Mode:")
    print("1. Quick Diagnostic (Scoring Breakdown)")
    print("2. FULL PIPELINE DRY RUN (AI Generation + Mock Broadcast)")
    print("3. Live Image Generation Test (Pollinations, Hugging Face, & Gemini Imagen)")
    print("4. Gist State Diagnostics (Opt-in Read/Write Test)")
    
    try:
        choice = input("\nEnter choice (1-4) or 'q' to quit: ").strip().lower()
        if choice == "1":
            await test_scoring()
        elif choice == "2":
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
        elif choice == "4":
            await test_gist_diagnostics()
        elif choice == "q":
            print("Exiting.")
        else:
            print("Defaulting to Scoring Breakdown.")
            await test_scoring()
    except EOFError:
        await test_scoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user.")
