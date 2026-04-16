import asyncio
import httpx
import feedparser
import re
import calendar
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from google.genai import types
from google import genai
from .config import (
    RSS_FEEDS, TIER_1_SOURCES, TIER_2_SOURCES, HIDDEN_GEM_SOURCES, 
    TOPIC_MAP, CURATOR_SYSTEM_INSTRUCTION, MENTOR_SYSTEM_INSTRUCTION,
    SAGE_DESIGNER_INSTRUCTION, # Sage Designer
    SECONDARY_TOPICS, GEMINI_API_KEY, GEMINI_MODEL_PRIORITY,
    HIGH_SIGNAL_KEYWORDS, MOMENTUM_PRODUCTS,
    BASE_TIER_1, BASE_HIDDEN_GEM, BASE_TIER_2, SIGNAL_BOOST,
    MOMENTUM_BOOST, SYNERGY_BONUS, DIVERSITY_PENALTY, MAX_TOPIC_RECURRENCE,
    FEED_SUMMARY_MAX_CHARS
)
from .utils import retry_with_backoff, SafeLogger

MODEL_ATTEMPT_RETRIES = 2

def calculate_relevance_score(item, pub_date, now_utc, recent_topics=None):
    """Calculates a multi-factor breakthrough score for an article."""
    score = 0
    title_text = item['title'].lower()
    content_text = f"{item['title']} {item['summary']}".lower()
    
    # 1. Source Tiering
    source_score = 0
    is_gem = any(g in item['link'] for g in HIDDEN_GEM_SOURCES)
    if is_gem:
        source_score = BASE_HIDDEN_GEM
    else:
        for domain in TIER_1_SOURCES:
            if domain in item['link']:
                source_score = BASE_TIER_1
                break
        if source_score == 0:
            for domain in TIER_2_SOURCES:
                if domain in item['link']:
                    source_score = BASE_TIER_2
                    break
    score += source_score

    # 2. High-Signal Keyword Boosting
    signal_score = 0
    for kw in HIGH_SIGNAL_KEYWORDS:
        if kw in content_text:
            signal_score += SIGNAL_BOOST
            # Apply only once for any high signal match to avoid inflation
            break
    score += signal_score

    # 3. Momentum Product Boosting
    momentum_score = 0
    for product in MOMENTUM_PRODUCTS:
        if product in title_text:
            momentum_score += MOMENTUM_BOOST
            break # Apply once 
    score += momentum_score

    # 4. Topic Diversity Penalty (Legacy)
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

    # 5. Time Decay
    age_hours = (now_utc - pub_date).total_seconds() / 3600
    decay = age_hours * 0.5
    score -= decay

    # Store components for diagnostics
    item['_score_debug'] = {
        "source": source_score,
        "signal": signal_score,
        "momentum": momentum_score,
        "penalty": topic_penalty,
        "decay": round(decay, 1)
    }

    return score

@retry_with_backoff
async def fetch_single_feed(client, url, start_time, now_utc, seen_links, recent_topics):
    """Fetches and parses a single RSS feed with Bozo resilience."""
    try:
        response = await client.get(url, timeout=10)
        if response.status_code != 200:
            return []
            
        # Expert Review Fix: Wrap CPU-bound feedparser in to_thread
        feed = await asyncio.to_thread(feedparser.parse, response.text)
        
        # Expert Review Fix: Check for bozo (malformed feed)
        if feed.bozo:
            SafeLogger.warn(f"Feed {url} is malformed (Bozo detected). Parsing as-is.")

        items = []
        for entry in feed.entries:
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.updated_parsed), timezone.utc)

            if not pub_date or pub_date < start_time or entry.link in seen_links:
                continue

            # Expert Review Fix: Use BeautifulSoup for robust HTML stripping (Fixes Naive Regex Parsing)
            raw_summary = getattr(entry, 'summary', getattr(entry, 'description', ""))
            clean_summary = BeautifulSoup(raw_summary, "html.parser").get_text()
            summary = clean_summary[:FEED_SUMMARY_MAX_CHARS]
            
            item = {
                "title": entry.title,
                "summary": summary,
                "link": entry.link,
                "source": getattr(feed.feed, 'title', url)
            }
            item["score"] = calculate_relevance_score(item, pub_date, now_utc, recent_topics)
            items.append(item)
        return items
    except (httpx.HTTPError, asyncio.TimeoutError) as e:
        SafeLogger.warn(f"Network error fetching {url}: {type(e).__name__}")
        return []
    except Exception as e:
        SafeLogger.error(f"Unexpected feed error {url}: {type(e).__name__} - {e}")
        return []


