import sys
import os

# Intercept --dry-run CLI argument before any configuration is loaded
if "--dry-run" in sys.argv:
    os.environ["DRY_RUN"] = "true"

import asyncio
import httpx
import logging
from datetime import datetime, timezone
from typing import List, Tuple, Any, Optional

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
    generate_interactive_reply, prune_gemini_model_priority_async,
    generate_image_alt_text
)
from src.broadcaster import (
    post_to_bluesky, post_to_mastodon, post_to_threads,
    update_social_profiles, fetch_bluesky_mentions, fetch_mastodon_mentions,
    fetch_threads_replies
)
from src.telegram_gateway import (
    send_draft_for_approval, check_for_telegram_topic
)
from src.config import (
    STATUS_FILE_PATH, IMAGEN_MODEL,
    MENTION_REPLY_PROB, COMMENT_REPLY_PROB, INTERACTION_LIMIT, AUTO_LIKE_INTERACTIONS
)
from google.genai import types
from google import genai
from atproto import AsyncClient, AsyncRequest, models

def _update_status_dashboard_sync(session_name: str, topic: str):
    """Synchronous implementation of STATUS.md update to be offloaded to thread."""
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

async def update_status_dashboard(session_name: str, topic: str):
    """Automatically update the STATUS.md dashboard without blocking the event loop."""
    await asyncio.to_thread(_update_status_dashboard_sync, session_name, topic)

def article_matches_topic(title: str, summary: str, topic: str) -> bool:
    """Returns True if any significant keyword from topic matches the article title or summary."""
    if not topic:
        return False
    import re
    # Normalize and extract keywords from the topic, ignoring common stopwords
    stopwords = {
        "why", "how", "what", "who", "where", "when", "did", "could", "would", "should", 
        "does", "is", "was", "were", "are", "be", "been", "a", "an", "the", "and", "or", 
        "but", "if", "for", "on", "about", "to", "in", "of", "with", "at", "by", "from", 
        "concerning", "about", "discuss", "write", "post"
    }
    words = re.findall(r'\b\w+\b', topic.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 2]
    
    if not keywords:
        return False
        
    title_lower = title.lower()
    summary_lower = summary.lower()
    
    return any(kw in title_lower or kw in summary_lower for kw in keywords)

async def curation_stage(client: httpx.AsyncClient, telegram_topic: Optional[str] = None) -> CurationResult:
    """Stage 1: Fetch and Score Raw News."""
    seen_data = await asyncio.to_thread(load_seen_articles)
    context = get_temporal_context()

    from src.feed_vanguard import VanguardManager
    vanguard = VanguardManager()
    
    # Pre-flight: Refresh blacklist based on current health
    SafeLogger.info("Vanguard: Running pre-flight RSS health check...")
    await vanguard.audit_and_update(client)
    active_feeds = vanguard.get_active_feeds()
    
    raw_news = await fetch_news(client, seen_data["links"], seen_data["recent_topics"], feed_list=active_feeds)
    all_articles = [Article(**item) for item in raw_news]

    if telegram_topic:
        SafeLogger.info(f"Curation Stage: Filtering RSS articles for Telegram topic request: '{telegram_topic}'")
        matching_articles = []
        for a in all_articles:
            if article_matches_topic(a.title, a.summary, telegram_topic):
                matching_articles.append(a)
        
        if matching_articles:
            SafeLogger.info(f"Curation Stage: Found {len(matching_articles)} matching articles in RSS feeds.")
            articles = matching_articles
        else:
            SafeLogger.info(f"Curation Stage: No matching articles found in feeds for '{telegram_topic}'. Falling back to raw focus.")
            articles = [Article(
                title=f"On-demand topic request: {telegram_topic}",
                link="https://telegram.org",
                summary=f"Synthesize strategic insights regarding the topic: {telegram_topic}.",
                published=datetime.now(timezone.utc).isoformat(),
                source="Telegram Intercept",
                score=100,
                topic=telegram_topic
            )]
    else:
        articles = all_articles
    
    return CurationResult(
        top_articles=articles,
        seen_links=seen_data["links"],
        recent_topics=seen_data["recent_topics"],
        last_dialect=seen_data.get("last_dialect"),
        session_name=context['session']
    )

