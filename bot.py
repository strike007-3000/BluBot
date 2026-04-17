import asyncio
import os
import httpx
import logging
from datetime import datetime, timezone
from typing import List, Tuple, Any

# Elite Architecture Imports
from src.settings import settings
from src import models as src_models
from src.models import (
    Article, CurationResult, SynthesisResult, BroadcastResult,
    InteractionNote, InteractionResult
)
from src.utils import (
    load_seen_articles, save_seen_articles, SafeLogger, 
    load_session_string, save_session_string, get_link_metadata,
    load_seen_interactions, save_seen_interactions, human_delay
)
from src.curator import (
    fetch_news, summarize_news, generate_mentor_insight, 
    get_temporal_context, generate_visual_prompt, generate_nvidia_image,
    generate_interactive_reply
)
from src.broadcaster import (
    post_to_bluesky, post_to_mastodon, post_to_threads,
    update_social_profiles, fetch_bluesky_mentions, fetch_mastodon_mentions
)
from src.config import (
    STATUS_FILE_PATH, IMAGEN_MODEL,
    MENTION_REPLY_PROB, INTERACTION_LIMIT, AUTO_LIKE_INTERACTIONS
)
from google.genai import types
from google import genai
from atproto import AsyncClient, AsyncRequest, models

async def update_status_dashboard(session_name: str, topic: str):
    """Automatically update the STATUS.md dashboard."""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        icon = "🚀" if "Morning" in session_name else "🔍"
        
        # Initialize if missing
        if not os.path.exists(STATUS_FILE_PATH):
            content = [
                "# 📊 BluBot System Telemetry\n\n",
                "Live status updates from the AI news curation engine.\n\n",
                "| Component | Status | Last Run | Mode |\n",
                "|:---|:---|:---|:---|\n",
                f"| **Broadcaster** | Operational | {today} | {icon} {session_name} ({topic}) |\n",
                "| **Signal Strength** | Elite (Natural) | -- | -- |\n"
            ]
            with open(STATUS_FILE_PATH, "w", encoding="utf-8") as f:
                f.writelines(content)
            return

        with open(STATUS_FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            if "| **Broadcaster** |" in line:
                new_lines.append(f"| **Broadcaster** | Operational | {today} | {icon} {session_name} ({topic}) |\n")
            elif "| **Signal Strength** |" in line:
                new_lines.append(f"| **Signal Strength** | Elite (Natural) | -- | -- |\n")
            else:
                new_lines.append(line)
        
        with open(STATUS_FILE_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        SafeLogger.debug(f"Dashboard update failed: {e}")

async def curation_stage(client: httpx.AsyncClient) -> CurationResult:
    """Stage 1: Fetch and Score Raw News."""
    from src.feed_vanguard import VanguardManager
    vanguard = VanguardManager()
    
    # Pre-flight: Refresh blacklist based on current health
    SafeLogger.info("Vanguard: Running pre-flight RSS health check...")
    await vanguard.audit_and_update(client)
    active_feeds = vanguard.get_active_feeds()
    
    seen_data = load_seen_articles()
    context = get_temporal_context()
    
    raw_news = await fetch_news(client, seen_data["links"], seen_data["recent_topics"], feed_list=active_feeds)
    articles = [Article(**item) for item in raw_news]
    
    return CurationResult(
        top_articles=articles,
        seen_links=seen_data["links"],
        recent_topics=seen_data["recent_topics"],
        last_dialect=seen_data.get("last_dialect"),
        session_name=context['session']
    )

async def synthesis_stage(client: httpx.AsyncClient, genai_client: genai.Client, curation: CurationResult) -> Tuple[SynthesisResult, CurationResult]:
    """Stage 2: AI Summarization and Persona Application."""
    context = get_temporal_context()
    news_count = len(curation.top_articles)
    
    summary, lead_link, topic, is_failover = None, None, "General", False
    
    if news_count > 3:
        # v3.7.0 logic: Morning/Midday -> Curator, Afternoon/Evening/Night -> Mentor
        is_mentor_time = any(x in curation.session_name for x in ["Afternoon", "Evening", "Night"])
        mode = "Mentor" if is_mentor_time else "Curator"
        try:
            # Convert back to dict for legacy curator logic (minimizing regression)
            news_dicts = [vars(a) for a in curation.top_articles]
            summary, lead_link, topic, is_failover, current_dialect = await summarize_news(
                news_dicts, context, mode=mode, last_dialect=curation.last_dialect
            )
            # Update curation result with the dialect used for persistence (requires non-frozen edit or re-init)
            # Since CurationResult is frozen, we re-instantiate
            curation = CurationResult(
                top_articles=curation.top_articles,
                seen_links=curation.seen_links,
                recent_topics=curation.recent_topics,
                last_dialect=current_dialect,
                session_name=curation.session_name,
                timestamp=curation.timestamp
            )
        except Exception as e:
            SafeLogger.warn(f"Synthesis failed, falling back to insight: {e}")
            summary, lead_link, topic, is_failover = await generate_mentor_insight(context)
    else:
        SafeLogger.info(f"Low volume ({news_count}), using Strategist Insight.")
        summary, lead_link, topic, is_failover = await generate_mentor_insight(context)

    if not summary:
        return SynthesisResult(content="", lead_link=None, topic="General"), curation

    # Visual Asset Creation
    image_data, image_url = None, None
    if lead_link:
        meta = await get_link_metadata(client, lead_link)
        if meta:
            image_url = meta.get('image_url')
            if not meta.get('image') and settings.enable_image_gen:
                visual_prompt = await generate_visual_prompt(genai_client, summary, topic)
                if settings.image_provider == "nvidia":
                    image_data = await generate_nvidia_image(client, visual_prompt)
            else:
                image_data = meta.get('image')

    return SynthesisResult(
        content=summary, 
        lead_link=lead_link, 
        topic=topic, 
        is_failover=is_failover,
        image_data=image_data,
        image_url=image_url
    ), curation

async def broadcast_stage(client: httpx.AsyncClient, synthesis: SynthesisResult) -> Tuple[List[BroadcastResult], Any]:
    """Stage 3: Multi-platform delivery."""
    # Bluesky Session Hardening
    bsky_client = AsyncClient(request=AsyncRequest(timeout=30.0))
    try:
        cached_session = load_session_string()
        if cached_session:
            SafeLogger.info("Restoring cached Bluesky session...")
            await bsky_client.login(session_string=cached_session)
        else:
            SafeLogger.info("Initiating new Bluesky login...")
            await bsky_client.login(settings.bsky_handle, settings.bsky_password)
        save_session_string(bsky_client.export_session_string())
    except Exception as e:
        SafeLogger.error(f"Bluesky auth failed: {e}")
        bsky_client = None

    tasks = [
        ("Bluesky", post_to_bluesky(bsky_client, client, synthesis.content, synthesis.lead_link, synthesis.image_data)) if bsky_client else None,
        ("Mastodon", post_to_mastodon(synthesis.content, synthesis.image_data)),
        ("Threads", post_to_threads(client, synthesis.content, synthesis.image_url))
    ]
    
    active = [t for t in tasks if t]
    results = await asyncio.gather(*[t[1] for t in active], return_exceptions=True)
    
    report = []
    for (name, _), res in zip(active, results):
        if isinstance(res, Exception):
            report.append(BroadcastResult(platform=name, success=False, error=str(res)))
        else:
            report.append(BroadcastResult(platform=name, success=True))
    return report, bsky_client

async def persistence_stage(curation: CurationResult, synthesis: SynthesisResult, client_bsky: Any = None):
    """Stage 4: State Synchronization."""
    # Load fresh state to ensure we have the latest counter
    state = load_seen_articles()
    
    seen_links = set(state.get("links", []))
    for article in curation.top_articles[:10]:
        if article.link not in seen_links:
            state.setdefault("links", []).append(article.link)

    if synthesis.topic != "General" and synthesis.topic not in state.get("recent_topics", []):
        state.setdefault("recent_topics", []).append(synthesis.topic)

    save_seen_articles({
        "links": curation.seen_links,
        "recent_topics": curation.recent_topics,
        "last_dialect": curation.last_dialect
    })
    await update_readme_dashboard(curation.session_name, synthesis.topic)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def interaction_stage(bsky_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = load_seen_interactions()
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    all_mentions = bsky_mentions + mastodon_mentions
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Probabilistic engagement (Humanization)
        if random.random() > MENTION_REPLY_PROB:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} (Engagement Roll).")
            seen_ids.append(mention.id)
            continue
            
        try:
            SafeLogger.info(f"Generating reply for @{mention.author} on {mention.platform}...")
            reply_text = await generate_interactive_reply(mention.text, mention.author, session_context)
            
            if not reply_text:
                continue
                
            # Human Delay before interaction
            await human_delay(10, 30)
            
            if mention.platform == "bluesky" and bsky_client:
                # Bluesky Reply with Threading
                parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.uri, cid=mention.cid)
                root_ref = models.ComAtprotoRepoStrongRef.Main(uri=mention.root_uri, cid=mention.root_cid) if mention.root_uri else parent_ref
                
                reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
                await bsky_client.send_post(text=reply_text, reply_to=reply_ref)
                
                if AUTO_LIKE_INTERACTIONS:
                    await bsky_client.like(mention.uri, mention.cid)
                    
            elif mention.platform == "mastodon":
                # Mastodon Reply
                from mastodon import Mastodon
                m = Mastodon(access_token=settings.mastodon_token, api_base_url=settings.mastodon_base_url)
                await asyncio.to_thread(m.status_post, reply_text, in_reply_to_id=mention.id)
                if AUTO_LIKE_INTERACTIONS:
                    await asyncio.to_thread(m.status_favourite, mention.id)
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    save_seen_interactions(seen_ids)
    return InteractionResult(processed_count=len(unseen), replied_ids=replied_ids, errors=errors)

async def main():
    if not settings.validate():
        return

    # Weekend Rest logic
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5 and now.hour >= 12 and not settings.should_bypass_rest:
        SafeLogger.info("Weekend rest initiated. Skipping post.")
        return

    logging.getLogger("atproto").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        genai_client = genai.Client(api_key=settings.gemini_key)
        
        # 1. Curation
        curation = await curation_stage(client)
        
        # 2. Synthesis
        context = get_temporal_context()
        synthesis, curation = await synthesis_stage(client, genai_client, curation)
        if not synthesis.content:
            SafeLogger.error("Synthesis produced no content. Aborting.")
            return

        # 3. Broadcast
        SafeLogger.info(f"Initiating elite broadcast for topic: {synthesis.topic}")
        results, bsky_client = await broadcast_stage(client, synthesis)
        for res in results:
            if res.success:
                SafeLogger.info(f"{res.platform} broadcast successful.")
            else:
                SafeLogger.error(f"{res.platform} broadcast failed: {res.error}")

        # 4. Interaction (Mention Replies)
        if settings.enable_interactions:
            interaction_res = await interaction_stage(bsky_client, context)
            SafeLogger.info(f"Interaction Session Complete: {len(interaction_res.replied_ids)} replies sent.")

        # 5. Persistence
        await persistence_stage(curation, synthesis, bsky_client)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
