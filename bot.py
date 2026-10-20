import sys
import os

# Intercept --dry-run CLI argument before any configuration is loaded
if "--dry-run" in sys.argv:
    os.environ["DRY_RUN"] = "true"
if "--roundup" in sys.argv:
    os.environ["FORCE_ROUNDUP"] = "true"

import asyncio
import httpx
import logging
import time
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
    is_safe_url, normalize_url, compute_story_fingerprint, smart_truncate,
    smart_split, PUBLISHED_POSTS_CAP,
)
from src.curator import (
    fetch_news, summarize_news, generate_mentor_insight,
    get_temporal_context, generate_visual_prompt, generate_ai_image,
    generate_interactive_reply, prune_gemini_model_priority_async,
    generate_image_alt_text, strip_markdown
)
from src.broadcaster import (
    post_to_bluesky, post_to_mastodon, post_to_threads, post_bluesky_receipt,
    update_social_profiles, fetch_bluesky_mentions, fetch_mastodon_mentions,
    fetch_threads_replies
)
from src.telegram_gateway import (
    send_draft_for_approval, check_for_telegram_topic,
    send_broadcast_platform_messages
)
from src.config import (
    STATUS_FILE_PATH, IMAGEN_MODEL,
    MENTION_REPLY_PROB, COMMENT_REPLY_PROB, INTERACTION_LIMIT, AUTO_LIKE_INTERACTIONS,
    BRIEFING_SYSTEM_INSTRUCTION
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
    from src.utils import filter_and_update_pending_stories
    suppressed_urls = filter_and_update_pending_stories(seen_data)
    combined_seen_links = list(set(seen_data.get("links", [])) | suppressed_urls)

    context = get_temporal_context()

    from src.feed_vanguard import VanguardManager
    vanguard = await asyncio.to_thread(VanguardManager)
    active_feeds = vanguard.get_active_feeds()

    # If a telegram_topic is requested, bypass default top-8 limit to filter the full candidate list
    raw_news, feed_outcomes = await fetch_news(
        client,
        combined_seen_links,
        seen_data["recent_topics"],
        feed_list=active_feeds,
        limit=None if telegram_topic else 8,
        recent_categories=seen_data.get("recent_categories", []),
        watch_topics=seen_data.get("watch_topics", []),
        story_state=seen_data
    )
    await asyncio.to_thread(vanguard.apply_feed_outcomes, feed_outcomes)

    all_articles = [Article(**item) for item in raw_news]

    if telegram_topic:
        SafeLogger.info(f"Curation Stage: Filtering source items for Telegram topic request: '{telegram_topic}'")
        matching_articles = []
        for a in all_articles:
            if article_matches_topic(a.title, a.summary, telegram_topic):
                matching_articles.append(a)

        if matching_articles:
            SafeLogger.info(f"Curation Stage: Found {len(matching_articles)} matching source items.")
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
    SafeLogger.info(f"Briefing Engine: Fetching 7-day source items for topic: '{topic}'")
    seen_data = await asyncio.to_thread(load_seen_articles)

    from src.feed_vanguard import VanguardManager
    vanguard = await asyncio.to_thread(VanguardManager)
    active_feeds = vanguard.get_active_feeds()

    raw_news, feed_outcomes = await fetch_news(
        client,
        seen_links=[],  # Do not filter out previously seen articles for historical 7-day briefings
        recent_topics=seen_data.get("recent_topics", []),
        feed_list=active_feeds,
        limit=None,
        recent_categories=seen_data.get("recent_categories", []),
        watch_topics=seen_data.get("watch_topics", []),
        days_lookback=7
    )
    await asyncio.to_thread(vanguard.apply_feed_outcomes, feed_outcomes)
    all_articles = [Article(**item) for item in raw_news]
    matching_articles = [a for a in all_articles if article_matches_topic(a.title, a.summary, topic)]

    if not matching_articles:
        return f"🔍 *7-Day Briefing for '{topic}'*\n\nNo matching source items were found over the past 7 days."

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
        response = await genai_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=BRIEFING_SYSTEM_INSTRUCTION, temperature=0.5)
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
    telegram_topic: Optional[str] = None,
    decision: Optional[Any] = None
) -> Tuple[SynthesisResult, CurationResult]:
    """Stage 2: Synthesize Raw News into an Elite Tech Insight Post or Thread Update."""
    context = get_temporal_context()
    news_count = len(curation.top_articles)
    SafeLogger.info(f"Synthesis Stage: Processing {news_count} curated articles.")

    summary, lead_link, topic, is_failover = None, None, "General", False

    # Check for update mode synthesis
    if decision and getattr(decision, "mode", None) == "update" and getattr(decision, "parent_entry", None):
        lead_art = curation.top_articles[0] if curation.top_articles else None
        if lead_art:
            from src.curator import summarize_update
            lead_dict = vars(lead_art)
            SafeLogger.info(f"Synthesis Stage: Executing dedicated update synthesis for parent '{decision.parent_fingerprint}'")
            up_res = await summarize_update(
                new_article=lead_dict,
                parent_entry=decision.parent_entry,
                context=context
            )
            summary, lead_link, topic, is_failover, current_dialect, platform_drafts = up_res
            return SynthesisResult(
                content=summary,
                lead_link=lead_link,
                topic=topic,
                is_failover=is_failover,
                media=None,
                writing_style="UPDATE",
                drafts=platform_drafts
            ), curation

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
        lead_link = curation.top_articles[0].link if curation.top_articles else "https://example.com/mock-lead-link"
        topic = telegram_topic if telegram_topic else "DryRun"
        is_failover = False
        from src.models import PlatformDrafts
        platform_drafts = PlatformDrafts.from_single(summary)
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
                config=types.GenerateContentConfig(
                    system_instruction=CURATOR_SYSTEM_INSTRUCTION,
                    temperature=0.7
                )
            )
            summary = strip_markdown(response.text.strip())
            from src.models import PlatformDrafts
            platform_drafts = PlatformDrafts.from_single(summary)
            lead_link = None
            topic = telegram_topic
        except Exception as e:
            SafeLogger.warn(f"Telegram topic synthesis failed: {e}")
            summary, lead_link, topic, is_failover = await generate_mentor_insight(context)
            from src.models import PlatformDrafts
            platform_drafts = PlatformDrafts.from_single(summary)
    elif news_count > 3 or (telegram_topic and news_count > 0):
        # Curation flow: either normal flow with >3 articles or matched Telegram topic
        is_mentor_time = any(x in curation.session_name for x in ["Afternoon", "Evening", "Night"])
        mode = "Mentor" if is_mentor_time else "Curator"
        try:
            # Convert back to dict for legacy curator logic (minimizing regression)
            news_dicts = [vars(a) for a in curation.top_articles]
            summary_res = await summarize_news(
                news_dicts, context, mode=mode, last_dialect=curation.last_dialect, writing_style=chosen_style
            )
            if len(summary_res) == 6:
                summary, lead_link, topic, is_failover, current_dialect, platform_drafts = summary_res
            else:
                summary, lead_link, topic, is_failover, current_dialect = summary_res
                from src.models import PlatformDrafts
                platform_drafts = PlatformDrafts.from_single(summary)

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
            from src.models import PlatformDrafts
            platform_drafts = PlatformDrafts.from_single(summary)
    else:
        SafeLogger.info(f"Low volume ({news_count}), using Strategist Insight.")
        summary, lead_link, topic, is_failover = await generate_mentor_insight(context)
        from src.models import PlatformDrafts
        platform_drafts = PlatformDrafts.from_single(summary)

    if not summary:
        from src.models import PlatformDrafts
        return SynthesisResult(content="", lead_link=None, topic="General", writing_style=chosen_style, drafts=PlatformDrafts.from_single("")), curation


    return SynthesisResult(
        content=summary,
        lead_link=lead_link,
        topic=topic,
        is_failover=is_failover,
        media=None,
        writing_style=chosen_style,
        drafts=platform_drafts
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
                        lead_title = lead_article.title if lead_article else ""
                        alt_text = await generate_image_alt_text(
                            og_bytes,
                            prompt="",
                            article_title=lead_title,
                            category=category,
                            topic=synthesis.topic
                        )
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
                lead_title = lead_article.title if lead_article else ""
                alt_prompt = visual_prompt if visual_prompt else f"Image representing {synthesis.topic}"
                alt_text = await generate_image_alt_text(
                    gen_bytes,
                    prompt=alt_prompt,
                    article_title=lead_title,
                    category=category,
                    topic=synthesis.topic
                )
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

    ai_status = 'Generated' if source == MediaSource.GENERATED else 'Not needed' if source == MediaSource.OPENGRAPH else 'Failed' if settings.enable_image_gen else 'Disabled'
    log_lines.append(f"AI: {ai_status}")

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

async def broadcast_stage(
    client: httpx.AsyncClient,
    synthesis: SynthesisResult,
    max_parts: Optional[int] = None,
    decision: Optional[Any] = None
) -> Tuple[List[BroadcastResult], Any]:
    """Stage 3: Multi-platform delivery."""
    if settings.is_dry_run:
        SafeLogger.info("DRY RUN: Skip broadcasting to social networks.")
        SafeLogger.info(f"DRY RUN Synthesis:\n{synthesis.content}")
        if synthesis.media and synthesis.media.alt_text:
            SafeLogger.info(f"DRY RUN Image Alt Text: {synthesis.media.alt_text}")
        return [
            BroadcastResult(platform="Bluesky", success=True, post_id="dry_run_bsky_id", post_url="https://bsky.app/profile/dryrun/post/dryrun"),
            BroadcastResult(platform="Mastodon", success=True, post_id="dry_run_masto_id", post_url="https://mastodon.social/@blubot/dryrun"),
            BroadcastResult(platform="Threads", success=True, post_id="dry_run_threads_id", post_url="https://threads.net/@blubot/post/dryrun")
        ], None

    # Bluesky Session Hardening
    bsky_client = AsyncClient(request=AsyncRequest(timeout=30.0))
    if settings.bsky_handle and settings.bsky_password:
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
    else:
        bsky_client = None

    tasks = []
    bsky_content = synthesis.get_platform_content("bluesky")
    mastodon_content = synthesis.get_platform_content("mastodon")
    threads_content = synthesis.get_platform_content("threads")

    # Extract target reply targets from decision if in update mode
    target_roots = getattr(decision, "target_platform_roots", {}) if decision and getattr(decision, "mode", None) == "update" else {}
    bsky_reply_target = target_roots.get("bluesky")
    mastodon_reply_id = target_roots.get("mastodon", {}).get("id") if isinstance(target_roots.get("mastodon"), dict) else target_roots.get("mastodon")
    threads_reply_id = target_roots.get("threads", {}).get("id") if isinstance(target_roots.get("threads"), dict) else target_roots.get("threads")

    if bsky_client and settings.bsky_handle:
        tasks.append(("Bluesky", post_to_bluesky(
            bsky_client, client, bsky_content, synthesis.lead_link, synthesis.media,
            max_parts=max_parts, reply_to=bsky_reply_target
        )))
    if settings.mastodon_token and settings.mastodon_base_url:
        tasks.append(("Mastodon", post_to_mastodon(
            mastodon_content, synthesis.media,
            max_parts=max_parts, reply_to_id=mastodon_reply_id
        )))
    if settings.threads_token and settings.threads_user_id:
        tasks.append(("Threads", post_to_threads(
            client, threads_content, synthesis.media,
            max_parts=max_parts, reply_to_id=threads_reply_id
        )))

    if not tasks:
        SafeLogger.error("No configured broadcast targets available!")
        return [BroadcastResult(platform="None", success=False, error="No configured targets")], bsky_client

    results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    report = []
    for (name, _), res in zip(tasks, results):
        if isinstance(res, Exception):
            report.append(BroadcastResult(platform=name, success=False, error=str(res)))
        elif not res:
            report.append(BroadcastResult(platform=name, success=False, error="Platform skipped or failed internally"))
        else:
            post_url = None
            if name in {"Mastodon", "Threads"} and isinstance(res, tuple):
                post_id, post_url = res
            else:
                post_id = getattr(res, "uri", res)
            post_id_str = str(post_id) if post_id else None
            if post_id_str:
                if name == "Bluesky" and post_id_str.startswith("at://"):
                    parts = post_id_str[5:].split("/")
                    if len(parts) >= 3 and parts[1] == "app.bsky.feed.post":
                        post_url = f"https://bsky.app/profile/{parts[0]}/post/{parts[2]}"

            report.append(BroadcastResult(
                platform=name, success=True,
                post_id=post_id_str,
                post_cid=getattr(res, "cid", None),
                post_url=post_url,
            ))
    return report, bsky_client

async def reserve_pending_stage(
    curation: CurationResult,
    synthesis: SynthesisResult,
    decision: Optional[Any] = None
) -> Tuple[Optional[dict], Article]:
    """Resolves lead article and writes pending reservation (original or update) to state."""
    import hashlib
    canonical_lead = None
    matched_article = None

    if synthesis.lead_link:
        canonical_lead = normalize_url(synthesis.lead_link)
        for art in curation.top_articles:
            if art.link and normalize_url(art.link) == canonical_lead:
                matched_article = art
                break

        if not matched_article:
            SafeLogger.error(f"Lead link '{synthesis.lead_link}' could not be unambiguously resolved to a candidate article in curation. Aborting broadcast.")
            sys.exit(1)
    else:
        # Linkless fallback path (e.g. mentor insight or topic fallback synthesis)
        content_hash = hashlib.sha256((synthesis.content or "").encode('utf-8')).hexdigest()[:16]
        canonical_lead = f"generated:{content_hash}"
        matched_article = Article(
            title=getattr(synthesis, 'topic', 'Generated Insight'),
            link=canonical_lead,
            summary=(synthesis.content or "")[:100],
            published=datetime.now(timezone.utc).isoformat(),
            source="Synthesis Engine"
        )

    state = await asyncio.to_thread(load_seen_articles)
    from src.utils import compute_story_fingerprint

    is_update_mode = bool(decision and getattr(decision, "mode", None) == "update")
    parent_fp = getattr(decision, "parent_fingerprint", None) if is_update_mode else None
    update_num = getattr(decision, "update_number", 0) if is_update_mode else 0

    idempotency_key = f"update:{parent_fp}:{canonical_lead}" if is_update_mode else f"original:{compute_story_fingerprint(matched_article.title)}:{canonical_lead}"

    # Idempotency check: if reservation or published post with this key exists, abort or skip duplicate
    for ps in state.get("pending_stories", []):
        if ps.get("idempotency_key") == idempotency_key or (is_update_mode and ps.get("url") == canonical_lead and ps.get("parent_story_fingerprint") == parent_fp):
            SafeLogger.warn(f"Duplicate reservation detected ({idempotency_key}). Skipping duplicate broadcast.")
            return None, matched_article

    for pub in state.get("published_posts", []):
        if pub.get("idempotency_key") == idempotency_key or (is_update_mode and pub.get("url") == canonical_lead and pub.get("parent_story_fingerprint") == parent_fp):
            SafeLogger.warn(f"Duplicate published story detected ({idempotency_key}). Skipping duplicate broadcast.")
            return None, matched_article

    pending_entry = {
        "url": canonical_lead,
        "title": matched_article.title,
        "fingerprint": compute_story_fingerprint(matched_article.title),
        "stage": "pending",
        "source_published_at": matched_article.published,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entry_kind": "update" if is_update_mode else "original",
        "parent_story_fingerprint": parent_fp,
        "update_number": update_num,
        "idempotency_key": idempotency_key,
        "target_platform_roots": getattr(decision, "target_platform_roots", {}) if is_update_mode else {},
        "editorial_decision": {
            "mode": getattr(decision, "mode", "original"),
            "confidence": getattr(decision, "confidence", "NO_MATCH"),
            "explanation": getattr(decision, "explanation", "")
        } if decision else None,
        "reservation_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state.setdefault("pending_stories", []).append(pending_entry)

    res_ok, updated_state = await asyncio.to_thread(
        save_seen_articles,
        state,
        is_reservation=True,
        reservation_key=idempotency_key,
    )
    if not res_ok:
        if updated_state.get("_reservation_conflict"):
            SafeLogger.warn(f"Duplicate reservation won concurrent claim ({idempotency_key}). Skipping duplicate broadcast.")
            return None, matched_article
        SafeLogger.error("CRITICAL: Authoritative pending reservation failed on configured state storage. Aborting publication.")
        sys.exit(1)

    return updated_state, matched_article


async def settle_persistence_stage(
    state: dict,
    curation: CurationResult,
    synthesis: SynthesisResult,
    matched_article: Article,
    results: List[BroadcastResult],
    decision: Optional[Any] = None
) -> dict:
    """Settles pending reservation to published (if any broadcast target succeeded) or retains as uncertain (if all failed)."""
    canonical_lead = normalize_url(synthesis.lead_link) if synthesis.lead_link else matched_article.link
    any_success = any(res.success for res in results)
    is_update_mode = bool(decision and getattr(decision, "mode", None) == "update")
    parent_fp = getattr(decision, "parent_fingerprint", None) if is_update_mode else None
    update_num = getattr(decision, "update_number", 0) if is_update_mode else 0

    reserved_entry = next(
        (
            pending for pending in state.get("pending_stories", [])
            if pending.get("url") == canonical_lead
            and (not is_update_mode or pending.get("parent_story_fingerprint") == parent_fp)
        ),
        None,
    )
    if reserved_entry:
        update_num = reserved_entry.get("update_number", update_num)

    if any_success:
        # Success policy: remove pending reservation when successful
        state["pending_stories"] = [
            ps for ps in state.get("pending_stories", [])
            if not (ps.get("url") == canonical_lead and (not is_update_mode or ps.get("parent_story_fingerprint") == parent_fp))
        ]

        from src.utils import compute_story_fingerprint
        fp = compute_story_fingerprint(matched_article.title)
        pub_entry = {
            "url": canonical_lead,
            "title": matched_article.title,
            "fingerprint": fp,
            "supporting_links": [normalize_url(sl) for sl in (matched_article.supporting_links or []) if sl],
            "stage": "published",
            "source_published_at": matched_article.published,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "entry_kind": "update" if is_update_mode else "original",
            "parent_story_fingerprint": parent_fp,
            "update_number": update_num,
        }
        state.setdefault("recent_stories", []).append(pub_entry)

        posts = {}
        thread_roots = {}
        for res in results:
            if not (res.success and res.post_id):
                continue
            plat_key = res.platform.lower()
            if res.platform == "Bluesky":
                posts["bluesky"] = {"uri": res.post_id, "cid": res.post_cid, "receipt_uri": res.receipt_id}
                thread_roots["bluesky"] = {"uri": res.post_id, "cid": res.post_cid}
            elif res.platform == "Mastodon":
                posts["mastodon"] = {"id": res.post_id, "url": res.post_url}
                thread_roots["mastodon"] = {"id": res.post_id, "url": res.post_url}
            elif res.platform == "Threads":
                posts["threads"] = {"id": res.post_id, "url": res.post_url}
                thread_roots["threads"] = {"id": res.post_id, "url": res.post_url}

        from src.config import FEED_CATEGORY_MAP
        published_category = FEED_CATEGORY_MAP.get(matched_article.source_id, "unknown")

        from src.utils import append_published_post
        append_published_post(
            state,
            url=canonical_lead,
            title=matched_article.title,
            topic=synthesis.topic or "General",
            supporting_links=pub_entry["supporting_links"],
            posts=posts,
            published_at=pub_entry["published_at"],
            source=matched_article.source,
            source_id=matched_article.source_id,
            category=published_category,
            supporting_sources=matched_article.supporting_sources,
            entry_kind="update" if is_update_mode else "original",
            story_fingerprint=fp,
            parent_story_fingerprint=parent_fp,
            update_number=update_num,
            source_url=canonical_lead,
            thread_roots=thread_roots,
            summary=matched_article.summary,
        )

        state.setdefault("links", [])
        if canonical_lead not in state["links"]:
            state["links"].append(canonical_lead)
        for sl in pub_entry["supporting_links"]:
            if sl not in state["links"]:
                state["links"].append(sl)

        if synthesis.topic != "General" and synthesis.topic not in state.get("recent_topics", []):
            state.setdefault("recent_topics", []).append(synthesis.topic)

        state.setdefault("recent_categories", []).append(published_category)
        state["recent_categories"] = state["recent_categories"][-10:]

        if synthesis.writing_style:
            state.setdefault("recent_styles", []).append(synthesis.writing_style)
            state["recent_styles"] = state["recent_styles"][-10:]

        state["total_posts_curated"] = state.get("total_posts_curated", 0) + 1
        state["last_dialect"] = curation.last_dialect
        state["links"] = state["links"][-500:]
        state.setdefault("recent_topics", [])
        state["recent_topics"] = state["recent_topics"][-20:]

        settle_ok, final_state = await asyncio.to_thread(
            save_seen_articles,
            state,
            is_reservation=False,
            settlement_delta={
                "posts_curated": 1,
                "category": published_category,
                "style": synthesis.writing_style,
                "topic": synthesis.topic if synthesis.topic != "General" else None,
                "last_dialect": curation.last_dialect,
            },
        )
        if not settle_ok:
            SafeLogger.error("Post-broadcast settlement failed to save on configured state storage.")
            sys.exit(1)
        return final_state
    else:
        # Ambiguous Failure path: Retain reservation with stage='uncertain'
        for ps in state.get("pending_stories", []):
            if ps.get("url") == canonical_lead:
                ps["stage"] = "uncertain"
                ps["updated_at"] = datetime.now(timezone.utc).isoformat()

        settle_ok, final_state = await asyncio.to_thread(save_seen_articles, state, is_reservation=False)
        SafeLogger.error("All broadcast targets failed or encountered errors. Pending reservation transitioned to uncertain state.")
        sys.exit(1)

def _source_receipt_pairs(article: Article) -> List[Tuple[str, str]]:
    """Keep source names aligned with their normalized corroborating links."""
    lead_link = normalize_url(article.link)
    seen = set()
    pairs = []
    for source, link in zip(article.supporting_sources or [], article.supporting_links or []):
        if not isinstance(source, str) or not source.strip() or not isinstance(link, str):
            continue
        canonical_link = normalize_url(link)
        if (
            not canonical_link.startswith(("http://", "https://"))
            or canonical_link == lead_link
            or canonical_link in seen
        ):
            continue
        seen.add(canonical_link)
        pairs.append((source.strip(), canonical_link))
        if len(pairs) == 2:
            break
    return pairs

def _attach_receipt_to_ledger(state: dict, root_uri: str, receipt_uri: str) -> bool:
    """Attach a receipt to the matching settled Bluesky root entry."""
    for entry in reversed(state.get("published_posts", [])):
        posts = entry.get("posts") if isinstance(entry, dict) else None
        bluesky = posts.get("bluesky") if isinstance(posts, dict) else None
        if isinstance(bluesky, dict) and bluesky.get("uri") == root_uri:
            bluesky["receipt_uri"] = receipt_uri
            return True
    return False

async def source_receipt_stage(
    state: dict,
    matched_article: Article,
    results: List[BroadcastResult],
    bsky_client: Any,
) -> Tuple[dict, List[BroadcastResult]]:
    """Post and persist an optional Bluesky source receipt after root settlement."""
    if (
        not settings.enable_source_receipts_bsky
        or settings.is_dry_run
        or not matched_article.consensus_synergy
        or not bsky_client
    ):
        return state, results

    bsky_result = next((result for result in results if result.platform == "Bluesky"), None)
    if not bsky_result or not bsky_result.success or not bsky_result.post_id or not bsky_result.post_cid:
        return state, results

    pairs = _source_receipt_pairs(matched_article)
    if not pairs:
        return state, results

    receipt_id = await post_bluesky_receipt(
        bsky_client, bsky_result.post_id, bsky_result.post_cid, pairs
    )
    if not receipt_id:
        return state, results

    from dataclasses import replace
    results = [
        replace(result, receipt_id=receipt_id) if result.platform == "Bluesky" else result
        for result in results
    ]
    if not _attach_receipt_to_ledger(state, bsky_result.post_id, receipt_id):
        SafeLogger.warn("Bluesky source receipt posted but no matching ledger entry was found.")
        return state, results

    try:
        saved, updated_state = await asyncio.to_thread(save_seen_articles, state, is_reservation=False)
        if not saved:
            SafeLogger.warn("Bluesky source receipt state could not be fully synchronized.")
        return updated_state, results
    except Exception as exc:
        SafeLogger.warn(f"Bluesky source receipt state save failed: {type(exc).__name__}")
        return state, results

def get_current_iso_week(now: Optional[datetime] = None) -> str:
    """Returns the current ISO week formatted as YYYY-Www (e.g. 2026-W42)."""
    current = now or datetime.now(timezone.utc)
    iso_year, iso_week, _ = current.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

def is_roundup_reserved_or_published(state: dict, iso_week: str) -> bool:
    """Decision table check: returns True if roundup for iso_week is pending, uncertain, or published."""
    canonical_key = f"generated:roundup:{iso_week}"
    for ps in state.get("pending_stories", []):
        if ps.get("url") == canonical_key:
            return True
    for entry in state.get("published_posts", []):
        if (
            entry.get("kind") == "roundup"
            and (entry.get("week") == iso_week or entry.get("url") == canonical_key)
        ):
            return True
    return False

def select_eligible_roundup_stories(state: dict, iso_week: str) -> List[dict]:
    """Finds published ledger entries belonging to the current ISO week with kind == 'post' and valid public URLs."""
    eligible = []
    for entry in state.get("published_posts", []):
        if entry.get("kind") == "roundup":
            continue
        raw_url = str(entry.get("url") or "").strip()
        from scripts.build_archive import is_valid_public_http_url
        if not is_valid_public_http_url(raw_url):
            continue

        pub_at = entry.get("published_at")
        if not pub_at:
            continue
        try:
            pub_dt = datetime.fromisoformat(str(pub_at))
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            ey, ew, _ = pub_dt.isocalendar()
            if f"{ey}-W{ew:02d}" == iso_week:
                # Normalize title: collapse newlines/whitespace, strip @ to avoid stray mentions, bound length
                raw_title = str(entry.get("title") or "").replace("\r", " ").replace("\n", " ").replace("@", "")
                clean_title = " ".join(raw_title.split())[:120]
                if clean_title:
                    normalized_entry = dict(entry)
                    normalized_entry["title"] = clean_title
                    normalized_entry["url"] = raw_url
                    eligible.append(normalized_entry)
        except Exception:
            continue
    return eligible

def build_roundup_text(iso_week: str, stories: List[dict]) -> str:
    """Builds deterministic, zero-AI digest text with header and numbered story paragraphs."""
    parts = [f"This week in AI ({iso_week})"]
    for idx, story in enumerate(stories, 1):
        title = story.get("title", "").strip()
        url = story.get("url", "").strip()
        parts.append(f"{idx}. {title}\n{url}")
    return "\n\n".join(parts)

def validate_roundup_urls_preserved(roundup_content: Any, stories: List[dict], max_parts: int) -> bool:
    """Pre-broadcast verification: ensures every story URL survives smart_split across all active platforms."""
    expected_urls = [s.get("url", "").strip() for s in stories if s.get("url")]
    def _safe_int(val, default):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    platform_configs = [
        ("bluesky", _safe_int(getattr(settings, "bluesky_limit", 300), 300) - 10),
        ("mastodon", _safe_int(getattr(settings, "mastodon_limit", 500), 500) - 15),
        ("threads", _safe_int(getattr(settings, "threads_limit", 500), 500) - 10),
    ]

    for platform, limit in platform_configs:
        if hasattr(roundup_content, "get_platform_content"):
            text = roundup_content.get_platform_content(platform)
        elif hasattr(roundup_content, platform):
            text = getattr(roundup_content, platform)
        else:
            text = str(roundup_content)

        # Apply platform-specific cleanups matching broadcasters
        from src.broadcaster import clean_hashtags_if_needed
        if platform == "bluesky":
            text = clean_hashtags_if_needed(text, getattr(settings, "enable_hashtags_bsky", False))
        elif platform == "mastodon":
            text = clean_hashtags_if_needed(text, getattr(settings, "enable_hashtags_mastodon", True))
        elif platform == "threads":
            text = clean_hashtags_if_needed(text, getattr(settings, "enable_hashtags_threads", False))

        chunks = smart_split(text, limit, max_chunks=max_parts)
        combined = " ".join(chunks)
        for expected_url in expected_urls:
            if expected_url not in combined:
                return False
    return True

async def roundup_stage(
    client: httpx.AsyncClient,
    genai_client: Any,
    now: Optional[datetime] = None,
) -> bool:
    """
    Executes the Friday Roundup pipeline.
    Returns True if the roundup was handled (published, skipped per duplicate protection, or aborted on error).
    Returns False ONLY if 0 eligible stories exist, signaling clean fallback to the normal publication pipeline.
    """
    current_time = now or datetime.now(timezone.utc)
    iso_week = get_current_iso_week(current_time)
    SafeLogger.info(f"Roundup Stage: Evaluating Friday roundup for {iso_week}")

    state = await asyncio.to_thread(load_seen_articles)

    # Decision Table 1: Skip run if already reserved (pending/uncertain) or published
    if is_roundup_reserved_or_published(state, iso_week):
        SafeLogger.info(f"Roundup Stage: Roundup for {iso_week} is already reserved or published. Skipping run.")
        return True

    # Decision Table 2: Find eligible stories from this week's ledger
    eligible = select_eligible_roundup_stories(state, iso_week)
    if not eligible:
        SafeLogger.info(f"Roundup Stage: 0 eligible stories found in published ledger for {iso_week}. Falling back to normal pipeline.")
        return False

    SafeLogger.info(f"Roundup Stage: Found {len(eligible)} eligible stories for {iso_week}.")

    # Rank stories by Bluesky live engagement metrics, falling back to recency
    from src.engagement import fetch_bluesky_metrics, bluesky_uri
    metrics = await fetch_bluesky_metrics(client, eligible)

    def story_score(entry: dict) -> Tuple[int, str]:
        uri = bluesky_uri(entry)
        m = metrics.get(uri or "") if uri else None
        if m:
            total_eng = m.get("likes", 0) + m.get("reposts", 0) + m.get("replies", 0) + m.get("quotes", 0)
        else:
            total_eng = -1
        pub_at = str(entry.get("published_at", ""))
        return (total_eng, pub_at)

    sorted_stories = sorted(eligible, key=story_score, reverse=True)
    selected_stories = sorted_stories[:5]

    # Build deterministic roundup text
    roundup_text = build_roundup_text(iso_week, selected_stories)
    num_parts = 1 + len(selected_stories)

    # Pre-broadcast URL preservation validation
    if not validate_roundup_urls_preserved(roundup_text, selected_stories, num_parts):
        SafeLogger.error("Roundup Stage: Pre-broadcast verification failed. Not all story URLs survived thread chunking. Aborting roundup run safely.")
        return True

    from src.models import PlatformDrafts
    drafts = PlatformDrafts.from_single(roundup_text)
    roundup_topic = f"Roundup {iso_week}"

    # Telegram Approval Stage (if enabled and not a dry-run)
    if settings.enable_telegram_approval and not settings.is_dry_run:
        final_drafts, _ = await send_draft_for_approval(
            drafts=drafts,
            media=None,
            client=client,
            genai_client=genai_client,
            topic=roundup_topic,
        )
        if final_drafts is None:
            SafeLogger.info("Telegram: Roundup draft rejected by user. Aborting execution.")
            return True

        if isinstance(final_drafts, str):
            final_drafts = PlatformDrafts.from_single(final_drafts)
        drafts = final_drafts
        roundup_text = drafts.bluesky

        # Re-validate all edited/remixed platform drafts before reservation
        if not validate_roundup_urls_preserved(drafts, selected_stories, num_parts):
            SafeLogger.error("Roundup Stage: Post-approval verification failed on edited drafts. Aborting roundup run safely.")
            return True
    else:
        SafeLogger.info("Telegram: Approval disabled or dry-run bypassed for roundup.")

    synthesis = SynthesisResult(
        content=roundup_text,
        lead_link=None,
        topic=roundup_topic,
        drafts=drafts,
        media=None,
    )

    # Pre-Broadcast Reservation Contract
    canonical_lead = f"generated:roundup:{iso_week}"
    state = await asyncio.to_thread(load_seen_articles)
    if is_roundup_reserved_or_published(state, iso_week):
        SafeLogger.info(f"Roundup Stage: Concurrent reservation detected for {iso_week}. Skipping.")
        return True

    pending_entry = {
        "url": canonical_lead,
        "title": f"This week in AI ({iso_week})",
        "fingerprint": compute_story_fingerprint(f"This week in AI ({iso_week})"),
        "stage": "pending",
        "kind": "roundup",
        "week": iso_week,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    state.setdefault("pending_stories", []).append(pending_entry)
    res_ok, updated_state = await asyncio.to_thread(save_seen_articles, state, is_reservation=True)
    if not res_ok:
        SafeLogger.error("CRITICAL: Roundup pending reservation failed on configured state storage. Aborting.")
        sys.exit(1)

    # Broadcast with exact max_parts
    SafeLogger.info(f"Initiating roundup broadcast for {iso_week} ({num_parts} parts max).")
    results, bsky_client = await broadcast_stage(client, synthesis, max_parts=num_parts)
    for res in results:
        if res.success:
            SafeLogger.info(f"{res.platform} roundup broadcast successful.")
        else:
            SafeLogger.error(f"{res.platform} roundup broadcast failed: {res.error}")

    any_success = any(res.success for res in results)
    state = updated_state
    if any_success:
        # Settle published roundup
        state["pending_stories"] = [ps for ps in state.get("pending_stories", []) if ps.get("url") != canonical_lead]
        posts = {}
        for res in results:
            if not (res.success and res.post_id):
                continue
            if res.platform == "Bluesky":
                posts["bluesky"] = {"uri": res.post_id, "cid": res.post_cid, "receipt_uri": res.receipt_id}
            else:
                posts[res.platform.lower()] = {"id": res.post_id}

        from src.utils import append_published_post
        append_published_post(
            state,
            url=canonical_lead,
            title=f"This week in AI ({iso_week})",
            topic="Roundup",
            supporting_links=[s.get("url") for s in selected_stories if s.get("url")],
            posts=posts,
            kind="roundup",
            week=iso_week,
            published_at=datetime.now(timezone.utc).isoformat(),
            source="BluBot",
            source_id="weekly_roundup",
            category="roundup",
        )
        state.setdefault("links", [])
        if canonical_lead not in state["links"]:
            state["links"].append(canonical_lead)

        settle_ok, final_state = await asyncio.to_thread(save_seen_articles, state, is_reservation=False)
        if not settle_ok:
            SafeLogger.error("Post-broadcast settlement failed to save on configured state storage.")
            sys.exit(1)

        # Telegram post-broadcast notifications
        if settings.telegram_bot_token and settings.telegram_user_id and not settings.is_dry_run:
            try:
                await send_broadcast_platform_messages(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_user_id,
                    results=results,
                    synthesis=synthesis,
                )
            except Exception as e:
                SafeLogger.warn(f"Telegram post-broadcast notifications failed: {e}")

        # Post-persistence status updates
        await update_status_dashboard("Friday Roundup", roundup_topic)
        if not settings.is_dry_run:
            from src.engagement import update_engagement_report
            await update_engagement_report(client, final_state, STATUS_FILE_PATH)
        return True
    else:
        # Ambiguous failure path: mark uncertain
        for ps in state.get("pending_stories", []):
            if ps.get("url") == canonical_lead:
                ps["stage"] = "uncertain"
                ps["updated_at"] = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(save_seen_articles, state, is_reservation=False)
        SafeLogger.error("All roundup broadcast targets failed. Reservation transitioned to uncertain.")
        sys.exit(1)

async def persistence_stage(curation: CurationResult, synthesis: SynthesisResult, client_bsky: Any = None):
    """Legacy compatibility helper delegating to reserve_pending_stage and settle_persistence_stage."""
    from dataclasses import replace
    if not synthesis.lead_link and curation.top_articles:
        synthesis = replace(synthesis, lead_link=curation.top_articles[0].link)
    state, matched = await reserve_pending_stage(curation, synthesis)
    dummy_results = [BroadcastResult(platform="Bluesky", success=True)]
    return await settle_persistence_stage(state, curation, synthesis, matched, dummy_results)

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

            reply_limit = {
                "bluesky": min(settings.bluesky_limit, 280),
                "mastodon": settings.mastodon_limit,
                "threads": settings.threads_limit,
            }.get(mention.platform)
            if reply_limit:
                reply_text = smart_truncate(reply_text, reply_limit)

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
            message = (str(e).splitlines() or ["no message"])[0][:120]
            error = f"{type(e).__name__}: {message}"
            SafeLogger.error(f"Failed to process interaction for @{mention.author}: {error}")
            errors.append(error)

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

        # Friday Evening Roundup Intercept
        is_scheduled = getattr(settings, "is_scheduled_run", False) is True
        force_roundup = getattr(settings, "force_roundup", False) is True
        # P1 fix: Do not consume or discard an explicit topic or curate command on Friday evening
        is_friday_evening_roundup = (
            (now.weekday() == 4 and now.hour >= 18 and is_scheduled and cmd_type != "topic")
            or force_roundup
        )
        if is_friday_evening_roundup:
            roundup_handled = await roundup_stage(client, genai_client, now)
            if roundup_handled:
                return

        t_start = time.monotonic()

        # 1. Curation
        t0 = time.monotonic()
        curation = await curation_stage(client, telegram_topic=telegram_topic)
        SafeLogger.info(f"Curation Stage: Completed in {time.monotonic() - t0:.2f}s ({len(curation.top_articles)} candidates).")

        # 1.5 Continuity Matching & Editorial Decision Orchestration
        from src.models import MatchDecision, EditorialDecision
        from src.curator import match_story_continuity

        decision = EditorialDecision(
            mode="original",
            parent_fingerprint=None,
            update_number=0,
            confidence=MatchDecision.NO_MATCH.value,
            explanation="Default original story"
        )

        lead_art = curation.top_articles[0] if curation.top_articles else None
        if lead_art and not telegram_topic:
            state_data = await asyncio.to_thread(load_seen_articles)
            published_ledger = state_data.get("published_posts", [])
            lead_dict = vars(lead_art)
            dec_type, parent_entry, explanation = match_story_continuity(lead_dict, published_ledger, now_utc=now)

            if dec_type == MatchDecision.CONFIDENT_UPDATE.value and parent_entry and settings.story_update_detection_enabled:
                from src.utils import compute_story_fingerprint
                parent_fp = parent_entry.get("story_fingerprint") or compute_story_fingerprint(parent_entry.get("title", ""))
                # Derive thread roots from parent posts if thread_roots is empty
                p_roots = dict(parent_entry.get("thread_roots") or {})
                if not p_roots and isinstance(parent_entry.get("posts"), dict):
                    posts = parent_entry["posts"]
                    if "bluesky" in posts and isinstance(posts["bluesky"], dict):
                        p_roots["bluesky"] = {"uri": posts["bluesky"].get("uri"), "cid": posts["bluesky"].get("cid")}
                    if "mastodon" in posts and isinstance(posts["mastodon"], dict):
                        p_roots["mastodon"] = {"id": posts["mastodon"].get("id"), "url": posts["mastodon"].get("url")}
                    if "threads" in posts and isinstance(posts["threads"], dict):
                        p_roots["threads"] = {"id": posts["threads"].get("id"), "url": posts["threads"].get("url")}

                prior_updates = [
                    p for p in published_ledger
                    if p.get("entry_kind") == "update" and p.get("parent_story_fingerprint") == parent_fp
                ]
                up_num = len(prior_updates) + 1
                decision = EditorialDecision(
                    mode="update",
                    parent_fingerprint=parent_fp,
                    update_number=up_num,
                    confidence=dec_type,
                    explanation=explanation,
                    target_platform_roots=p_roots,
                    parent_entry=parent_entry
                )
                SafeLogger.info(f"Continuity Matcher: CONFIDENT_UPDATE identified for '{parent_entry.get('title', '')}' (Update #{up_num}). Roots: {list(decision.target_platform_roots.keys())}")
            else:
                SafeLogger.info(f"Continuity Matcher: Evaluated as {dec_type} ({explanation}). Proceeding with normal standalone post.")
                from src.utils import compute_story_fingerprint
                parent_fp_standalone = (parent_entry.get("story_fingerprint") or compute_story_fingerprint(parent_entry.get("title", ""))) if parent_entry else None
                decision = EditorialDecision(
                    mode="original",
                    parent_fingerprint=parent_fp_standalone,
                    update_number=0,
                    confidence=dec_type,
                    explanation=explanation
                )

        if settings.is_dry_run:
            SafeLogger.info(
                f"DRY RUN Continuity Evaluation:\n"
                f"→ candidate: {lead_art.title if lead_art else 'None'}\n"
                f"→ matched original story: {decision.parent_entry.get('title') if decision.parent_entry else 'None'}\n"
                f"→ confidence: {decision.confidence}\n"
                f"→ reason: {decision.explanation}\n"
                f"→ action: {'reply update' if decision.mode == 'update' else 'standalone post'}"
            )

        # 2. Synthesis
        t0 = time.monotonic()
        context = get_temporal_context()
        synthesis, curation = await synthesis_stage(
            client, genai_client, curation,
            telegram_topic=telegram_topic,
            decision=decision
        )
        if not synthesis.content:
            SafeLogger.error("Synthesis produced no content. Aborting.")
            return
        SafeLogger.info(f"Synthesis Stage: Completed in {time.monotonic() - t0:.2f}s.")

        # 2.2 Media Strategy Decision
        t0 = time.monotonic()
        media = await media_strategy_stage(client, genai_client, synthesis, curation)
        from dataclasses import replace
        synthesis = replace(synthesis, media=media)
        SafeLogger.info(f"Media Stage: Completed in {time.monotonic() - t0:.2f}s.")

        # 2.5 Telegram Approval Stage (if enabled and not a dry-run)
        if settings.enable_telegram_approval and not settings.is_dry_run:
            from src.models import PlatformDrafts
            initial_drafts = synthesis.drafts or PlatformDrafts.from_single(synthesis.content)
            final_drafts, final_media = await send_draft_for_approval(
                drafts=initial_drafts,
                media=synthesis.media,
                client=client,
                genai_client=genai_client,
                topic=synthesis.topic,
                decision=decision
            )
            if final_drafts is None:
                SafeLogger.info("Telegram: Draft rejected by user. Aborting execution.")
                return

            if isinstance(final_drafts, str):
                final_drafts = PlatformDrafts.from_single(final_drafts)

            synthesis = replace(
                synthesis,
                content=final_drafts.bluesky,
                drafts=final_drafts,
                media=final_media
            )
        else:
            SafeLogger.info("Telegram: Approval disabled or dry-run bypassed.")

        # 2.8 Pre-Broadcast Lead Resolution & Reservation Contract
        state, matched_article = await reserve_pending_stage(curation, synthesis, decision=decision)
        if state is None:
            SafeLogger.warn("Reservation skipped duplicate candidate; halting broadcast pipeline.")
            return

        # 3. Broadcast
        t0 = time.monotonic()
        SafeLogger.info(f"Initiating elite broadcast for topic: {synthesis.topic} (Mode: {decision.mode})")
        results, bsky_client = await broadcast_stage(client, synthesis, decision=decision)
        for res in results:
            if res.success:
                SafeLogger.info(f"{res.platform} broadcast successful.")
            else:
                SafeLogger.error(f"{res.platform} broadcast failed: {res.error}")
        SafeLogger.info(f"Broadcast Stage: Completed in {time.monotonic() - t0:.2f}s.")

        # 3.5 Immediate Post-Broadcast Settlement
        state = await settle_persistence_stage(state, curation, synthesis, matched_article, results, decision=decision)
        state, results = await source_receipt_stage(state, matched_article, results, bsky_client)
        SafeLogger.info(f"Total Pipeline Duration: {time.monotonic() - t_start:.2f}s.")

        # 3.6 Post-Broadcast Telegram Multi-Platform Notifications
        if settings.telegram_bot_token and settings.telegram_user_id and not settings.is_dry_run:
            try:
                await send_broadcast_platform_messages(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_user_id,
                    results=results,
                    synthesis=synthesis,
                )
            except Exception as e:
                SafeLogger.warn(f"Telegram post-broadcast notifications failed: {e}")

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
        if not settings.is_dry_run:
            from src.engagement import update_engagement_report
            await update_engagement_report(client, state, STATUS_FILE_PATH)
        await update_social_profiles(bsky_client, settings.mastodon_token, active_day, synthesis.topic)

        if settings.enable_interactions and not settings.is_dry_run:
            interaction_res = await interaction_stage(bsky_client, client, context)
            SafeLogger.info(f"Interaction Session Complete: {len(interaction_res.replied_ids)} replies sent.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
