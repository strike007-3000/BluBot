import asyncio
from mastodon import Mastodon
from atproto import AsyncClient, models
from .config import (
    BLUESKY_HANDLE, BLUESKY_PASSWORD, 
    MASTODON_TOKEN, MASTODON_BASE_URL, 
    THREADS_TOKEN, THREADS_USER_ID,
    BLUESKY_LIMIT, MASTODON_LIMIT, THREADS_LIMIT
)
from .utils import (
    retry_with_backoff, get_link_metadata, compress_image, 
    SafeLogger, truncate_bytes
)
import re

@retry_with_backoff
async def post_to_bluesky(bsky_client, client_shared, text, link=None, override_image=None):
    """Posts to Bluesky using an authenticated client, with Facets and byte-safe truncation."""
    if not BLUESKY_HANDLE:
        return

    # Expert Review Fix: Use byte-safe truncation BEFORE calculating facets
    # This prevents 'Forbidden' or 'Bad Request' errors due to out-of-bounds byte offsets.
    text = truncate_bytes(text, BLUESKY_LIMIT)

    facets = []
    
    # 1. URL Facets
    url_regex = re.compile(r'https?://[^\s]+')
    for match in url_regex.finditer(text):
        start = len(text[:match.start()].encode('utf-8'))
        end = len(text[:match.end()].encode('utf-8'))
        facets.append(models.AppBskyRichtextFacet.Main(
            features=[models.AppBskyRichtextFacet.Link(uri=match.group())],
            index=models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=end)
        ))
    
    # 2. Hashtag Facets
    tag_regex = re.compile(r'#(\w+)')
    for match in tag_regex.finditer(text):
        start = len(text[:match.start()].encode('utf-8'))
        end = len(text[:match.end()].encode('utf-8'))
        facets.append(models.AppBskyRichtextFacet.Main(
            features=[models.AppBskyRichtextFacet.Tag(tag=match.group(1))],
            index=models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=end)
        ))

    embed = None
    if link:
        meta = await get_link_metadata(client_shared, link)
        if meta:
            # Expert Review Fix: Sage Designer Override
            image_data = override_image if override_image else meta.get('image')
            
            thumb_blob = None
            if image_data:
                try:
                    # Expert Review Fix: Wrap CPU-bound compression in to_thread
                    compressed = await asyncio.to_thread(compress_image, image_data)
                    upload = await bsky_client.upload_blob(compressed)
                    thumb_blob = upload.blob
                except Exception as e: 
                    SafeLogger.warn(f"Failed to upload Bluesky thumbnail: {e}")

            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    title=meta['title'],
                    description=meta['description'],
                    uri=meta['url'],
                    thumb=thumb_blob
                )
            )

    await bsky_client.send_post(text=text, embed=embed, facets=facets)
    SafeLogger.info("Successfully posted to Bluesky!")

@retry_with_backoff
async def post_to_mastodon(text):
    """Posts to Mastodon using the standardized character limit."""
    if not MASTODON_TOKEN or not MASTODON_BASE_URL:
        return

    def _post():
        m = Mastodon(access_token=MASTODON_TOKEN, api_base_url=MASTODON_BASE_URL)
        m.status_post(text[:MASTODON_LIMIT])
    
    await asyncio.to_thread(_post)
    SafeLogger.info("Successfully posted to Mastodon!")

@retry_with_backoff
async def post_to_threads(client, text):
    """Posts to Threads using fully asynchronous logic and status validation."""
    if not THREADS_TOKEN or not THREADS_USER_ID:
        return

    # 1. Create Media Container
    base_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text[:THREADS_LIMIT],
        "access_token": THREADS_TOKEN
    }
    
    res = await client.post(base_url, data=payload, timeout=20)
    res.raise_for_status()
    container_id = res.json().get("id")

    # 2. Wait for READY state (Polling loop)
    # Even for text, a small check ensures robustness
    for _ in range(3):
        status_res = await client.get(
            f"https://graph.threads.net/v1.0/{container_id}",
            params={"fields": "status", "access_token": THREADS_TOKEN}
        )
        if status_res.status_code == 200 and status_res.json().get("status") == "FINISHED":
            break
        await asyncio.sleep(2)

    # 3. Publish
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    publish_res = await client.post(
        publish_url, 
        data={"creation_id": container_id, "access_token": THREADS_TOKEN}, 
        timeout=20
    )
    publish_res.raise_for_status()
    SafeLogger.info("Successfully posted to Threads!")
