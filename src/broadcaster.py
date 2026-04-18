import asyncio
import re
from mastodon import Mastodon
from atproto import AsyncClient, models
from src.utils import (
    retry_with_backoff, get_link_metadata, compress_image, 
    SafeLogger, truncate_bytes, get_image_mime, smart_truncate, smart_split,
    human_delay
)
from src.settings import settings

@retry_with_backoff
async def post_to_bluesky(bsky_client, client_shared, text, link=None, override_image=None):
    """Posts to Bluesky with Conditional Multi-Post Threading (The Weaver)."""
    if not settings.bsky_handle or not bsky_client:
        return

    chunks = smart_split(text, settings.bluesky_limit)
    root_post = None
    parent_post = None

    # Expert Review: Lead Image always attached to the FIRST post (The Cover)
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

    for i, chunk in enumerate(chunks):
        # Add pagination markers for threads (1/N)
        current_text = chunk
        if len(chunks) > 1:
            current_text = f"{chunk} ({i+1}/{len(chunks)})"

        # Calculate facets for the current chunk
        facets = []
        url_regex = re.compile(r'https?://[^\s]+')
        for match in url_regex.finditer(current_text):
            start = len(current_text[:match.start()].encode('utf-8'))
            end = len(current_text[:match.end()].encode('utf-8'))
            facets.append(models.AppBskyRichtextFacet.Main(
                features=[models.AppBskyRichtextFacet.Link(uri=match.group())],
                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=end)
            ))
        
        tag_regex = re.compile(r'#(\w+)')
        for match in tag_regex.finditer(current_text):
            start = len(current_text[:match.start()].encode('utf-8'))
            end = len(current_text[:match.end()].encode('utf-8'))
            facets.append(models.AppBskyRichtextFacet.Main(
                features=[models.AppBskyRichtextFacet.Tag(tag=match.group(1))],
                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=end)
            ))

        # Handle Chaining
        reply_ref = None
        if root_post and parent_post:
            reply_ref = models.AppBskyFeedPost.ReplyRef(
                root=models.ComAtprotoRepoStrongRef.Main(uri=root_post.uri, cid=root_post.cid),
                parent=models.ComAtprotoRepoStrongRef.Main(uri=parent_post.uri, cid=parent_post.cid)
            )

        # Chaining Delay
        if i > 0:
            await human_delay(settings.thread_pause_min, settings.thread_pause_max)

        # Post chunk
        resp = await bsky_client.send_post(
            text=current_text, 
            embed=embed if i == 0 else None, # Lead image on first post only
            facets=facets,
            reply_to=reply_ref
        )
        
        parent_post = resp
        if i == 0:
            root_post = resp
            
    SafeLogger.info(f"Successfully posted {len(chunks)}-part thread to Bluesky!")

@retry_with_backoff
async def post_to_mastodon(text, image_data=None):
    """Posts to Mastodon with Conditional Multi-Post Threading (The Weaver)."""
    if not settings.mastodon_token or not settings.mastodon_base_url:
        return

    chunks = smart_split(text, settings.mastodon_limit)
    
    loop = asyncio.get_running_loop()
    
    def _post_thread():
        m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
        media_ids = []
        if image_data:
            try:
                mime = get_image_mime(image_data)
                if mime:
                    media = m.media_post(image_data, mime_type=mime)
                    media_ids.append(media['id'])
            except Exception as e:
                SafeLogger.warn(f"Mastodon media failed: {e}")

        prev_id = None
        for i, chunk in enumerate(chunks):
            current_text = chunk
            if len(chunks) > 1:
                current_text = f"{chunk} ({i+1}/{len(chunks)})"
            
            # Chaining Delay
            if i > 0:
                asyncio.run_coroutine_threadsafe(
                    human_delay(settings.thread_pause_min, settings.thread_pause_max),
                    loop
                ).result()

            # Post chunk (Media only on the first post)
            status = m.status_post(
                current_text, 
                media_ids=media_ids if i == 0 else None,
                in_reply_to_id=prev_id
            )
            prev_id = status['id']

    await asyncio.to_thread(_post_thread)
    SafeLogger.info(f"Successfully posted {len(chunks)}-part thread to Mastodon!")

@retry_with_backoff
async def post_to_threads(client, text, image_url=None):
    """Posts to Threads with Conditional Multi-Post Threading (The Weaver)."""
    if not settings.threads_token or not settings.threads_user_id:
        return

    chunks = smart_split(text, settings.threads_limit)
    base_url = f"https://graph.threads.net/v1.0/{settings.threads_user_id}/threads"
    publish_url = f"https://graph.threads.net/v1.0/{settings.threads_user_id}/threads_publish"
    
    root_post_id = None
    
    for i, chunk in enumerate(chunks):
        current_text = chunk
        if len(chunks) > 1:
            current_text = f"{chunk} ({i+1}/{len(chunks)})"
            
        container_id = None
        # Lead Image ONLY on the first post
        if i == 0 and image_url:
            try:
                res = await client.post(base_url, data={
                    "media_type": "IMAGE", "image_url": image_url,
                    "text": current_text, "access_token": settings.threads_token
                }, timeout=20)
                res.raise_for_status()
                container_id = res.json().get("id")
            except Exception:
                SafeLogger.warn("Threads IMAGE container failed. Falling back to TEXT...")

        if not container_id:
            data = {
                "media_type": "TEXT", "text": current_text,
                "access_token": settings.threads_token
            }
            if root_post_id:
                data["reply_to"] = root_post_id
                
            res = await client.post(base_url, data=data, timeout=20)
            res.raise_for_status()
            container_id = res.json().get("id")

        # Wait for media processing
        for _ in range(3):
            status_res = await client.get(f"https://graph.threads.net/v1.0/{container_id}", params={"fields": "status", "access_token": settings.threads_token})
            if status_res.status_code == 200 and status_res.json().get("status") == "FINISHED":
                break
            await asyncio.sleep(2)

        # Publish
        publish_res = await client.post(publish_url, data={"creation_id": container_id, "access_token": settings.threads_token}, timeout=20)
        publish_res.raise_for_status()
        
        # Capture the FIRST post ID as the root for all subsequent replies
        if i == 0:
            root_post_id = publish_res.json().get("id")

        # Chaining Delay
        if i < len(chunks) - 1:
            await human_delay(settings.thread_pause_min, settings.thread_pause_max)

    SafeLogger.info(f"Successfully posted {len(chunks)}-part thread to Threads!")

async def update_social_profiles(bsky_client, mastodon_token, count, dialect, topic):
    """Dynamically update social media bios with exciting telemetry."""
    if not settings.enable_bio_management:
        return

    bio = f"🤖 BluBot v3.8 | {count:,} stories narrated | 🔍 Voice: {dialect} | Latest: {topic}"
    
    # 1. Bluesky
    if bsky_client and settings.bsky_handle:
        try:
            # actor.putProfile updates the profile record
            await bsky_client.app.bsky.actor.put_profile(data={
                "description": bio,
                "displayName": "BluBot Elite Sage"
            })
            SafeLogger.info("Bluesky bio updated successfully.")
        except Exception as e:
            SafeLogger.warn(f"Bluesky bio update failed: {e}")

    # 2. Mastodon
    if mastodon_token and settings.mastodon_base_url:
        try:
            from mastodon import Mastodon
            m = Mastodon(access_token=mastodon_token, api_base_url=settings.mastodon_base_url)
            m.account_update_credentials(note=bio)
            SafeLogger.info("Mastodon bio updated successfully.")
        except Exception as e:
            SafeLogger.warn(f"Mastodon bio update failed: {e}")
