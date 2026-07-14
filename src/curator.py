import asyncio
import os
import httpx
import feedparser
import re
import calendar
import base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from google.genai import types
from google import genai
from src.settings import settings
from src.config import (
    RSS_FEEDS, TIER_1_SOURCES, TIER_2_SOURCES, HIDDEN_GEM_SOURCES, 
    TOPIC_MAP, CURATOR_SYSTEM_INSTRUCTION, MENTOR_SYSTEM_INSTRUCTION,
    INTERACTIVE_REPLY_INSTRUCTION,
    SAGE_DESIGNER_INSTRUCTION, SECONDARY_TOPICS, GEMINI_MODEL_PRIORITY,
    HIGH_SIGNAL_KEYWORDS, MOMENTUM_PRODUCTS,
    BASE_TIER_1, BASE_HIDDEN_GEM, BASE_TIER_2, SIGNAL_BOOST,
    MOMENTUM_BOOST, SYNERGY_BONUS, DIVERSITY_PENALTY, MAX_TOPIC_RECURRENCE,
    FEED_SUMMARY_MAX_CHARS, NVIDIA_MODEL_ID, NVIDIA_INVOKE_URL
)
from src.utils import retry_with_backoff, SafeLogger

MODEL_ATTEMPT_RETRIES = 2

_MARKDOWN_STRIP_RE = re.compile(r'(\*\*|__|\*)')

def calculate_relevance_score(item, pub_date, now_utc, recent_topics=None, recent_categories=None):
    """Calculates a multi-factor breakthrough score for an article using stable IDs."""
    score = 0
    title_text = item['title'].lower()
    content_text = f"{item['title']} {item['summary']}".lower()
    
    # 1. Source Registry base score (ID-based)
    from src.config import FEED_SCORE_MAP, FEED_CATEGORY_MAP, CATEGORY_RECURRENCE_PENALTY_STEP
    source_id = item.get("source_id", "unknown")
    source_score = FEED_SCORE_MAP.get(source_id, 0)
    score += source_score
    
    # 2. High-Signal Keyword Boosting
    signal_score = 0
    for kw in HIGH_SIGNAL_KEYWORDS:
        if kw in content_text:
            signal_score += SIGNAL_BOOST
            break
    score += signal_score
    
    # 3. Momentum Product Boosting
    momentum_score = 0
    for product in MOMENTUM_PRODUCTS:
        if product in title_text:
            momentum_score += MOMENTUM_BOOST
            break 
    score += momentum_score
    
    # 4. Topic Diversity Penalty
    topic_penalty = 0
    if recent_topics:
        item_topic = "General"
        for topic, keywords in TOPIC_MAP.items():
            if any(kw.lower() in content_text for kw in keywords):
                item_topic = topic
                break
        if item_topic in recent_topics:
            topic_penalty = 12
            score -= topic_penalty
            
    # 5. Progressive Recency-weighted Category Recurrence Penalty
    category_penalty = 0
    if recent_categories:
        item_category = FEED_CATEGORY_MAP.get(source_id, "unknown")
        total_weight = 0.0
        for idx, cat in enumerate(reversed(recent_categories)):
            if cat == item_category:
                # Recency-weighted penalty: idx=0 (immediate previous) -> 1.0, idx=1 -> 0.5, etc.
                total_weight += 1.0 / (idx + 1)
        if total_weight > 0:
            category_penalty = round(total_weight * CATEGORY_RECURRENCE_PENALTY_STEP)
            score -= category_penalty

    # 6. Time Decay
    age_hours = (now_utc - pub_date).total_seconds() / 3600
    decay = age_hours * 0.5
    score -= decay
    
    item['_score_debug'] = {
        "source": source_score,
        "signal": signal_score,
        "momentum": momentum_score,
        "penalty": topic_penalty,
        "category_penalty": category_penalty,
        "decay": round(decay, 1)
    }
    return score

