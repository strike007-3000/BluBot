import asyncio
import os
import httpx
from datetime import datetime, timezone

# Modular Imports
from src.config import validate_config, README_FILE_PATH
from src.utils import load_seen_articles, save_seen_articles, SafeLogger, load_session_string, save_session_string
from src.curator import (
    fetch_news, summarize_news, generate_mentor_insight, 
    get_temporal_context, generate_visual_prompt
)
from src.broadcaster import post_to_bluesky, post_to_mastodon, post_to_threads
from src.config import (
    BLUESKY_HANDLE, BLUESKY_PASSWORD, 
    IMAGEN_MODEL, ENABLE_IMAGE_GEN
)
from google.genai import types
from atproto import AsyncClient, AsyncRequest

async def update_live_status(session_name):
    """Automatically update the README dashboard using absolute pathing."""
    try:
        if not os.path.exists(README_FILE_PATH):
            SafeLogger.warn(f"README not found at {README_FILE_PATH}. Skipping dashboard update.")
            return

        with open(README_FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        icon = "🚀" if "Morning" in session_name else "🔍"
        
        new_lines = []
        for line in lines:
            if "| **Broadcaster** |" in line:
                new_lines.append(f"| **Broadcaster** | Operational | {today} | {icon} {session_name} |\n")
            elif "| **Signal Strength** |" in line:
                new_lines.append(f"| **Signal Strength** | Elite (Parallel) | -- | -- |\n")
            else:
                new_lines.append(line)

        with open(README_FILE_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        SafeLogger.info("Updated README Live Status Dashboard.")
    except IOError as e:
        SafeLogger.error(f"Filesystem error updating README: {e}")
    except Exception as e:
        SafeLogger.error(f"Unexpected error in README update: {e}")

async def generate_ai_thumbnail(genai_client, summary, topic):
    """Orchestrates the Sage Designer pipeline to generate a custom visualization."""
    if not ENABLE_IMAGE_GEN:
        return None
        
    try:
        SafeLogger.info(f"Sage Designer: Generating visual prompt for '{topic}'...")
        visual_prompt = await generate_visual_prompt(genai_client, summary, topic)
        
        SafeLogger.info(f"Sage Designer: Generating Imagen 4 thumbnail...")
        response = await genai_client.aio.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=visual_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio='1:1'
            )
        )
        
        if response.generated_images:
            # We need the raw bytes for broadcaster.py
            return response.generated_images[0].image._image_bytes
            
    except Exception as e:
        SafeLogger.warn(f"Sage Designer failed: {e}. Falling back to No-Image mode.")
    return None

async def main():
    if not validate_config():
        return

    context = get_temporal_context()
    now = datetime.now(timezone.utc)

    # Weekend Skip logic
    if now.weekday() >= 5 and now.hour >= 12:
        SafeLogger.info(f"Skipping scheduled post: It's {context['day']} afternoon. Bot is resting.")
        return

    # Expert Review Fix: Use shared context manager for httpx session
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        seen_data = load_seen_articles()
        news = await fetch_news(client, seen_data["links"], seen_data["recent_topics"])

        # 4-State Persona Matrix Decision
        summary, lead_link, topic, internal_failover = None, None, "General", False
        session = context['session']
        news_count = len(news)
        
        if news_count > 3:
            mode = "Mentor" if "Afternoon" in session else "Curator"
            try:
                summary, lead_link, topic, internal_failover = await summarize_news(news, context, mode=mode)
                SafeLogger.info(
                    f"pipeline_failover_result stage=summarize_news success=true "
                    f"failover_succeeded={'true' if internal_failover else 'false'} final_path=summarize_news"
                )
            except Exception as e:
                SafeLogger.warn(
                    f"Summarization failed after model fallbacks ({e}). "
                    "Degrading gracefully to mentor insight mode."
                )
                try:
                    summary, lead_link, topic, internal_failover = await generate_mentor_insight(context)
                    SafeLogger.info(
                        f"pipeline_failover_result stage=summarize_news success=true "
                        f"failover_succeeded=true internal_model_failover={'true' if internal_failover else 'false'} "
                        "final_path=generate_mentor_insight"
                    )
                except Exception:
                    SafeLogger.error(
                        "pipeline_failover_result stage=summarize_news success=false "
                        "failover_succeeded=false final_path=none"
                    )
                    raise
        else:
            mode_label = "Strategist" if "Morning" in session else "Mentor"
            SafeLogger.info(f"Low news volume ({news_count}). Switching to {mode_label} Mode.")
            summary, lead_link, topic, internal_failover = await generate_mentor_insight(context)
            SafeLogger.info(
                f"pipeline_failover_result stage=summarize_news success=true info=direct_mentor_path "
                f"internal_model_failover={'true' if internal_failover else 'false'}"
            )

        if summary:
            SafeLogger.info(f"Broadcasting in {topic} mode...")
            
            # Expert Review Fix: Increase timeout to 30s to prevent InvokeTimeoutError
            bsky_client = AsyncClient(request=AsyncRequest(timeout=30.0))

            @bsky_client.on_session_change
            async def on_session_change(event, session):
                # Save the updated session string whenever it is created or refreshed
                save_session_string(bsky_client.export_session_string())

            try:
                session_str = load_session_string()
                if session_str:
                    SafeLogger.info("Attempting login via persisted session...")
                    await bsky_client.login(session_string=session_str)
                else:
                    SafeLogger.info("No session found. Logging in with credentials.")
                    await bsky_client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
            except Exception as e:
                # Login failure can be 429 (Rate Limit) or 401 (Unauthorized)
                SafeLogger.error(f"Bluesky auth failed: {type(e).__name__} - {e}")
                bsky_client = None

            # Expert Review Fix: Sage Designer AI Visualization
            # First, check metadata to see if we have a unique image
            override_image = None
            if lead_link:
                from src.utils import get_link_metadata
                meta = await get_link_metadata(client, lead_link)
                # If no unique image found (generic filtered out in utils), try AI Generation
                if not meta.get('image') and ENABLE_IMAGE_GEN:
                    override_image = await generate_ai_thumbnail(genai_client, summary, topic)

            # Expert Review Fix: Atomic Persistence & Exception Handling
            # Using gather with return_exceptions=True to ensure one failure doesn't block state saving
            broadcast_tasks = [
                ("Bluesky", post_to_bluesky(bsky_client, client, summary, lead_link, override_image)) if bsky_client else None,
                ("Mastodon", post_to_mastodon(summary)),
                ("Threads", post_to_threads(client, summary))
            ]
            
            # Filter out None tasks (e.g., if Bsky login failed)
            active_tasks = [t for t in broadcast_tasks if t is not None]
            
            results = await asyncio.gather(*[t[1] for t in active_tasks], return_exceptions=True)
            
            for (name, _), res in zip(active_tasks, results):
                if isinstance(res, Exception):
                    SafeLogger.error(f"{name} broadcast failed: {res}")
                else:
                    SafeLogger.info(f"{name} broadcast successful.")

            # Persistence Bug Fix (Duplicate protection)
            if news:
                current_seen = set(seen_data["links"])
                for item in news[:10]:
                    if item['link'] not in current_seen:
                        seen_data["links"].append(item['link'])
            
            if topic and topic != "General":
                if topic not in seen_data["recent_topics"]:
                    seen_data["recent_topics"].append(topic)
            
            save_seen_articles(seen_data)
            
            # Dashboard Update
            await update_live_status(f"{session} ({topic})")
        else:
            SafeLogger.error("Quality validation failed. Run aborted.")

if __name__ == "__main__":
    asyncio.run(main())
