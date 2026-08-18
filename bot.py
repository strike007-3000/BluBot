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
    InteractionNote, InteractionResult, MediaAsset, MediaSource
)
from src.utils import (
    load_seen_articles, save_seen_articles, SafeLogger, 
    load_session_string, save_session_string, get_link_metadata,
    load_seen_interactions, save_seen_interactions, human_delay,
    is_safe_url
)
from src.curator import (
    fetch_news, summarize_news, generate_mentor_insight, 
    get_temporal_context, generate_visual_prompt, generate_ai_image,
    generate_interactive_reply, prune_gemini_model_priority_async,
    generate_image_alt_text, strip_markdown
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
    """Returns True if all significant keywords from topic match (with inflections on word boundaries) the article title or summary."""
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
    target_words = set(re.findall(r'\b\w+\b', f"{title_lower} {summary_lower}"))
    
    for kw in keywords:
        # Generate valid inflection candidates for each keyword
        candidates = {kw}
        if kw.endswith('e'):
            root = kw[:-1]
            candidates.update({kw + 's', kw + 'd', root + 'ing', root + 'ition', root + 'itions'})
        else:
            candidates.update({kw + 's', kw + 'ed', kw + 'ing', kw + 'ion', kw + 'ions'})
            
        # Specific mappings for common terms
        if kw == 'acquire':
            candidates.update({'acquisition', 'acquisitions'})
        elif kw == 'acquisition':
            candidates.update({'acquire', 'acquires', 'acquired', 'acquiring'})
            
        # If none of the candidates exist as a full word in the target text, it's not a match
        if not (candidates & target_words):
            return False
            
    return True

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
    
    # If a telegram_topic is requested, bypass default top-8 limit to filter the full candidate list
    raw_news = await fetch_news(
        client, 
        seen_data["links"], 
        seen_data["recent_topics"], 
        feed_list=active_feeds, 
        limit=None if telegram_topic else 8,
        recent_categories=seen_data.get("recent_categories", []),
        watch_topics=seen_data.get("watch_topics", [])
    )
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
                link=None,
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
        session_name=context['session'],
        recent_categories=seen_data.get("recent_categories", []),
        recent_styles=seen_data.get("recent_styles", [])
    )

async def generate_briefing(client: httpx.AsyncClient, genai_client: genai.Client, topic: str) -> str:
    """Generates a grounded 7-day topic briefing using multi-source story clustering."""
    SafeLogger.info(f"Briefing Engine: Fetching 7-day RSS articles for topic: '{topic}'")
    seen_data = await asyncio.to_thread(load_seen_articles)
    
    from src.feed_vanguard import VanguardManager
    vanguard = VanguardManager()
    await vanguard.audit_and_update(client)
    active_feeds = vanguard.get_active_feeds()
    
    raw_news = await fetch_news(
        client,
        seen_links=[],  # Do not filter out previously seen articles for historical 7-day briefings
        recent_topics=seen_data.get("recent_topics", []),
        feed_list=active_feeds,
        limit=None,
        recent_categories=seen_data.get("recent_categories", []),
        watch_topics=seen_data.get("watch_topics", []),
        days_lookback=7
    )
    all_articles = [Article(**item) for item in raw_news]
    matching_articles = [a for a in all_articles if article_matches_topic(a.title, a.summary, topic)]
    
    if not matching_articles:
        return f"🔍 *7-Day Briefing for '{topic}'*\n\nNo articles matching this topic were found in RSS feeds over the past 7 days."
        
    article_bullets = []
    for idx, a in enumerate(matching_articles[:15]):
        corrob_str = f" [Corroborated by: {', '.join(a.supporting_sources)}]" if a.supporting_sources else ""
        article_bullets.append(f"{idx+1}. **{a.title}** ({a.source}){corrob_str}\n   Summary: {a.summary}\n   URL: {a.link}")
        
    articles_text = "\n\n".join(article_bullets)

    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Bypassing Gemini briefing synthesis.")
        return f"📊 *7-Day Executive Briefing: {topic} (DRY RUN)*\n\n**Executive Summary**\nThis is a mock executive briefing compiled under dry-run mode.\n\n**Key Developments**\n- Mock Development 1: Detailed mock description citation [Mock Source](https://example.com).\n\nSource articles analyzed:\n{articles_text}"
    
    prompt = (
        f"Generate a comprehensive, analytical executive briefing for the topic: '{topic}'.\n\n"
        f"Grounded Source Articles (Past 7 Days):\n{articles_text}\n\n"
        "Requirements:\n"
        "1. Write a clean, well-structured Telegram briefing in Markdown format.\n"
        "2. Provide an Executive Summary paragraph.\n"
        "3. Highlight 3-5 Key Developments or Trends based strictly on the provided articles.\n"
        "4. Include direct Markdown link citations [Title](URL) for each key development.\n"
        "5. If corroboration exists across multiple sources, explicitly highlight the consensus.\n"
        "6. Do not include hashtags or robotic introductory preambles."
    )
    
    try:
        from src.config import CURATOR_SYSTEM_INSTRUCTION
        response = await genai_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=CURATOR_SYSTEM_INSTRUCTION, temperature=0.5)
        )
        briefing_text = response.text.strip()
        header = f"📊 *7-Day Executive Briefing: {topic}*\n\n"
        return header + briefing_text
    except Exception as e:
        SafeLogger.error(f"Briefing synthesis failed: {e}")
        return f"⚠️ Failed to generate briefing for *{topic}*: {e}"

