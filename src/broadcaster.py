import asyncio
import re
from mastodon import Mastodon
from atproto import AsyncClient, models
from .utils import (
    retry_with_backoff, get_link_metadata, compress_image, 
    SafeLogger, truncate_bytes, get_image_mime
)
from .settings import settings

@retry_with_backoff
async def post_to_bluesky(bsky_client, client_shared, text, link=None, override_image=None):
    """Posts to Bluesky with full Facets support and byte-safe truncation."""
    if not settings.bsky_handle or not bsky_client:
        return

    # Expert Review Fix: Byte-safe truncation
    text = truncate_bytes(text, settings.bluesky_limit)
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
    if not settings.mastodon_token or not settings.mastodon_base_url:
        return

    def _post():
        m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
        media_ids = []
        if image_bytes := image_data:
            try:
                mime = get_image_mime(image_bytes)
                if mime:
                    media = m.media_post(image_bytes, mime_type=mime)
                    media_ids.append(media['id'])
            except Exception as e:
                SafeLogger.warn(f"Mastodon media failed: {e}")
                
        m.status_post(text[:settings.mastodon_limit], media_ids=media_ids)
    
    await asyncio.to_thread(_post)
    SafeLogger.info("Successfully posted to Mastodon!")

@retry_with_backoff
async def post_to_threads(client, text, image_url=None):
    """Posts to Threads with IMAGE-to-TEXT fallback logic and delivery telemetry."""
    if not settings.threads_token or not settings.threads_user_id:
        return

    base_url = f"https://graph.threads.net/v1.0/{settings.threads_user_id}/threads"
    container_id = None
    
    if image_url:
        try:
            res = await client.post(base_url, data={
                "media_type": "IMAGE", "image_url": image_url,
                "text": text[:settings.threads_limit], "access_token": settings.threads_token
            }, timeout=20)
            res.raise_for_status()
            container_id = res.json().get("id")
        except Exception:
            SafeLogger.warn("Threads IMAGE failed. Falling back to TEXT...")

    if not container_id:
        res = await client.post(base_url, data={
            "media_type": "TEXT", "text": text[:settings.threads_limit],
            "access_token": settings.threads_token
        }, timeout=20)
        res.raise_for_status()
        container_id = res.json().get("id")

    # Wait for media processing to finish
    for _ in range(3):
        status_res = await client.get(f"https://graph.threads.net/v1.0/{container_id}", params={"fields": "status", "access_token": settings.threads_token})
        if status_res.status_code == 200 and status_res.json().get("status") == "FINISHED":
            break
        await asyncio.sleep(2)

    # Final publish step
    publish_url = f"https://graph.threads.net/v1.0/{settings.threads_user_id}/threads_publish"
    try:
        publish_res = await client.post(publish_url, data={"creation_id": container_id, "access_token": settings.threads_token}, timeout=20)
        publish_res.raise_for_status()
        SafeLogger.info("Successfully posted to Threads!")
    except Exception as e:
        # P1 Badge: Propagate delivery failure to orchestrator but skip global retry (Zero-Duplicate)
        SafeLogger.error(f"Threads delivery failed: {e}. Check dashboard for status.")
        setattr(e, "skip_backoff_retry", True)
        raise