async def synthesis_stage(client: httpx.AsyncClient, genai_client: genai.Client, curation: CurationResult, telegram_topic: Optional[str] = None) -> Tuple[SynthesisResult, CurationResult]:
    """Stage 2: AI Summarization and Persona Application."""
    context = get_temporal_context()
    news_count = len(curation.top_articles)
    
    summary, lead_link, topic, is_failover = None, None, "General", False
    
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Generating mock synthesis summary.")
        summary = "DRY RUN: This is a mock synthesis summary of AI breakthrough news. #AI #Tech"
        lead_link = "https://example.com/mock-lead-link"
        topic = telegram_topic if telegram_topic else "DryRun"
        is_failover = False
    elif telegram_topic and not (news_count > 0 and not any(a.source == "Telegram Intercept" for a in curation.top_articles)):
        SafeLogger.info(f"Synthesis Stage: Generating on-demand post from scratch for topic: '{telegram_topic}'")
        try:
            from src.config import CURATOR_SYSTEM_INSTRUCTION
            prompt = (
                f"Write an elite tech insight post on the topic: '{telegram_topic}'.\n"
                "CRITICAL: If this topic is hypothetical, speculative, or references a potential future scenario (e.g. 'could be', 'what if', 'speculation'), "
                "do NOT write as if it has already occurred or is an established fact. Frame it hypothetically (e.g., 'If Cursor were to be acquired...'). "
                "Do not state unverified assumptions as facts."
            )
            response = await genai_client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=CURATOR_SYSTEM_INSTRUCTION, temperature=0.7)
            )
            summary = strip_markdown(response.text.strip())
            lead_link = "https://telegram.org"
            topic = telegram_topic
        except Exception as e:
            SafeLogger.warn(f"Telegram topic synthesis failed: {e}")
            summary, lead_link, topic, is_failover = await generate_mentor_insight(context)
    elif news_count > 3 or (telegram_topic and news_count > 0):
        # Curation flow: either normal flow with >3 articles or matched Telegram topic
        is_mentor_time = any(x in curation.session_name for x in ["Afternoon", "Evening", "Night"])
        mode = "Mentor" if is_mentor_time else "Curator"
        try:
            # Convert back to dict for legacy curator logic (minimizing regression)
            news_dicts = [vars(a) for a in curation.top_articles]
            summary, lead_link, topic, is_failover, current_dialect = await summarize_news(
                news_dicts, context, mode=mode, last_dialect=curation.last_dialect
            )
            if telegram_topic:
                topic = telegram_topic
            # v3.7.1 Fix: Propagate updated dialect back to main state
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

    # Strip formatting function (imported / defined inline)
    from src.curator import strip_markdown

    # Visual Asset Creation
    image_data, image_url = None, None
    visual_prompt = None
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

    # Alt text generation
    image_alt_text = None
    if image_data:
        alt_prompt = visual_prompt if visual_prompt else f"Minimalist tech illustration of {topic}"
        image_alt_text = await generate_image_alt_text(image_data, alt_prompt)

    return SynthesisResult(
        content=summary, 
        lead_link=lead_link, 
        topic=topic, 
        is_failover=is_failover,
        image_data=image_data,
        image_url=image_url,
        image_alt_text=image_alt_text
    ), curation