async def synthesis_stage(
    client: httpx.AsyncClient, 
    genai_client: genai.Client, 
    curation: CurationResult, 
    telegram_topic: Optional[str] = None
) -> Tuple[SynthesisResult, CurationResult]:
    """Stage 2: Synthesize Raw News into an Elite Tech Insight Post."""
    context = get_temporal_context()
    news_count = len(curation.top_articles)
    SafeLogger.info(f"Synthesis Stage: Processing {news_count} curated articles.")
    
    summary, lead_link, topic, is_failover = None, None, "General", False
    
    # Choose writing style from styles compatible with selected content
    from src.config import FEED_CATEGORY_MAP, STYLE_COMPATIBILITY, ALL_STYLES
    lead_article = curation.top_articles[0] if curation.top_articles else None
    lead_category = "unknown"
    if lead_article:
        lead_category = FEED_CATEGORY_MAP.get(lead_article.source_id, "unknown")
    
    compatible_styles = STYLE_COMPATIBILITY.get(lead_category, ALL_STYLES)
    if not compatible_styles:
        compatible_styles = ALL_STYLES
        
    recent_styles = curation.recent_styles or []
    last_indices = {}
    for style in compatible_styles:
        try:
            idx = len(recent_styles) - 1 - recent_styles[::-1].index(style)
        except ValueError:
            idx = -1
        last_indices[style] = idx
        
    sorted_styles = sorted(compatible_styles, key=lambda s: last_indices[s])
    chosen_style = sorted_styles[0]
    
    has_only_synthetic = all(a.source == "Telegram Intercept" for a in curation.top_articles)
    use_scratch_synthesis = telegram_topic and (news_count == 0 or has_only_synthetic)

    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Generating mock synthesis summary.")
        summary = "DRY RUN: This is a mock synthesis summary of AI breakthrough news. #AI #Tech"
        lead_link = "https://example.com/mock-lead-link"
        topic = telegram_topic if telegram_topic else "DryRun"
        is_failover = False
    elif use_scratch_synthesis:
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
            lead_link = None
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
                news_dicts, context, mode=mode, last_dialect=curation.last_dialect, writing_style=chosen_style
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
                timestamp=curation.timestamp,
                recent_categories=curation.recent_categories,
                recent_styles=curation.recent_styles
            )
        except Exception as e:
            SafeLogger.warn(f"Synthesis failed, falling back to insight: {e}")
            summary, lead_link, topic, is_failover = await generate_mentor_insight(context)
    else:
        SafeLogger.info(f"Low volume ({news_count}), using Strategist Insight.")
        summary, lead_link, topic, is_failover = await generate_mentor_insight(context)

    if not summary:
        return SynthesisResult(content="", lead_link=None, topic="General", writing_style=chosen_style), curation


    return SynthesisResult(
        content=summary, 
        lead_link=lead_link, 
        topic=topic, 
        is_failover=is_failover,
        media=None,
        writing_style=chosen_style
    ), curation

