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
    get_temporal_context, generate_visual_prompt
)
from src.broadcaster import post_to_bluesky, post_to_mastodon, post_to_threads
from google.genai import types
from google import genai
from atproto import AsyncClient, AsyncRequest

async def update_live_status(session_name):
    try:
        if not os.path.exists(README_FILE_PATH):
            return
        with open(README_FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_lines = []
        for line in lines:
            if "| **Broadcaster** |" in line:
                new_lines.append(f"| **Broadcaster** | Operational | {today} | {session_name} |\n")
            else:
                new_lines.append(line)
        with open(README_FILE_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        SafeLogger.debug(f"Dashboard update failed: {e}")

async def generate_ai_thumbnail(genai_client, summary, topic):
    from src.config import IMAGEN_MODEL, ENABLE_IMAGE_GEN
    if not ENABLE_IMAGE_GEN:
        return None
    try:
        visual_prompt = await generate_visual_prompt(genai_client, summary, topic)
        response = await genai_client.aio.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=visual_prompt,
            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio='1:1')
        )
        if response.generated_images:
            return response.generated_images[0].image._image_bytes
    except Exception as e:
        SafeLogger.warn(f"Sage Designer failed: {e}")
    return None

async def main():
    if not validate_config():
        return

    # Critical: Re-fetch keys from environment locally inside main
    gemini_key = os.getenv("GEMINI_KEY")
    bsky_handle = os.getenv("BSKY_HANDLE")
    bsky_password = os.getenv("BSKY_APP_PASSWORD")

    logging.getLogger("atproto").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    genai_client = genai.Client(api_key=gemini_key)
    context = get_temporal_context()
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        seen_data = load_seen_articles()
        news = await fetch_news(client, seen_data["links"], seen_data["recent_topics"])

        if len(news) > 3:
            mode = "Mentor" if "Afternoon" in context['session'] else "Curator"
            summary, lead_link, topic, _ = await summarize_news(news, context, mode=mode)
        else:
            summary, lead_link, topic, _ = await generate_mentor_insight(context)

        if summary:
            bsky_client = AsyncClient(request=AsyncRequest(timeout=30.0))
            try:
                session_str = load_session_string()
                if session_str:
                    await bsky_client.login(session_string=session_str)
                else:
                    await bsky_client.login(bsky_handle, bsky_password)
            except Exception as e:
                SafeLogger.debug(f"Bluesky login failed, falling back: {e}")
                await bsky_client.login(bsky_handle, bsky_password)

            override_image = None
            image_url_for_threads = None
            if lead_link:
                from src.utils import get_link_metadata
                meta = await get_link_metadata(client, lead_link)
                if meta:
                    image_url_for_threads = meta.get('image_url')
                    if not meta.get('image'):
                        override_image = await generate_ai_thumbnail(genai_client, summary, topic)
                    else:
                        override_image = meta.get('image')

            broadcast_tasks = [
                post_to_bluesky(bsky_client, client, summary, lead_link, override_image),
                post_to_mastodon(summary, override_image),
                post_to_threads(client, summary, image_url_for_threads)
            ]
            await asyncio.gather(*broadcast_tasks, return_exceptions=True)

            if news:
                for item in news[:10]:
                    if item['link'] not in seen_data["links"]:
                        seen_data["links"].append(item['link'])
            save_seen_articles(seen_data)
            await update_live_status(f"{context['session']} ({topic})")

if __name__ == "__main__":
    asyncio.run(main())