@retry_with_backoff
async def fetch_single_feed(client, url, start_time, now_utc, seen_links, recent_topics, recent_categories=None):
    """Fetches and parses a single RSS feed with Bozo resilience."""
    try:
        from src.config import URL_TO_ID
        source_id = URL_TO_ID.get(url, "unknown")
        
        response = await client.get(url, timeout=10)
        feed = await asyncio.to_thread(feedparser.parse, response.content)
        items = []
        for entry in feed.entries:
            link = getattr(entry, 'link', None)
            if not link or link in seen_links:
                continue
                
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc)
            else:
                pub_date = now_utc
            
            clean_summary = BeautifulSoup(getattr(entry, 'summary', getattr(entry, 'description', "")), "html.parser").get_text()
            item = {
                "title": getattr(entry, 'title', 'Untitled'),
                "summary": clean_summary[:FEED_SUMMARY_MAX_CHARS],
                "link": link,
                "published": pub_date.isoformat(),
                "source": getattr(feed.feed, 'title', url),
                "source_url": url,
                "source_id": source_id
            }
            item["score"] = calculate_relevance_score(item, pub_date, now_utc, recent_topics, recent_categories)
            items.append(item)
        return items
    except Exception: return []

async def fetch_news(client, seen_links=None, recent_topics=None, feed_list=None, limit=8, recent_categories=None):
    """Orchestrates parallel fetching with Consensus Synergy and Greedy Diversity."""
    now_utc = datetime.now(timezone.utc)
    source_list = feed_list if feed_list is not None else RSS_FEEDS
    tasks = [fetch_single_feed(client, url, now_utc - timedelta(days=2), now_utc, seen_links or [], recent_topics, recent_categories) for url in source_list]
    results = await asyncio.gather(*tasks)
    
    all_raw_entries = [e for sublist in results for e in sublist]
    
    unique_by_link = {}
    for e in all_raw_entries:
        if e['link'] not in unique_by_link: 
            unique_by_link[e['link']] = e
        else:
            unique_by_link[e['link']]['score'] += SYNERGY_BONUS
            unique_by_link[e['link']]['consensus_synergy'] = True
            
    entries = list(unique_by_link.values())
    entries.sort(key=lambda x: x["score"], reverse=True)

    # Enforce policy: The lead article (index 0) cannot be from a "critical" category
    # unless all available entries are critical.
    from src.config import FEED_CATEGORY_MAP
    if entries:
        first_category = FEED_CATEGORY_MAP.get(entries[0].get("source_id"), "unknown")
        if first_category == "critical":
            non_critical_idx = -1
            for idx, entry in enumerate(entries):
                entry_cat = FEED_CATEGORY_MAP.get(entry.get("source_id"), "unknown")
                if entry_cat != "critical":
                    non_critical_idx = idx
                    break
            if non_critical_idx != -1:
                # Swap the non-critical entry to index 0
                non_critical_entry = entries.pop(non_critical_idx)
                entries.insert(0, non_critical_entry)

    if limit is None:
        return entries
    return entries[:limit]

def strip_markdown(text):
    if not text: return text
    return _MARKDOWN_STRIP_RE.sub('', text).strip()

def supports_thinking(model_name: str) -> bool:
    """
    Determines if a model supports the thinking_budget parameter.
    Currently supported by: gemini-2.0 and gemini-2.5 pro/flash/flash-lite.
    """
    if not model_name:
        return False
    model_lower = model_name.lower()
    if "gemini-2.0" not in model_lower and "gemini-2.5" not in model_lower:
        return False
    if "gemini-2.0" in model_lower or "gemini-2.5" in model_lower:
        return True
    return False

