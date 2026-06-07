import asyncio
import re
from datetime import datetime, timezone, timedelta
from mastodon import Mastodon
from atproto import AsyncClient, models
from src.utils import (
    retry_with_backoff, get_link_metadata, compress_image, 
    SafeLogger, truncate_bytes, get_image_mime, smart_truncate, smart_split,
    human_delay
)
from src.settings import settings
from src.config import VERSION

@retry_with_backoff
async def post_to_bluesky(bsky_client, client_shared, text, link=None, override_image=None):
    """Posts to Bluesky with Conditional Multi-Post Threading (The Weaver)."""
    if not settings.bsky_handle or not bsky_client:
        return

    # Safety Buffer: Account for pagination suffixes (e.g. " (1/2)")
    safe_limit = settings.bluesky_limit - 10
    chunks = smart_split(text, safe_limit, max_chunks=settings.max_thread_parts)
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
    # Safety Buffer: Account for pagination suffixes (e.g. " (1/2)") with higher margin for Mastodon
    safe_limit = settings.mastodon_limit - 15
    chunks = smart_split(text, safe_limit, max_chunks=settings.max_thread_parts)
    
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
    # Safety Buffer: Account for pagination suffixes
    safe_limit = settings.threads_limit - 10
    chunks = smart_split(text, safe_limit, max_chunks=settings.max_thread_parts)
    
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
                data["reply_to_id"] = root_post_id
                
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

async def fetch_bluesky_mentions(bsky_client):
    """Fetches recent mentions and replies from Bluesky within 24 hours."""
    if not bsky_client:
        return []
    
    try:
        from src.models import InteractionNote
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        resp = await bsky_client.app.bsky.notification.list_notifications()
        mentions = []
        
        # Decide which reasons to include based on settings
        valid_reasons = {'mention'}
        if settings.enable_bsky_comment_replies:
            valid_reasons.add('reply')

        for n in resp.notifications:
            if n.reason in valid_reasons and hasattr(n, 'record') and hasattr(n.record, 'text'):
                try:
                    indexed_dt = datetime.fromisoformat(n.indexed_at.replace("Z", "+00:00"))
                except Exception:
                    continue
                
                # Enforce 24-hour lookback
                if indexed_dt < cutoff:
                    continue

                # Filter self-replies
                if n.author.handle == settings.bsky_handle:
                    continue

                clean_text = n.record.text.strip()
                # Apply length and content filters to replies
                if n.reason == 'reply':
                    if len(clean_text) < 10 or not any(c.isalnum() for c in clean_text):
                        continue
                else:  # Direct mention
                    if len(clean_text) < 2 or not any(c.isalnum() for c in clean_text):
                        continue

                # Extract threading metadata
                root_uri = n.record.reply.root.uri if hasattr(n.record, 'reply') else n.uri
                root_cid = n.record.reply.root.cid if hasattr(n.record, 'reply') else n.cid
                
                mentions.append(InteractionNote(
                    platform="bluesky",
                    id=n.uri,
                    author=n.author.handle,
                    text=n.record.text,
                    timestamp=n.indexed_at,
                    uri=n.uri,
                    cid=n.cid,
                    root_uri=root_uri,
                    root_cid=root_cid
                ))
        return mentions
    except Exception as e:
        SafeLogger.debug(f"Failed to fetch Bluesky mentions: {e}")
        return []

async def fetch_mastodon_mentions():
    """Fetches recent mentions and replies from Mastodon within 24 hours."""
    if not settings.mastodon_token or not settings.mastodon_base_url:
        return []
    
    try:
        from src.models import InteractionNote
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
        # Use asyncio.to_thread for synchronous mastodon calls
        notifications = await asyncio.to_thread(m.notifications, types=['mention'])
        mentions = []
        for n in notifications:
            status = n.get('status')
            if status:
                is_reply = status.get('in_reply_to_id') is not None
                if is_reply and not settings.enable_mastodon_comment_replies:
                    continue

                created_at = status.get('created_at')
                if created_at:
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    # Enforce 24-hour lookback
                    if created_at < cutoff:
                        continue

                text = re.sub(r'<[^>]+>', '', status['content'])  # Strip HTML
                clean_text = text.strip()
                
                # Pre-filter logic
                if is_reply:
                    if len(clean_text) < 10 or not any(c.isalnum() for c in clean_text):
                        continue
                else:
                    if len(clean_text) < 2 or not any(c.isalnum() for c in clean_text):
                        continue

                mentions.append(InteractionNote(
                    platform="mastodon",
                    id=str(status['id']),
                    author=status['account']['acct'],
                    text=text,
                    timestamp=status['created_at'].isoformat() if hasattr(status['created_at'], 'isoformat') else str(status['created_at']),
                    root_uri=str(status['in_reply_to_id']) if status.get('in_reply_to_id') else None
                ))
        return mentions
    except Exception as e:
        SafeLogger.debug(f"Failed to fetch Mastodon mentions: {e}")
        return []

