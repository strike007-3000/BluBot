import asyncio
import requests
from mastodon import Mastodon
from atproto import AsyncClient, models
from .config import (
    BLUESKY_HANDLE, BLUESKY_PASSWORD, 
    MASTODON_TOKEN, MASTODON_BASE_URL, 
    THREADS_TOKEN, THREADS_USER_ID
)
from .utils import retry_with_backoff, get_link_metadata, compress_image

@retry_with_backoff
async def post_to_bluesky(text, link=None):
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        return

    client = AsyncClient()
    await client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)

    embed = None
    if link:
        meta = await asyncio.to_thread(get_link_metadata, link)
        if meta:
            thumb_blob = None
            if meta['image']:
                try:
                    compressed = compress_image(meta['image'])
                    upload = await client.upload_blob(compressed)
                    thumb_blob = upload.blob
                except Exception: pass

            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    title=meta['title'],
                    description=meta['description'],
                    uri=meta['url'],
                    thumb=thumb_blob
                )
            )

    await client.send_post(text=text[:300], embed=embed)
    print("Successfully posted to Bluesky!", flush=True)

@retry_with_backoff
async def post_to_mastodon(text):
    if not MASTODON_TOKEN or not MASTODON_BASE_URL:
        return

    def _post():
        m = Mastodon(access_token=MASTODON_TOKEN, api_base_url=MASTODON_BASE_URL)
        m.status_post(text[:500])
    
    await asyncio.to_thread(_post)
    print("Successfully posted to Mastodon!", flush=True)

@retry_with_backoff
async def post_to_threads(text):
    if not THREADS_TOKEN or not THREADS_USER_ID:
        return

    def _post():
        base = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
        res = requests.post(base, data={"media_type": "TEXT", "text": text[:500], "access_token": THREADS_TOKEN}, timeout=15)
        res.raise_for_status()
        id = res.json().get("id")
        requests.post(f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish", data={"creation_id": id, "access_token": THREADS_TOKEN}, timeout=15).raise_for_status()

    await asyncio.to_thread(_post)
    print("Successfully posted to Threads!", flush=True)