async def prune_gemini_model_priority_async(genai_client):
    """Asynchronously lists available models and prunes the GEMINI_MODEL_PRIORITY in-place."""
    if settings.is_dry_run or os.getenv("CI", "false").lower() == "true":
        return
    try:
        SafeLogger.info("Gemini Model Discovery: Querying available models from API...")
        available_models = []
        async for m in await genai_client.aio.models.list():
            available_models.append(m.name)
            
        pruned = []
        for model_id in GEMINI_MODEL_PRIORITY:
            norm_id = model_id.lower()
            if any(norm_id in m.lower() or m.lower() in norm_id for m in available_models):
                pruned.append(model_id)
                
        if pruned:
            SafeLogger.info(f"Gemini Model Discovery: Discovered active models: {pruned}")
            GEMINI_MODEL_PRIORITY.clear()
            GEMINI_MODEL_PRIORITY.extend(pruned)
        else:
            SafeLogger.warn("Gemini Model Discovery: None of the prioritized models were returned by the API. Keeping defaults.")
    except Exception as e:
        SafeLogger.warn(f"Gemini Model Discovery: API call failed ({e}). Falling back to configured defaults.")

async def summarize_news(news_items, context, mode="Curator", last_dialect=None, writing_style=None):
    """Synthesizes news with full Failover Loop and randomized Dialect adaptation."""
    if not news_items: return None, None, "General", False, None
    
    if settings.is_dry_run:
        SafeLogger.info("Dry run: Bypassing Gemini synthesis call.")
        return "Mock Dry-Run Post Summary: BluBot is operating correctly in dry-run mode. #AI #News", news_items[0]['link'], "Dry Run Curation", False, "ANALYTICAL"

    # Professional Architecture: Use settings singleton
    client = genai.Client(api_key=settings.gemini_key)
    
    from .config import CURATOR_SYSTEM_INSTRUCTION, PERSONA_DIALECTS
    import random
    
    # Select Dialect (ensure variety)
    available_dialects = list(PERSONA_DIALECTS.keys())
    if last_dialect in available_dialects and len(available_dialects) > 1:
        available_dialects.remove(last_dialect)
    
    current_dialect = random.choice(available_dialects)
    dialect_instruction = PERSONA_DIALECTS[current_dialect]
    
    news_text = "\n".join([f"- {i+1}. {item['title']} ({item['source']})" for i, item in enumerate(news_items)])
    
    # Combine instructions
    base_instruction = MENTOR_SYSTEM_INSTRUCTION if mode == "Mentor" else CURATOR_SYSTEM_INSTRUCTION
    combined_instruction = f"{base_instruction}\n\nSTYLE OVERRIDE: {dialect_instruction}"
    
    if writing_style:
        from .config import WRITING_STYLES
        style_instruction = WRITING_STYLES.get(writing_style)
        if style_instruction:
            combined_instruction += f"\n\nWRITING STRUCTURE INSTRUCTION:\n{style_instruction}"
    
    # Check for Consensus Curation (allows threads opt-in)
    has_consensus = any(item.get('consensus_synergy', False) for item in news_items)
    if has_consensus:
        combined_instruction += "\n\nCONSENSUS EVENT INSTRUCTION: Multiple independent feeds have reported the same major breakthrough. You may expand the post up to 500 characters only when the existing platform-specific limits and splitter can safely handle it. Do not pad. Do not write a long summary. State one clear thesis, explain why the consensus matters, and keep the tone human, concise, and business-relevant."
    
    # Friday Morning Curation focus overlay
    is_friday_morning = context.get('day') == 'Friday' and 'Morning' in context.get('session', '')
    if is_friday_morning:
        combined_instruction += "\n\nRELEASE ROUNDUP INSTRUCTION: Focus exclusively on summarizing the latest market launches, product updates, and developer releases from the past week (Weekly Release Roundup format). Highlight the most impactful commercial developer announcements."

    user_prompt = f"Day: {context['day']}, Session: {context['session']}, Mode: {mode}\nNews Data:\n{news_text}"
    
    for idx, model_id in enumerate(GEMINI_MODEL_PRIORITY):
        for attempt in range(1, MODEL_ATTEMPT_RETRIES + 1):
            try:
                SafeLogger.info(f"Synthesizing via {model_id} (Attempt {attempt})...")
                
                # Dynamic GenerateContentConfig args
                config_args = {
                    "temperature": 0.7
                }
                
                # Check for system_instruction support
                if "gemma" not in model_id.lower():
                    config_args["system_instruction"] = combined_instruction
                
                # Apply thinking config if supported
                if supports_thinking(model_id):
                    budget = settings.thinking_budget if settings.thinking_budget is not None else 1024
                    config_args["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)
                
                contents = f"{combined_instruction}\n\nUSER INPUT:\n{user_prompt}" if "gemma" in model_id.lower() else user_prompt
                
                response = await client.aio.models.generate_content(
                    model=model_id, contents=contents,
                    config=types.GenerateContentConfig(**config_args)
                )
                
                raw_text = response.text.strip()
                topic = "General"
                summary = raw_text
                
                if "TOPIC:" in raw_text and "BODY:" in raw_text:
                    parts = raw_text.split("BODY:", 1)
                    topic = parts[0].replace("TOPIC:", "").strip()
                    summary = parts[1].strip()
                
                if len(summary) > 60:
                    return strip_markdown(summary), news_items[0]['link'], topic, (idx > 0), current_dialect
                    
            except Exception as e:
                SafeLogger.warn(f"Model {model_id} attempt {attempt} failed: {e}")
                
                # Infrastructure Resilience: Add delay for 503 errors to allow service to recover
                if "503" in str(e) or "UNAVAILABLE" in str(e).upper():
                    SafeLogger.info(f"Service spike detected. Cooling down for 2s...")
                    await asyncio.sleep(2)
                    
                if attempt == MODEL_ATTEMPT_RETRIES and idx == len(GEMINI_MODEL_PRIORITY) - 1:
                    raise e
    return None, None, "General", False, None

async def generate_mentor_insight(context):
    if settings.is_dry_run:
        SafeLogger.info("Dry run: Bypassing Gemini mentor insight call.")
        return "Mock Dry-Run Mentor Insight: Focus on strategic scaling in dry-run mode. #Strategy", None, "Strategy", False

    key = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=key)
    topic = SECONDARY_TOPICS[0]
    
    for model_id in GEMINI_MODEL_PRIORITY:
        try:
            SafeLogger.info(f"Generating Mentor Insight via {model_id}...")
            
            config_args = {
                "temperature": 0.8
            }
            
            # Check for system_instruction support
            if "gemma" not in model_id.lower():
                config_args["system_instruction"] = MENTOR_SYSTEM_INSTRUCTION
            
            # Apply thinking config if supported
            if supports_thinking(model_id):
                budget = settings.thinking_budget if settings.thinking_budget is not None else 1024
                config_args["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)
                
            contents = f"{MENTOR_SYSTEM_INSTRUCTION}\n\nTopic: {topic}" if "gemma" in model_id.lower() else f"Topic: {topic}"
            
            response = await client.aio.models.generate_content(
                model=model_id, 
                contents=contents,
                config=types.GenerateContentConfig(**config_args)
            )
            summary = response.text.strip()
            if "BODY:" in summary:
                summary = summary.split("BODY:", 1)[1].strip()

            return strip_markdown(summary), None, "Strategy", (model_id != GEMINI_MODEL_PRIORITY[0])
        except Exception as e:
            SafeLogger.warn(f"Mentor Fallback failed on {model_id}: {e}")
    return None, None, "Strategy", False

def get_temporal_context():
    """Enhanced Temporal Awareness for v3.7.0 (High Resolution + Manual Intercept)."""
    from src.settings import settings
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    hour = now.hour
    
    # Resolve Session name
    if 0 <= hour < 6:
        session = "Night Reflection"
    elif 6 <= hour < 11:
        session = "Morning Intelligence"
    elif 11 <= hour < 15:
        session = "Midday Briefing"
    elif 15 <= hour < 19:
        session = "Afternoon Deep Dive"
    else:
        session = "Evening Synthesis"
        
    # Manual Intercept Decoration
    if settings.is_manual_run:
        session += " (Intercept)"
        
    return {
        "day": now.strftime("%A"), 
        "session": session,
        "is_intercept": settings.is_manual_run
    }

def get_category_prompt_keywords(category: str, topic: str, summary: str) -> str:
    # Check for specific subjects in text first to be precise
    text_lower = f"{topic} {summary}".lower()
    if any(k in text_lower for k in ("security", "encryption", "identity", "secure", "auth")):
        return "Theme: security, identity, encryption, secure agents. Avoid generic AI robot imagery."
    if any(k in text_lower for k in ("agent", "orchestration", "collaboration", "autonomous workflow")):
        return "Theme: agents, orchestration, collaboration, autonomous workflows. Avoid generic AI robot imagery."
    
    # Otherwise fall back to feed category
    cat_lower = category.lower()
    if cat_lower in ("research_lab", "academic"):
        return "Theme: Research - neural networks, transformers, inference. Avoid generic AI robot imagery."
    elif cat_lower in ("enterprise", "business"):
        return "Theme: Enterprise - workflows, automation, business systems. Avoid generic AI robot imagery."
    elif cat_lower in ("infrastructure",):
        return "Theme: Infrastructure - chips, GPUs, networking, datacenters. Avoid generic AI robot imagery."
    
    # Generic fallback
    return "Theme: modern technology illustration, enterprise AI. Avoid generic AI robot imagery."

async def generate_visual_prompt(client, summary, topic, category="unknown"):
    theme_guide = get_category_prompt_keywords(category, topic, summary)
    prompt_content = f"Topic: {topic}\nSummary: {summary}\n{theme_guide}"
    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL_PRIORITY[0],
            contents=prompt_content,
            config=types.GenerateContentConfig(system_instruction=SAGE_DESIGNER_INSTRUCTION, temperature=0.8)
        )
        return response.text.strip()
    except Exception:
        return f"Minimalist tech illustration of {topic}"