async def fetch_threads_replies(client):
    """Fetches recent replies to Threads posts within 24 hours."""
    if not settings.threads_token or not settings.threads_user_id or not settings.enable_threads_comment_replies:
        return []
    
    try:
        from src.models import InteractionNote
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Determine the bot's username to filter out self-replies
        own_username = None
        try:
            me_res = await client.get("https://graph.threads.net/v1.0/me", params={
                "fields": "username",
                "access_token": settings.threads_token
            }, timeout=10)
            if me_res.status_code == 200:
                own_username = me_res.json().get("username")
        except Exception:
            pass

        # 1. Fetch user's recent posts
        url = f"https://graph.threads.net/v1.0/{settings.threads_user_id}/threads"
        res = await client.get(url, params={
            "fields": "id,text,created_at",
            "access_token": settings.threads_token
        }, timeout=15)
        res.raise_for_status()
        posts = res.json().get("data", [])
        
        replies = []
        for post in posts:
            post_time_str = post.get("created_at")
            if not post_time_str:
                continue
            post_dt = datetime.fromisoformat(post_time_str.replace("Z", "+00:00"))
            # Skip checking posts older than 24 hours
            if post_dt < cutoff:
                continue
            
            # Fetch replies for this post
            replies_url = f"https://graph.threads.net/v1.0/{post['id']}/replies"
            rep_res = await client.get(replies_url, params={
                "fields": "id,text,username,created_at",
                "access_token": settings.threads_token
            }, timeout=15)
            rep_res.raise_for_status()
            for reply_data in rep_res.json().get("data", []):
                username = reply_data.get("username")
                if own_username and username == own_username:
                    continue

                reply_time_str = reply_data.get("created_at")
                if not reply_time_str:
                    continue
                reply_dt = datetime.fromisoformat(reply_time_str.replace("Z", "+00:00"))
                # Enforce 24-hour lookback on reply itself
                if reply_dt < cutoff:
                    continue
                
                text = reply_data.get("text", "")
                if len(text.strip()) < 10 or not any(c.isalnum() for c in text):
                    continue
                
                replies.append(InteractionNote(
                    platform="threads",
                    id=reply_data["id"],
                    author=username or "unknown",
                    text=text,
                    timestamp=reply_time_str,
                    uri=reply_data["id"],
                    cid=reply_data["id"],
                    root_uri=post["id"],
                    root_cid=post["id"]
                ))
        return replies
    except Exception as e:
        SafeLogger.debug(f"Failed to fetch Threads replies: {e}")
        return []

async def update_social_profiles(bsky_client, mastodon_token, active_day, topic):
    """Dynamically update social media bios with exciting telemetry."""
    if not settings.enable_bio_management:
        return

    bio = f"AI signal, zero noise. Day {active_day}. | Currently tracking: {topic}"
    
    # 1. Bluesky
    if bsky_client and settings.bsky_handle:
        try:
            # Fetch current profile to preserve all existing fields
            profile = None
            try:
                profile = await bsky_client.app.bsky.actor.profile.get(
                    repo=bsky_client.me.did,
                    rkey='self'
                )
            except Exception:
                pass

            if profile and profile.value:
                # Mutate the existing record object to preserve other fields (e.g. pinnedPost, self-labels, joinedViaStarterPack, pronouns, website)
                record = profile.value
                record.description = bio
            else:
                record = models.AppBskyActorProfile.Record(
                    description=bio,
                    display_name="BluBot Elite Sage"
                )

            await bsky_client.com.atproto.repo.put_record(
                models.ComAtprotoRepoPutRecord.Data(
                    collection='app.bsky.actor.profile',
                    repo=bsky_client.me.did,
                    rkey='self',
                    record=record
                )
            )
            SafeLogger.info("Bluesky bio updated successfully.")
        except Exception as e:
            SafeLogger.warn(f"Bluesky bio update failed: {e}")

    # 2. Mastodon
    if mastodon_token and settings.mastodon_base_url:
        try:
            from mastodon import Mastodon
            m = Mastodon(access_token=mastodon_token, api_base_url=settings.mastodon_base_url)
            await asyncio.to_thread(m.account_update_credentials, note=bio)
            SafeLogger.info("Mastodon bio updated successfully.")
        except Exception as e:
            SafeLogger.warn(f"Mastodon bio update failed: {e}")