def _extract_entities(text):
    """Simple extraction of potential topic entities (Proper Nouns, Products)."""
    # Look for capitalized sequences and common product IDs
    entities = re.findall(r'[A-Z][a-z]+(?: [A-Z][a-z]+)*', text)
    # Add product matches from config if present
    from .config import MOMENTUM_PRODUCTS
    for p in MOMENTUM_PRODUCTS:
        if p.lower() in text.lower():
            entities.append(p.title())
    return set(entities)

async def fetch_news(client, seen_links=None, recent_topics=None):
    """Orchestrates parallel fetching with Consensus Synergy and Greedy Diversity."""
    if seen_links is None: seen_links = []
    seen_set = set(seen_links)
    
    now_utc = datetime.now(timezone.utc)
    start_time = now_utc - timedelta(days=2)
    
    tasks = [fetch_single_feed(client, url, start_time, now_utc, seen_set, recent_topics) for url in RSS_FEEDS]
    results = await asyncio.gather(*tasks)

    all_raw_entries = [e for sublist in results for e in sublist]
    
    # 1. Deduplicate by link across feeds
    unique_by_link = {}
    for e in all_raw_entries:
        if e['link'] not in unique_by_link:
            unique_by_link[e['link']] = e
        else:
            # If same link found elsewhere, it's a "Synergy" signal
            unique_by_link[e['link']]['_synergy_count'] = unique_by_link[e['link']].get('_synergy_count', 1) + 1
    
    entries = list(unique_by_link.values())
    if not entries: return []

    # 2. Add Consensus Synergy Bonus
    for e in entries:
        count = e.get('_synergy_count', 1)
        if count > 1:
            e['score'] += SYNERGY_BONUS
            e['_score_debug']['synergy'] = SYNERGY_BONUS
        else:
            e['_score_debug']['synergy'] = 0
            
    # 3. Enrich with entities for Diversity Engine
    for e in entries:
        e['_entities'] = _extract_entities(f"{e['title']} {e['summary']}")

    # 4. Sort by preliminary score
    entries.sort(key=lambda x: x["score"], reverse=True)

    # 5. Greedy Diversity Selection (Top 8)
    selected = []
    topic_counts = {}
    remaining = entries.copy()

    while len(selected) < 8 and remaining:
        # Re-sort remaining based on diversity penalty
        for r in remaining:
            penalty = 0
            for ent in r['_entities']:
                count = topic_counts.get(ent, 0)
                if count >= MAX_TOPIC_RECURRENCE:
                    penalty = max(penalty, DIVERSITY_PENALTY)
            r['_current_score'] = r['score'] - penalty
            r['_score_debug']['diversity_penalty'] = penalty
        
        remaining.sort(key=lambda x: x["_current_score"], reverse=True)
        top_candidate = remaining.pop(0)
        
        # Select it
        selected.append(top_candidate)
        # Update entity counts
        for ent in top_candidate['_entities']:
            topic_counts[ent] = topic_counts.get(ent, 0) + 1

    # Ensure at least one hidden gem (Legacy injection logic)
    has_gem = any(any(g in a['link'] for g in HIDDEN_GEM_SOURCES) for a in selected)
    if not has_gem and selected:
        for r in remaining:
            if any(g in r['link'] for g in HIDDEN_GEM_SOURCES):
                selected.pop() # Remove least diverse/scored
                selected.append(r)
                break

    return selected[:8]


def validate_summary(text):
    if not text or len(text) < 60: return False, "Short/Empty"
    if re.search(r'(.)\1{4,}', text): return False, "Repetition"
    return True, "Valid"
    
def strip_markdown(text):
    """Failsafe to remove markdown bolding and italics often generated by LLMs."""
    if not text: return text
    # Remove bolding (** or __)
    text = re.sub(r'(\*\*|__)', '', text)
    # Remove italics (* or _) - Be careful with underscores in hashtags? 
    # Usually LLMs use * for italics. Let's just do * for now to avoid breaking hashtags.
    text = re.sub(r'(\*)', '', text)
    return text.strip()