def validate_opengraph_image(image_bytes: bytes, image_url: str) -> Any:
    """Validates the OpenGraph image and returns structured ImageValidationResult."""
    from src.models import ImageValidationResult
    from PIL import Image
    import io
    from src.utils import get_image_mime, SafeLogger
    
    mime_type = get_image_mime(image_bytes)
    if not mime_type:
        return ImageValidationResult(valid=False, reason="unsupported_mime", final_url=image_url)
        
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
    except Exception as e:
        return ImageValidationResult(valid=False, reason=f"decode_failed: {e}", mime_type=mime_type, final_url=image_url)
        
    byte_size = len(image_bytes)
    if byte_size > 10 * 1024 * 1024:
        return ImageValidationResult(valid=False, reason="file_too_large", mime_type=mime_type, width=width, height=height, final_url=image_url)
        
    if width < 200 or height < 200:
        return ImageValidationResult(valid=False, reason="dimensions_too_small", mime_type=mime_type, width=width, height=height, final_url=image_url)
        
    aspect_ratio = width / height
    if aspect_ratio < 0.4 or aspect_ratio > 2.5:
        return ImageValidationResult(valid=False, reason="extreme_aspect_ratio", mime_type=mime_type, width=width, height=height, final_url=image_url)
        
    from src.config import GENERIC_IMAGE_PATTERNS
    is_generic = any(p in image_url.lower() for p in GENERIC_IMAGE_PATTERNS)
    if is_generic:
        return ImageValidationResult(valid=False, reason="placeholder_pattern", mime_type=mime_type, width=width, height=height, final_url=image_url)
        
    try:
        colors = img.getcolors(maxcolors=2)
        if colors is not None and len(colors) == 1:
            SafeLogger.warn("OpenGraph validation soft warning: low_entropy image (solid color)")
    except Exception:
        pass
        
    return ImageValidationResult(valid=True, mime_type=mime_type, width=width, height=height, final_url=image_url)