async def media_strategy_stage(client, genai_client, synthesis: SynthesisResult, curation: CurationResult) -> Optional[MediaAsset]:
    """Dedicated media decision stage (Step 1 & 2 & 3 & 4 & 5)."""
    from src.models import MediaAsset, MediaSource
    from src.curator import validate_opengraph_image, generate_visual_prompt, generate_ai_image, generate_image_alt_text
    from src.utils import get_image_mime, SafeLogger
    from PIL import Image
    import io
    
    # Defaults and info for logging
    lead_link = synthesis.lead_link
    has_lead_link = lead_link is not None
    
    # Extract category for prompts
    category = "unknown"
    lead_article = curation.top_articles[0] if curation.top_articles else None
    if lead_article:
        from src.config import FEED_CATEGORY_MAP
        category = FEED_CATEGORY_MAP.get(lead_article.source_id, "unknown")
        
    validation_res = None
    image_bytes = None
    public_url = None
    source = None
    alt_text = None
    
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Constructing mock MediaAsset.")
        return MediaAsset(
            source=MediaSource.GENERATED,
            image_bytes=b"mock_dry_run_image_bytes",
            public_url="https://example.com/mock-dry-run-image.png",
            mime_type="image/png",
            width=1200,
            height=630,
            alt_text="Mock dry-run tech illustration.",
            attribution_url=lead_link
        )

    # 1. Valid lead link and valid OpenGraph image -> use OpenGraph asset
    if has_lead_link:
        try:
            meta = await get_link_metadata(client, lead_link)
            if meta:
                og_url = meta.get('image_url')
                og_bytes = meta.get('image')
                
                if og_bytes:
                    # Validate OpenGraph image
                    validation_res = validate_opengraph_image(og_bytes, og_url or "")
                    if validation_res.valid:
                        image_bytes = og_bytes
                        public_url = og_url
                        source = MediaSource.OPENGRAPH
                        # Generate alt text for OpenGraph image
                        alt_text = await generate_image_alt_text(og_bytes, f"OpenGraph image for {synthesis.topic}")
                    else:
                        SafeLogger.info(f"OpenGraph validation failed: {validation_res.reason}. Falling back to AI Image generation.")
                elif og_url and is_safe_url(og_url):
                    # Capture public URL even if download failed/was blocked, allowing threads/link-only fallback
                    public_url = og_url
        except Exception as e:
            SafeLogger.warn(f"Failed to fetch metadata or validate OpenGraph: {e}")
    
    # 2. Lead link but invalid/missing OpenGraph image OR No lead link -> generate illustration if enabled
    if not source and settings.enable_image_gen:
        try:
            # Generate visual prompt (passing category)
            visual_prompt = await generate_visual_prompt(genai_client, synthesis.content, synthesis.topic, category)
            
            # Generate AI image based on configured provider
            gen_bytes = await generate_ai_image(client, genai_client, visual_prompt)
            if gen_bytes:
                image_bytes = gen_bytes
                public_url = None
                source = MediaSource.GENERATED
                
                # Generate alt text for generated image
                alt_prompt = visual_prompt if visual_prompt else f"Minimalist tech illustration of {synthesis.topic}"
                alt_text = await generate_image_alt_text(gen_bytes, alt_prompt)
            else:
                SafeLogger.warn(f"AI image generation ({settings.image_provider}) returned no bytes.")
        except Exception as e:
            SafeLogger.warn(f"AI image generation failed: {e}")
            
    # 3. Fallback/Final Asset Construction
    if not source and public_url:
        source = MediaSource.OPENGRAPH

    if source and (image_bytes or public_url):
        mime_type = get_image_mime(image_bytes) if image_bytes else None
        width, height = None, None
        if image_bytes:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                width, height = img.size
            except Exception:
                pass
            
        media = MediaAsset(
            source=source,
            image_bytes=image_bytes,
            public_url=public_url,
            mime_type=mime_type,
            width=width,
            height=height,
            alt_text=alt_text,
            attribution_url=lead_link
        )
    else:
        media = None
        
    # 4. Structured Logging (Step 8 & 6 refinements)
    log_lines = [
        "Media Strategy",
        "--------------",
        f"Article: {'Yes' if has_lead_link else 'No'}",
        f"OpenGraph: {'Valid' if source == MediaSource.OPENGRAPH else 'Rejected' if validation_res else 'N/A'}"
    ]
    if validation_res and not validation_res.valid:
        log_lines.append(f"  Reason: {validation_res.reason}")
        
    log_lines.append(f"AI: {'Generated' if source == MediaSource.GENERATED else 'Skipped' if source == MediaSource.OPENGRAPH else 'Failed' if settings.enable_image_gen else 'Disabled'}")
    
    # dimensions, MIME type, and byte size
    if media:
        log_lines.append(f"Dimensions: {media.width}x{media.height}")
        log_lines.append(f"MIME type: {media.mime_type}")
        byte_size_str = f"{len(media.image_bytes)} bytes" if media.image_bytes else "None"
        log_lines.append(f"Byte size: {byte_size_str}")
    
    # intended delivery modes
    bsky_mode = "External card" if has_lead_link else "Image embed" if media else "Text only"
    mast_mode = "Uploaded media" if media else "Text only"
    threads_mode = "Hosted image" if (media and media.public_url) else "Text only"
    
    log_lines.append(f"Bluesky: {bsky_mode}")
    log_lines.append(f"Mastodon: {mast_mode}")
    log_lines.append(f"Threads: {threads_mode}")
    
    if not media:
        log_lines.append("Text-only Fallback: Yes")
        
    SafeLogger.info("\n".join(log_lines))
    
    return media