async def broadcast_stage(client: httpx.AsyncClient, synthesis: SynthesisResult) -> Tuple[List[BroadcastResult], Any]:
    """Stage 3: Multi-platform delivery."""
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Skip broadcasting to social networks.")
        SafeLogger.info(f"DRY RUN Synthesis:\n{synthesis.content}")
        if synthesis.image_alt_text:
            SafeLogger.info(f"DRY RUN Image Alt Text: {synthesis.image_alt_text}")
        return [
            BroadcastResult(platform="Bluesky", success=True),
            BroadcastResult(platform="Mastodon", success=True),
            BroadcastResult(platform="Threads", success=True)
        ], None

    # Bluesky Session Hardening
    bsky_client = AsyncClient(request=AsyncRequest(timeout=30.0))
    try:
        cached_session = await asyncio.to_thread(load_session_string)
        if cached_session:
            SafeLogger.info("Restoring cached Bluesky session...")
            await bsky_client.login(session_string=cached_session)
        else:
            SafeLogger.info("Initiating new Bluesky login...")
            await bsky_client.login(settings.bsky_handle, settings.bsky_password)
        session_str = bsky_client.export_session_string()
        await asyncio.to_thread(save_session_string, session_str)
    except Exception as e:
        SafeLogger.error(f"Bluesky auth failed: {e}")
        bsky_client = None

    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Skip broadcasting to social networks.")
        SafeLogger.info(f"DRY RUN Synthesis:\n{synthesis.content}")
        if synthesis.image_alt_text:
            SafeLogger.info(f"DRY RUN Image Alt Text: {synthesis.image_alt_text}")
        return [
            BroadcastResult(platform="Bluesky", success=True),
            BroadcastResult(platform="Mastodon", success=True),
            BroadcastResult(platform="Threads", success=True)
        ], None

    tasks = [
        ("Bluesky", post_to_bluesky(bsky_client, client, synthesis.content, synthesis.lead_link, synthesis.image_data, synthesis.image_alt_text)) if bsky_client else None,
        ("Mastodon", post_to_mastodon(synthesis.content, synthesis.image_data, synthesis.image_alt_text)),
        ("Threads", post_to_threads(client, synthesis.content, synthesis.image_url, synthesis.image_alt_text))
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
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Skip state persistence updates.")
        return

    # Load fresh state to ensure we have the latest counter
    state = await asyncio.to_thread(load_seen_articles)
    
    seen_links = set(state.get("links", []))
    for article in curation.top_articles[:10]:
        if article.link not in seen_links:
            state.setdefault("links", []).append(article.link)

    if synthesis.topic != "General" and synthesis.topic not in state.get("recent_topics", []):
        state.setdefault("recent_topics", []).append(synthesis.topic)

    # Update stats
    today_date = datetime.now(timezone.utc).date()
    if "start_date" not in state:
        state["start_date"] = "2026-03-31"
    
    try:
        from datetime import date
        start_dt = date.fromisoformat(state["start_date"])
        active_day = (today_date - start_dt).days + 1
    except Exception:
        active_day = 68  # Fallback

    # Increment total posts by 1 (actual synthesized post broadcast)
    state["total_posts_curated"] = state.get("total_posts_curated", 0) + 1
    state["last_dialect"] = curation.last_dialect
    
    # Cap history to prevent state bloat (Tier 1 constraint)
    state["links"] = state["links"][-500:]
    state["recent_topics"] = state["recent_topics"][-20:]

    await asyncio.to_thread(save_seen_articles, state)
    await update_status_dashboard(curation.session_name, synthesis.topic)

    # Dynamic Bio Update
    await update_social_profiles(
        client_bsky, 
        settings.mastodon_token, 
        active_day,
        synthesis.topic
    )

async def interaction_stage(bsky_client, http_client, session_context: dict) -> InteractionResult:
    """Handles social interactions (mentions/replies) with humanized engagement."""
    SafeLogger.info("Starting Interaction Stage (Mention Replies)...")
    seen_ids = await asyncio.to_thread(load_seen_interactions)
    replied_ids = []
    errors = []
    
    # 1. Fetch mentions
    bsky_mentions = await fetch_bluesky_mentions(bsky_client)
    mastodon_mentions = await fetch_mastodon_mentions()
    
    # 2. Fetch Threads replies
    threads_replies = []
    if settings.enable_threads_comment_replies:
        threads_replies = await fetch_threads_replies(http_client)
        
    all_mentions = bsky_mentions + mastodon_mentions + threads_replies
    
    # Filter and prioritize
    unseen = [m for m in all_mentions if m.id not in seen_ids]
    SafeLogger.info(f"Found {len(unseen)} new mentions/comments to process.")
    
    import random
    for mention in unseen[:INTERACTION_LIMIT]:
        # Differentiate replies from direct mentions
        is_reply = mention.root_uri is not None and mention.root_uri != mention.id
        reply_prob = COMMENT_REPLY_PROB if is_reply else MENTION_REPLY_PROB
        
        # Probabilistic engagement (Humanization)
        if random.random() > reply_prob:
            SafeLogger.info(f"Decision: Skipping reply to @{mention.author} on {mention.platform} (Engagement Roll).")
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
                    
            elif mention.platform == "threads":
                # Threads Reply
                base_url = f"https://graph.threads.net/v1.0/{settings.threads_user_id}/threads"
                publish_url = f"https://graph.threads.net/v1.0/{settings.threads_user_id}/threads_publish"
                
                res = await http_client.post(base_url, data={
                    "media_type": "TEXT",
                    "text": reply_text,
                    "reply_to": mention.id,
                    "access_token": settings.threads_token
                }, timeout=20)
                res.raise_for_status()
                container_id = res.json().get("id")
                
                for _ in range(3):
                    status_res = await http_client.get(
                        f"https://graph.threads.net/v1.0/{container_id}", 
                        params={"fields": "status", "access_token": settings.threads_token}
                    )
                    if status_res.status_code == 200 and status_res.json().get("status") == "FINISHED":
                        break
                    await asyncio.sleep(2)
                
                publish_res = await http_client.post(publish_url, data={
                    "creation_id": container_id,
                    "access_token": settings.threads_token
                }, timeout=20)
                publish_res.raise_for_status()
            
            replied_ids.append(mention.id)
            seen_ids.append(mention.id)
            SafeLogger.info(f"Successfully replied to @{mention.author} on {mention.platform}!")
            
        except Exception as e:
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {e}")
            errors.append(str(e))

    await asyncio.to_thread(save_seen_interactions, seen_ids)
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
        
        # Prune models dynamically at startup based on API limits
        await prune_gemini_model_priority_async(genai_client)
        
        # Check for on-demand Telegram topic intercept
        telegram_topic = await check_for_telegram_topic()

        # 1. Curation
        curation = await curation_stage(client, telegram_topic=telegram_topic)
        
        # 2. Synthesis
        context = get_temporal_context()
        synthesis, curation = await synthesis_stage(client, genai_client, curation, telegram_topic=telegram_topic)
        if not synthesis.content:
            SafeLogger.error("Synthesis produced no content. Aborting.")
            return

        # 2.5 Telegram Approval Stage (if enabled and not a dry-run)
        if settings.enable_telegram_approval and not settings.is_dry_run:
            final_content, final_image, final_alt = await send_draft_for_approval(
                text=synthesis.content,
                image_bytes=synthesis.image_data,
                image_alt_text=synthesis.image_alt_text,
                client=client,
                genai_client=genai_client,
                topic=synthesis.topic
            )
            if final_content is None:
                SafeLogger.info("Telegram: Draft rejected by user. Aborting execution.")
                return
            
            # Update synthesis with approved/edited text and media
            from dataclasses import replace
            synthesis = replace(synthesis, content=final_content, image_data=final_image, image_alt_text=final_alt)

        # 3. Broadcast
        SafeLogger.info(f"Initiating elite broadcast for topic: {synthesis.topic}")
        results, bsky_client = await broadcast_stage(client, synthesis)
        for res in results:
            if res.success:
                SafeLogger.info(f"{res.platform} broadcast successful.")
            else:
                SafeLogger.error(f"{res.platform} broadcast failed: {res.error}")

        # 4. Interaction (Mention Replies)
        if settings.enable_interactions and not settings.is_dry_run:
            interaction_res = await interaction_stage(bsky_client, client, context)
            SafeLogger.info(f"Interaction Session Complete: {len(interaction_res.replied_ids)} replies sent.")

        # 5. Persistence
        await persistence_stage(curation, synthesis, bsky_client)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