async def generate_image_alt_text(image_bytes: bytes, prompt: str) -> str:
    """Generates screen-reader-friendly alt text for the generated image using Gemini Vision."""
    try:
        # Use settings singleton for key
        client = genai.Client(api_key=settings.gemini_key)
        # Use a model from priority list that supports multimodal inputs, falling back to gemini-2.5-flash-lite
        model_to_use = GEMINI_MODEL_PRIORITY[0] if "gemma" not in GEMINI_MODEL_PRIORITY[0].lower() else "models/gemini-2.5-flash-lite"
        
        response = await client.aio.models.generate_content(
            model=model_to_use,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg",
                ),
                f"Describe this tech illustration in one concise sentence (maximum 100 characters) for use as screen-reader alt text. The prompt used to generate it was: '{prompt}'. Do not include metadata, preambles, or hashtags."
            ]
        )
        return response.text.strip().replace('"', '').replace('\n', ' ')
    except Exception as e:
        SafeLogger.warn(f"Failed to generate alt text via Gemini Vision: {e}. Falling back to default.")
        return f"Tech illustration of: {prompt}"

@retry_with_backoff
async def generate_nvidia_image(client, prompt):
    """Calls NVIDIA NIM for SD3-Medium image generation with robust response parsing."""
    nv_key = settings.nvidia_key
    if not nv_key:
        return None
    
    headers = {
        "Authorization": f"Bearer {nv_key}",
        "Accept": "application/json"
    }
    payload = {
        "prompt": prompt,
        "aspect_ratio": "1:1",
        "mode": "text-to-image",
        "model": "sd3"
    }
    
    try:
        response = None
        result = None
        try:
            response = await client.post(NVIDIA_INVOKE_URL, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            SafeLogger.warn(f"NVIDIA NIM primary endpoint failed ({e}). Attempting OpenAI-compatible endpoint fallback...")
            fallback_url = "https://ai.api.nvidia.com/v1/images/generations"
            fallback_payload = {
                "prompt": prompt,
                "model": "black-forest-labs/flux.2-klein-4b",
                "response_format": "b64_json"
            }
            response = await client.post(fallback_url, headers=headers, json=fallback_payload, timeout=45)
            response.raise_for_status()
            result = response.json()
        
        # Expert Review Fix: Robust multi-format base64 parsing (artifacts vs direct image field)
        image_b64 = None
        if "image" in result:
            image_b64 = result["image"]
        elif "artifacts" in result and len(result["artifacts"]) > 0:
            image_b64 = result["artifacts"][0].get("base64")
        elif "data" in result and len(result["data"]) > 0:
            image_b64 = result["data"][0].get("b64_json") or result["data"][0].get("base64")
        
        if image_b64:
            SafeLogger.info("NVIDIA NIM: Image successfully generated.")
            return base64.b64decode(image_b64)
            
        SafeLogger.warn(f"NVIDIA NIM: Response succeeded but no image found. Response keys: {list(result.keys())}")
    except Exception as e:
        SafeLogger.warn(f"NVIDIA NIM failed: {e}")
    return None

async def generate_interactive_reply(original_text, author, context):
    """Generates an AI reply for a social mention, maintaining the Sage persona."""
    try:
        genai_client = genai.Client(api_key=settings.gemini_key)
        
        # Format the system instruction with current temporal/session context
        system_instruction = INTERACTIVE_REPLY_INSTRUCTION.format(
            context=f"{context['session']} - {context['day']}"
        )
        
        config_args = {
            "temperature": 0.7,
            "max_output_tokens": 100
        }
        
        # Check for system_instruction support
        if "gemma" not in settings.gemini_model.lower():
            config_args["system_instruction"] = system_instruction
            
        prompt = f"User @{author} mentioned you: '{original_text}'. Respond insightfully as the Elite Sage."
        contents = f"{system_instruction}\n\n{prompt}" if "gemma" in settings.gemini_model.lower() else prompt
        
        response = await genai_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(**config_args)
        )
        
        return response.text.strip()
    except Exception as e:
        SafeLogger.error(f"Interaction generation failed: {e}")
        return None