async def broadcast_stage(client: httpx.AsyncClient, synthesis: SynthesisResult) -> Tuple[List[BroadcastResult], Any]:
    """Stage 3: Multi-platform delivery."""
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Skip broadcasting to social networks.")
        SafeLogger.info(f"DRY RUN Synthesis:\n{synthesis.content}")
        if synthesis.media and synthesis.media.alt_text:
            SafeLogger.info(f"DRY RUN Image Alt Text: {synthesis.media.alt_text}")
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

    tasks = [
        ("Bluesky", post_to_bluesky(bsky_client, client, synthesis.content, synthesis.lead_link, synthesis.media)) if bsky_client else None,
        ("Mastodon", post_to_mastodon(synthesis.content, synthesis.media)),
        ("Threads", post_to_threads(client, synthesis.content, synthesis.media))
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
        if article.link and article.link not in seen_links:
            state.setdefault("links", []).append(article.link)
            seen_links.add(article.link)
        if article.supporting_links:
            for s_link in article.supporting_links:
                if s_link and s_link not in seen_links:
                    state.setdefault("links", []).append(s_link)
                    seen_links.add(s_link)

    if synthesis.topic != "General" and synthesis.topic not in state.get("recent_topics", []):
        state.setdefault("recent_topics", []).append(synthesis.topic)

    published_category = "unknown"
    if synthesis.lead_link:
        for article in curation.top_articles:
            if article.link == synthesis.lead_link:
                from src.config import FEED_CATEGORY_MAP
                published_category = FEED_CATEGORY_MAP.get(article.source_id, "unknown")
                break
    elif curation.top_articles:
        from src.config import FEED_CATEGORY_MAP
        published_category = FEED_CATEGORY_MAP.get(curation.top_articles[0].source_id, "unknown")

    state.setdefault("recent_categories", []).append(published_category)
    state["recent_categories"] = state["recent_categories"][-10:]

    if synthesis.writing_style:
        state.setdefault("recent_styles", []).append(synthesis.writing_style)
        state["recent_styles"] = state["recent_styles"][-10:]

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
                    "reply_to_id": mention.id,
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

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as client:
        genai_client = genai.Client(api_key=settings.gemini_key)
        
        # Prune models dynamically at startup based on API limits
        await prune_gemini_model_priority_async(genai_client)
        
        # Check for on-demand Telegram topic or brief intercept
        res = await check_for_telegram_topic()
        if isinstance(res, tuple):
            cmd_type, telegram_topic = res
        else:
            cmd_type, telegram_topic = ("topic" if res else None), res

        if cmd_type == "brief":
            SafeLogger.info(f"Brief Engine: Generating 7-day briefing for topic '{telegram_topic}'")
            briefing = await generate_briefing(client, genai_client, telegram_topic)
            if settings.telegram_bot_token and settings.telegram_user_id and not settings.is_dry_run:
                try:
                    from telegram import Bot
                    from src.utils import smart_split
                    bot = Bot(token=settings.telegram_bot_token)
                    chunks = smart_split(briefing, 4096)  # No max_chunks cap for Telegram briefing delivery
                    for chunk in chunks:
                        await bot.send_message(chat_id=settings.telegram_user_id, text=chunk, parse_mode="Markdown")
                    SafeLogger.info("Briefing Engine: Successfully delivered briefing to Telegram.")
                except Exception as e:
                    SafeLogger.error(f"Briefing Engine: Failed to deliver briefing: {e}")
            else:
                SafeLogger.info(f"Briefing Output:\n{briefing}")
            return

        # 1. Curation
        curation = await curation_stage(client, telegram_topic=telegram_topic)
        
        # 2. Synthesis
        context = get_temporal_context()
        synthesis, curation = await synthesis_stage(client, genai_client, curation, telegram_topic=telegram_topic)
        if not synthesis.content:
            SafeLogger.error("Synthesis produced no content. Aborting.")
            return

        # 2.2 Media Strategy Decision
        media = await media_strategy_stage(client, genai_client, synthesis, curation)
        from dataclasses import replace
        synthesis = replace(synthesis, media=media)

        # 2.5 Telegram Approval Stage (if enabled and not a dry-run)
        if settings.enable_telegram_approval and not settings.is_dry_run:
            final_content, final_media = await send_draft_for_approval(
                text=synthesis.content,
                media=synthesis.media,
                client=client,
                genai_client=genai_client,
                topic=synthesis.topic
            )
            if final_content is None:
                SafeLogger.info("Telegram: Draft rejected by user. Aborting execution.")
                return
            
            synthesis = replace(
                synthesis,
                content=final_content,
                media=final_media
            )

        # 2.8 Pre-Broadcast Lead Resolution & Reservation Contract
        if not synthesis.lead_link:
            SafeLogger.error("Synthesis lead_link is missing or ambiguous. Aborting execution before broadcast.")
            sys.exit(1)

        from src.utils import normalize_url, load_seen_articles, save_seen_articles
        canonical_lead = normalize_url(synthesis.lead_link)
        matched_article = None
        for art in curation.top_articles:
            if art.link and normalize_url(art.link) == canonical_lead:
                matched_article = art
                break

        if not matched_article:
            if canonical_lead:
                from src.models import Article
                matched_article = Article(
                    title=getattr(synthesis, 'topic', 'Published Article'),
                    link=synthesis.lead_link,
                    summary='',
                    published=datetime.now(timezone.utc).isoformat(),
                    source='Synthesis Lead'
                )
            else:
                SafeLogger.error(f"Lead link '{synthesis.lead_link}' could not be unambiguously resolved. Aborting broadcast.")
                sys.exit(1)

        # Write pending reservation before broadcast
        state = await asyncio.to_thread(load_seen_articles)
        pending_entry = {
            "url": canonical_lead,
            "title": matched_article.title,
            "stage": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        state.setdefault("pending_stories", []).append(pending_entry)
        res_ok = await asyncio.to_thread(save_seen_articles, state, is_reservation=True)
        if settings.gist_id and settings.gist_token and not res_ok:
            SafeLogger.error("CRITICAL: Authoritative Gist pending reservation failed. Aborting publication.")
            # Roll back memory state
            state["pending_stories"].pop()
            sys.exit(1)

        # 3. Broadcast
        SafeLogger.info(f"Initiating elite broadcast for topic: {synthesis.topic}")
        results, bsky_client = await broadcast_stage(client, synthesis)
        for res in results:
            if res.success:
                SafeLogger.info(f"{res.platform} broadcast successful.")
            else:
                SafeLogger.error(f"{res.platform} broadcast failed: {res.error}")

        # 3.5 Immediate Post-Broadcast Settlement
        any_success = any(res.success for res in results)
        
        # Remove pending entry regardless of outcome
        state["pending_stories"] = [ps for ps in state.get("pending_stories", []) if ps.get("url") != canonical_lead]
        
        if any_success:
            pub_entry = {
                "url": canonical_lead,
                "title": matched_article.title,
                "supporting_links": [normalize_url(sl) for sl in (matched_article.supporting_links or []) if sl],
                "stage": "published",
                "published_at": datetime.now(timezone.utc).isoformat()
            }
            state.setdefault("recent_stories", []).append(pub_entry)
            state.setdefault("links", [])
            if canonical_lead not in state["links"]:
                state["links"].append(canonical_lead)
            for sl in pub_entry["supporting_links"]:
                if sl not in state["links"]:
                    state["links"].append(sl)

            if synthesis.topic != "General" and synthesis.topic not in state.get("recent_topics", []):
                state.setdefault("recent_topics", []).append(synthesis.topic)

            from src.config import FEED_CATEGORY_MAP
            published_category = FEED_CATEGORY_MAP.get(matched_article.source_id, "unknown")
            state.setdefault("recent_categories", []).append(published_category)
            state["recent_categories"] = state["recent_categories"][-10:]

            if synthesis.writing_style:
                state.setdefault("recent_styles", []).append(synthesis.writing_style)
                state["recent_styles"] = state["recent_styles"][-10:]

            state["total_posts_curated"] = state.get("total_posts_curated", 0) + 1
            state["last_dialect"] = curation.last_dialect
            state["links"] = state["links"][-500:]
            state["recent_topics"] = state["recent_topics"][-20:]

            settle_ok = await asyncio.to_thread(save_seen_articles, state, is_reservation=False)
            if settings.gist_id and settings.gist_token and not settle_ok:
                SafeLogger.error("Post-broadcast settlement failed to sync to Gist. Local recovery state written.")
                sys.exit(1)
        else:
            await asyncio.to_thread(save_seen_articles, state, is_reservation=False)
            SafeLogger.error("All broadcast targets failed. Pending reservation cleared.")
            sys.exit(1)

        # 4. Post-Persistence Nonessential Tasks
        today_date = datetime.now(timezone.utc).date()
        if "start_date" not in state:
            state["start_date"] = "2026-03-31"
        try:
            from datetime import date
            start_dt = date.fromisoformat(state["start_date"])
            active_day = (today_date - start_dt).days + 1
        except Exception:
            active_day = 68

        await update_status_dashboard(curation.session_name, synthesis.topic)
        await update_social_profiles(bsky_client, settings.mastodon_token, active_day, synthesis.topic)

        if settings.enable_interactions and not settings.is_dry_run:
            interaction_res = await interaction_stage(bsky_client, client, context)
            SafeLogger.info(f"Interaction Session Complete: {len(interaction_res.replied_ids)} replies sent.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