def _extract_error_code_and_message(error):
    """Best-effort extraction of provider status details from SDK exceptions."""
    code = None
    for attr in ("status_code", "code", "http_status", "status"):
        value = getattr(error, attr, None)
        if value is not None:
            code = str(value)
            break

    response = getattr(error, "response", None)
    if code is None and response is not None:
        status_code = getattr(response, "status_code", None)
        if status_code is not None:
            code = str(status_code)

    message = str(error)
    return code, message

def _is_transient_model_error(error):
    """Transient Gemini/provider failures that should trigger model failover."""
    code, message = _extract_error_code_and_message(error)
    message_upper = message.upper()

    if code in {"503", "429"}:
        return True

    return "UNAVAILABLE" in message_upper

async def generate_content_with_failover(client, user_prompt, config, mode):
    """Attempts content generation across prioritized Gemini models."""
    last_error = None
    for model_id in GEMINI_MODEL_PRIORITY:
        try:
            SafeLogger.info(f"Synthesizing in {mode} Mode via {model_id}...")
            response = await client.aio.models.generate_content(model=model_id, contents=user_prompt, config=config)
            return response
        except Exception as e:
            last_error = e
            SafeLogger.warn(f"Model {model_id} failed in {mode} Mode: {type(e).__name__} - {e}")
    raise RuntimeError(
        f"All Gemini failover models failed for {mode} Mode. Last error: {type(last_error).__name__} - {last_error}"
    ) from last_error

async def summarize_news(news_items, context, mode="Curator"):
    """Synthesizes news using Gemini API with standardized Model constant."""
    if not news_items: return None, None, None

    client = genai.Client(api_key=GEMINI_API_KEY)
    news_text = "\n".join([f"- {i+1}. {item['title']} ({item['source']})" for i, item in enumerate(news_items)])
    
    instruction = MENTOR_SYSTEM_INSTRUCTION if mode == "Mentor" else CURATOR_SYSTEM_INSTRUCTION
    user_prompt = f"Day: {context['day']}, Session: {context['session']}, Mode: {mode}\nNews Data:\n{news_text}"
    
    config = types.GenerateContentConfig(system_instruction=instruction, temperature=0.7)

    attempted_models = []
    attempt_errors = []
    last_error = None

    for idx, model_id in enumerate(GEMINI_MODEL_PRIORITY):
        attempted_models.append(model_id)
        SafeLogger.info(
            f"gemini_attempt mode={mode} model={model_id} order={idx + 1}/{len(GEMINI_MODEL_PRIORITY)}"
        )

        for attempt in range(1, MODEL_ATTEMPT_RETRIES + 1):
            try:
                # Instruction Adaptation for Gemma vs Gemini
                if "gemma" in model_id.lower():
                    # Gemma path: Prepend instruction to user prompt
                    response = await client.aio.models.generate_content(
                        model=model_id,
                        contents=f"{instruction}\n\nUSER INPUT:\n{user_prompt}",
                        config=types.GenerateContentConfig(temperature=0.7)
                    )
                else:
                    # Gemini path: Use native system_instruction
                    response = await client.aio.models.generate_content(
                        model=model_id,
                        contents=user_prompt,
                        config=config
                    )
                raw_text = response.text.strip()

                topic = "General"
                summary = raw_text
                if "TOPIC:" in raw_text and "BODY:" in raw_text:
                    parts = raw_text.split("BODY:", 1)
                    topic = parts[0].replace("TOPIC:", "").strip()
                    summary = parts[1].strip()

                is_valid, reason = validate_summary(summary)
                if is_valid:
                    SafeLogger.info(f"model={model_id} attempt={attempt}/{MODEL_ATTEMPT_RETRIES} -> success")
                    SafeLogger.info(
                        f"gemini_failover_result mode={mode} success=true "
                        f"failover_succeeded={'true' if idx > 0 else 'false'} final_model={model_id}"
                    )
                    return strip_markdown(summary), news_items[0]['link'], topic, (idx > 0)

                if reason == "No Hashtags" and len(summary) >= 30:
                    SafeLogger.info(f"model={model_id} attempt={attempt}/{MODEL_ATTEMPT_RETRIES} -> success")
                    SafeLogger.info(
                        f"gemini_failover_result mode={mode} success=true "
                        f"failover_succeeded={'true' if idx > 0 else 'false'} final_model={model_id}"
                    )
                    return strip_markdown(summary.strip()) + " #AI #Tech", news_items[0]['link'], "General", (idx > 0)

                last_error = ValueError(f"AI Validation Failed: {reason}")
                raise last_error
            except ValueError as e:
                last_error = e
                attempt_errors.append({
                    "model": model_id,
                    "status": "validation_failed",
                    "error_class": "ValueError",
                    "message": str(e)
                })
                SafeLogger.warn(
                    f"gemini_error mode={mode} model={model_id} "
                    f"error_class=ValueError status=validation_failed reason={reason}"
                )
                if idx < len(GEMINI_MODEL_PRIORITY) - 1:
                    next_model = GEMINI_MODEL_PRIORITY[idx + 1]
                    SafeLogger.warn(
                        f"Model {model_id} failed validation ({reason}) - trying {next_model}"
                    )
                continue
            except Exception as e:
                last_error = e
                code, message = _extract_error_code_and_message(e)
                SafeLogger.warn(
                    f"model={model_id} attempt={attempt}/{MODEL_ATTEMPT_RETRIES} -> fail "
                    f"error_class={type(e).__name__} status={code or 'unknown'} message={message[:180]}"
                )
                attempt_errors.append({
                    "model": model_id,
                    "status": code or "unknown",
                    "error_class": type(e).__name__,
                    "message": message
                })
                SafeLogger.warn(
                    f"gemini_error mode={mode} model={model_id} "
                    f"error_class={type(e).__name__} status={code or 'unknown'} message={message[:180]}"
                )
                if idx < len(GEMINI_MODEL_PRIORITY) - 1:
                    next_model = GEMINI_MODEL_PRIORITY[idx + 1]
                    SafeLogger.warn(
                        f"Model {model_id} failed with error code={code or 'unknown'} "
                        f"message={message[:180]} - trying {next_model}"
                    )
                continue

    SafeLogger.error(
        f"gemini_failover_result mode={mode} success=false failover_succeeded=false "
        f"final_model=none attempted_models={attempted_models}"
    )
    attempt_statuses = [f"{a['model']}:{a['status']}" for a in attempt_errors]
    raise RuntimeError(
        "All Gemini models failed in summarize_news. "
        f"Attempted models (in order): {attempted_models}. "
        f"Attempt statuses: {attempt_statuses}. "
        f"Final error: {type(last_error).__name__} - {last_error}"
    ) from last_error

