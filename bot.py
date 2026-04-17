import asyncio
import os
import httpx
import logging
from datetime import datetime, timezone

# Modular Imports
from src.config import validate_config, README_FILE_PATH
from src.utils import load_seen_articles, save_seen_articles, SafeLogger, load_session_string, save_session_string
from src.curator import (
    fetch_news, summarize_news, generate_mentor_insight, 
    get_temporal_context, generate_visual_prompt, generate_nvidia_image
)
from src.broadcaster import post_to_bluesky, post_to_mastodon, post_to_threads
from google.genai import types
from google import genai
from atproto import AsyncClient, AsyncRequest

async def update_live_status(session_name):
    """Automatically update the README dashboard using absolute pathing."""
    try:
        if not os.path.exists(README_FILE_PATH):
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
    except Exception as e:
        SafeLogger.debug(f"Dashboard update failed: {e}")

async def generate_ai_thumbnail(client, genai_client, summary, topic):
    """Orchestrates the chosen image generation provider pipeline."""
    from src.config import IMAGEN_MODEL, ENABLE_IMAGE_GEN, IMAGE_PROVIDER
    if not ENABLE_IMAGE_GEN:
        return None
        
    try:
        SafeLogger.info(f"Sage Designer: Generating visual prompt for '{topic}'...")
        visual_prompt = await generate_visual_prompt(genai_client, summary, topic)
        
        if IMAGE_PROVIDER == "nvidia":
            SafeLogger.info(f"Sage Designer: Generating NVIDIA SD3-Medium thumbnail...")
            return await generate_nvidia_image(client, visual_prompt)
        else:
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
                return response.generated_images[0].image._image_bytes
            
    except Exception as e:
        err_msg = str(e).lower()
        if "paid plan" in err_msg or "billing" in err_msg or "403" in err_msg:
            SafeLogger.info("Sage Designer: Primary image provider restricted. Skipping.")
        else:
            SafeLogger.warn(f"Sage Designer failed: {e}. Falling back.")
    return None

async def main():
    if not validate_config():
        return

    # Expert Review Fix: Dynamic runtime identity (v3.5.12)
    gemini_key = os.getenv("GEMINI_KEY")
    bsky_handle = os.getenv("BSKY_HANDLE")
    bsky_password = os.getenv("BSKY_APP_PASSWORD")

    logging.getLogger("atproto").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Initialize client with dynamic key
    genai_client = genai.Client(api_key=gemini_key)
    context = get_temporal_context()
    now = datetime.now(timezone.utc)

    # Weekend Skip logic
    if now.weekday() >= 5 and now.hour >= 12:
        SafeLogger.info(f"Skipping scheduled post: Weekend rest initiated.")
        return

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        seen_data = load_seen_articles()
        news = await fetch_news(client, seen_data["links"], seen_data["recent_topics"])

        # 4-State Persona Matrix Selection
        summary, lead_link, topic, internal_failover = None, None, "General", False
        session = context['session']
        news_count = len(news)
        
        if news_count > 3:
            mode = "Mentor" if "Afternoon" in session else "Curator"
            try:
                summary, lead_link, topic, internal_failover = await summarize_news(news, context, mode=mode)
            except Exception as e:
                SafeLogger.warn(f"Summarization failed ({e}). Falling back to insight mode.")
                summary, lead_link, topic, internal_failover = await generate_mentor_insight(context)
        else:
            SafeLogger.info(f"Low news volume ({news_count}). Switching to Strategist Mode.")
            summary, lead_link, topic, internal_failover = await generate_mentor_insight(context)

        if summary:
            SafeLogger.info(f"Broadcasting in {topic} mode...")
            
            # Bluesky Session Authentication with Full Fallback
            bsky_client = AsyncClient(request=AsyncRequest(timeout=30.0))
            try:
                session_str = load_session_string()
                if session_str:
                    try:
                        await bsky_client.login(session_string=session_str)
                    except Exception as e:
                        if "520" in str(e):
                            await asyncio.sleep(2)
                        await bsky_client.login(bsky_handle, bsky_password)
                else:
                    await bsky_client.login(bsky_handle, bsky_password)
                
                # Save session string on success
                save_session_string(bsky_client.export_session_string())
            except Exception as e:
                SafeLogger.error(f"Bluesky auth failed: {e}")
                bsky_client = None

            # Visual Orchestration
            override_image = None
            image_url_for_threads = None
            if lead_link:
                from src.utils import get_link_metadata
                meta = await get_link_metadata(client, lead_link)
                if meta:
                    image_url_for_threads = meta.get('image_url')
                    if not meta.get('image'):
                        override_image = await generate_ai_thumbnail(client, genai_client, summary, topic)
                    else:
                        override_image = meta.get('image')

            # Atomic Broadcast Gather
            broadcast_tasks = [
                ("Bluesky", post_to_bluesky(bsky_client, client, summary, lead_link, override_image)) if bsky_client else None,
                ("Mastodon", post_to_mastodon(summary, override_image)),
                ("Threads", post_to_threads(client, summary, image_url_for_threads))
            ]
            active_tasks = [t for t in broadcast_tasks if t is not None]
            results = await asyncio.gather(*[t[1] for t in active_tasks], return_exceptions=True)
            
            for (name, _), res in zip(active_tasks, results):
                if isinstance(res, Exception):
                    SafeLogger.error(f"{name} broadcast failed: {res}")
                else:
                    SafeLogger.info(f"{name} broadcast successful.")

            # Persistence of Signal
            if news:
                current_seen = set(seen_data["links"])
                for item in news[:10]:
                    if item['link'] not in current_seen:
                        seen_data["links"].append(item['link'])
            
            if topic and topic != "General" and topic not in seen_data["recent_topics"]:
                seen_data["recent_topics"].append(topic)
            
            save_seen_articles(seen_data)
            await update_live_status(f"{session} ({topic})")
        else:
            SafeLogger.error("Synthesis failed. Post aborted.")

if __name__ == "__main__":
    asyncio.run(main())
