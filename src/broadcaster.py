import asyncio
import re
from mastodon import Mastodon
from atproto import AsyncClient, models
from .utils import (
    retry_with_backoff, get_link_metadata, compress_image, 
    SafeLogger, truncate_bytes, get_image_mime
)
from .config import BLUESKY_LIMIT, MASTODON_LIMIT, THREADS_LIMIT

@retry_with_backoff
async def post_to_bluesky(bsky_client, client_shared, text, link=None, override_image=None):
    """Posts to Bluesky with full Facets support and byte-safe truncation."""
    from .config import BLUESKY_HANDLE
    if not BLUESKY_HANDLE or not bsky_client:
        return

    # Expert Review Fix: Byte-safe truncation
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
            image_data = override_image if override_image else meta.get('image')
            thumb_blob = None
            if image_data:
                try:
                    compressed = await asyncio.to_thread(compress_image, image_data)
                    if compressed:
                        upload = await bsky_client.upload_blob(compressed)
                        thumb_blob = upload.blob
                except Exception as e: 
                    SafeLogger.warn(f"Bluesky thumbnail failed: {e}")

            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    title=meta['title'], description=meta['description'],
                    uri=meta['url'], thumb=thumb_blob
                )
            )

    await bsky_client.send_post(text=text, embed=embed, facets=facets)
    SafeLogger.info("Successfully posted to Bluesky!")

@retry_with_backoff
async def post_to_mastodon(text, image_data=None):
    """Posts to Mastodon with dynamic MIME detection and retry handling."""
    from .config import MASTODON_TOKEN, MASTODON_BASE_URL
    if not MASTODON_TOKEN or not MASTODON_BASE_URL:
        return

    def _post():
        m = Mastodon(access_token=MASTODON_TOKEN, api_base_url=MASTODON_BASE_URL)
        media_ids = []
        if image_bytes := image_data:
            try:
                mime = get_image_mime(image_bytes)
                if mime:
                    media = m.media_post(image_bytes, mime_type=mime)
                    media_ids.append(media['id'])
            except Exception as e:
                SafeLogger.warn(f"Mastodon media failed: {e}")
                
        m.status_post(text[:MASTODON_LIMIT], media_ids=media_ids)
    
    await asyncio.to_thread(_post)
    SafeLogger.info("Successfully posted to Mastodon!")

@retry_with_backoff
async def post_to_threads(client, text, image_url=None):
    """Posts to Threads with IMAGE-to-TEXT fallback logic and delivery telemetry."""
    from .config import THREADS_TOKEN, THREADS_USER_ID
    if not THREADS_TOKEN or not THREADS_USER_ID:
        return

    base_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    container_id = None
    
    if image_url:
        try:
            res = await client.post(base_url, data={
                "media_type": "IMAGE", "image_url": image_url,
                "text": text[:THREADS_LIMIT], "access_token": THREADS_TOKEN
            }, timeout=20)
            res.raise_for_status()
            container_id = res.json().get("id")
        except Exception:
            SafeLogger.warn("Threads IMAGE failed. Falling back to TEXT...")

    if not container_id:
        res = await client.post(base_url, data={
            "media_type": "TEXT", "text": text[:THREADS_LIMIT],
            "access_token": THREADS_TOKEN
        }, timeout=20)
        res.raise_for_status()
        container_id = res.json().get("id")

    # Wait for media processing to finish
    for _ in range(3):
        status_res = await client.get(f"https://graph.threads.net/v1.0/{container_id}", params={"fields": "status", "access_token": THREADS_TOKEN})
        if status_res.status_code == 200 and status_res.json().get("status") == "FINISHED":
            break
        await asyncio.sleep(2)

    # Final publish step
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    try:
        publish_res = await client.post(publish_url, data={"creation_id": container_id, "access_token": THREADS_TOKEN}, timeout=20)
        
        # Expert Review Fix: Catch delivery errors but log them instead of raising (v3.6.3)
        # This prevents the global @retry_with_backoff from re-threading the whole post (Zero-Duplicate strategy)
        publish_res.raise_for_status()
        SafeLogger.info("Successfully posted to Threads!")
    except Exception as e:
        SafeLogger.error(f"Threads delivery failed: {e}. Check dashboard for status.")