async def generate_mentor_insight(context):
    """Fallback insight generation using standardized Model constant."""
    import random
    topic = random.choice(SECONDARY_TOPICS)
    SafeLogger.info(f"Triggering Mentor Fallback: {topic}")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    user_prompt = f"Current Time: {context['day']} {context['session']}\nStrategic Topic: {topic}"
    config = types.GenerateContentConfig(system_instruction=MENTOR_SYSTEM_INSTRUCTION, temperature=0.8)

    attempted_models = []
    attempt_errors = []
    last_error = None
    mode = "Mentor Fallback"

    for idx, model_id in enumerate(GEMINI_MODEL_PRIORITY):
        attempted_models.append(model_id)
        SafeLogger.info(
            f"gemini_attempt mode={mode} model={model_id} order={idx + 1}/{len(GEMINI_MODEL_PRIORITY)}"
        )

        for attempt in range(1, MODEL_ATTEMPT_RETRIES + 1):
            try:
                # Instruction Adaptation for Gemma vs Gemini
                if "gemma" in model_id.lower():
                    # Gemma path: Prepend instruction to user prompt
                    response = await client.aio.models.generate_content(
                        model=model_id,
                        contents=f"{instruction}\n\nUSER INPUT:\n{user_prompt}",
                        config=types.GenerateContentConfig(temperature=0.7)
                    )
                else:
                    # Gemini path: Use native system_instruction
                    response = await client.aio.models.generate_content(
                        model=model_id,
                        contents=user_prompt,
                        config=config
                    )
                summary = response.text.strip()

                if "BODY:" in summary:
                    summary = summary.split("BODY:", 1)[1].strip()

                is_valid, reason = validate_summary(summary)
                if is_valid:
                    SafeLogger.info(f"model={model_id} attempt={attempt}/{MODEL_ATTEMPT_RETRIES} -> success")
                    SafeLogger.info(
                        f"gemini_failover_result mode={mode} success=true "
                        f"failover_succeeded={'true' if idx > 0 else 'false'} final_model={model_id}"
                    )
                    return strip_markdown(summary), None, "Strategy", (idx > 0)

                if reason == "No Hashtags" and len(summary) >= 30:
                    SafeLogger.info(f"model={model_id} attempt={attempt}/{MODEL_ATTEMPT_RETRIES} -> success")
                    SafeLogger.info(
                        f"gemini_failover_result mode={mode} success=true "
                        f"failover_succeeded={'true' if idx > 0 else 'false'} final_model={model_id}"
                    )
                    return strip_markdown(summary.strip()) + " #AI #Tech", None, "Strategy", (idx > 0)

                last_error = ValueError(f"AI Validation Failed: {reason}")
                raise last_error
            except ValueError as e:
                last_error = e
                attempt_errors.append({
                    "model": model_id,
                    "status": "validation_failed",
                    "error_class": "ValueError",
                    "message": str(e)
                })
                SafeLogger.warn(
                    f"gemini_error mode={mode} model={model_id} "
                    f"error_class=ValueError status=validation_failed reason={reason}"
                )
                if idx < len(GEMINI_MODEL_PRIORITY) - 1:
                    next_model = GEMINI_MODEL_PRIORITY[idx + 1]
                    SafeLogger.warn(
                        f"Model {model_id} failed validation ({reason}) - trying {next_model}"
                    )
                continue
            except Exception as e:
                last_error = e
                code, message = _extract_error_code_and_message(e)
                SafeLogger.warn(
                    f"model={model_id} attempt={attempt}/{MODEL_ATTEMPT_RETRIES} -> fail "
                    f"error_class={type(e).__name__} status={code or 'unknown'} message={message[:180]}"
                )
                attempt_errors.append({
                    "model": model_id,
                    "status": code or "unknown",
                    "error_class": type(e).__name__,
                    "message": message
                })
                SafeLogger.warn(
                    f"gemini_error mode={mode} model={model_id} "
                    f"error_class={type(e).__name__} status={code or 'unknown'} message={message[:180]}"
                )
                if idx < len(GEMINI_MODEL_PRIORITY) - 1:
                    next_model = GEMINI_MODEL_PRIORITY[idx + 1]
                    SafeLogger.warn(
                        f"Model {model_id} failed with error code={code or 'unknown'} "
                        f"message={message[:180]} - trying {next_model}"
                    )
                continue

    SafeLogger.error(
        f"gemini_failover_result mode={mode} success=false failover_succeeded=false "
        f"final_model=none attempted_models={attempted_models}"
    )
    attempt_statuses = [f"{a['model']}:{a['status']}" for a in attempt_errors]
    raise RuntimeError(
        "All Gemini models failed in generate_mentor_insight. "
        f"Attempted models (in order): {attempted_models}. "
        f"Attempt statuses: {attempt_statuses}. "
        f"Final error: {type(last_error).__name__} - {last_error}"
    ) from last_error

def get_temporal_context():
    """Calculates branding context."""
    now = datetime.now(timezone.utc)
    day = now.strftime("%A")
    session = "Morning Intelligence" if now.hour < 12 else "Afternoon Deep Dive"
    theme = "Technical Analysis"
    return {"day": day, "session": session, "theme": theme}

async def generate_visual_prompt(client, summary, topic):
    """Uses Gemini to generate a high-fidelity visual prompt for Imagen 4."""
    user_prompt = f"Topic: {topic}\nNews Summary: {summary}\nTask: Create a minimalist technical visual prompt."
    config = types.GenerateContentConfig(
        system_instruction=SAGE_DESIGNER_INSTRUCTION,
        temperature=0.8
    )
    
    try:
        # We use the primary Gemini model for prompt generation
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL_PRIORITY[0],
            contents=user_prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        SafeLogger.warn(f"Sage Designer prompt generation failed: {e}")
        return f"A minimalist high-tech representation of {topic} and AI."