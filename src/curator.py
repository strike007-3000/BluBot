import asyncio
import os
import httpx
import feedparser
import re
import calendar
import base64
from typing import Tuple, List, Optional
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from google.genai import types, errors
from google import genai
from src.settings import settings
from src.config import (
    RSS_FEEDS, TIER_1_SOURCES, TIER_2_SOURCES, HIDDEN_GEM_SOURCES,
    TOPIC_MAP, CURATOR_SYSTEM_INSTRUCTION, MENTOR_SYSTEM_INSTRUCTION,
    INTERACTIVE_REPLY_INSTRUCTION,
    SAGE_DESIGNER_INSTRUCTION, SECONDARY_TOPICS, GEMINI_MODEL_PRIORITY,
    ALT_TEXT_MODELS, VISUAL_PROMPT_MODEL,
    normalize_gemini_model_id,
    HIGH_SIGNAL_KEYWORDS, MOMENTUM_PRODUCTS,
    BASE_TIER_1, BASE_HIDDEN_GEM, BASE_TIER_2, SIGNAL_BOOST,
    MOMENTUM_BOOST, SYNERGY_BONUS, DIVERSITY_PENALTY, MAX_TOPIC_RECURRENCE,
    FEED_SUMMARY_MAX_CHARS
)
from src.utils import retry_with_backoff, SafeLogger
from src.models import ImageValidationResult

_MARKDOWN_STRIP_RE = re.compile(r'(\*\*|__|\*)')

def calculate_relevance_score(item, pub_date, now_utc, recent_topics=None, recent_categories=None, watch_topics=None):
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

    # 6. Watchlist Topic Boosting (Word-boundary matching, max boost across all watches capped at +8)
    watchlist_score = 0
    matched_watch_topic = None
    if watch_topics:
        best_boost = 0
        best_topic = None
        for w in watch_topics:
            w_topic = w.get("topic", "").lower() if isinstance(w, dict) else str(w).lower()
            w_keywords = w.get("keywords", [w_topic]) if isinstance(w, dict) else [w_topic]

            raw_boost = 0
            # Word-boundary matching to prevent false positives like 'ai' inside 'maintenance'
            if w_topic and re.search(r'\b' + re.escape(w_topic) + r'\b', title_text):
                raw_boost = 8
            elif any(kw and re.search(r'\b' + re.escape(kw.lower()) + r'\b', title_text) for kw in w_keywords):
                raw_boost = 5
            elif any(kw and re.search(r'\b' + re.escape(kw.lower()) + r'\b', content_text) for kw in w_keywords):
                raw_boost = 3

            if raw_boost > best_boost:
                best_boost = raw_boost
                best_topic = w_topic
                if best_boost >= 8:
                    break

        if best_boost > 0:
            watchlist_score = min(8, best_boost)
            matched_watch_topic = best_topic
            score += watchlist_score

    # 7. Time Decay
    age_hours = (now_utc - pub_date).total_seconds() / 3600
    decay = age_hours * 0.5
    score -= decay

    item['_score_debug'] = {
        "source": source_score,
        "signal": signal_score,
        "momentum": momentum_score,
        "watchlist": watchlist_score,
        "matched_watch": matched_watch_topic,
        "penalty": topic_penalty,
        "category_penalty": category_penalty,
        "decay": round(decay, 1)
    }
    return score

async def fetch_single_feed(client, url, start_time, now_utc, seen_links, recent_topics, recent_categories=None, watch_topics=None):
    """Fetches and parses a single RSS feed, returning (url, items, is_healthy, error_msg)."""
    try:
        from src.config import URL_TO_ID
        source_id = URL_TO_ID.get(url, "unknown")

        try:
            response = await client.get(url, timeout=10)
        except Exception as e:
            return url, [], False, f"Network error: {type(e).__name__}"

        if response.status_code != 200:
            return url, [], False, f"HTTP {response.status_code}"

        feed = await asyncio.to_thread(feedparser.parse, response.content)

        # Health check before recency/seen-link filtering
        if feed.bozo and not feed.entries:
            return url, [], False, "Parse error/Invalid RSS"
        if not feed.entries:
            return url, [], False, "Empty feed"

        items = []
        from src.utils import normalize_url
        normalized_seen_links = {normalize_url(sl) for sl in seen_links if sl}
        for entry in feed.entries:
            link = getattr(entry, 'link', None)
            if not link:
                continue
            canonical_link = normalize_url(link)
            if link in seen_links or canonical_link in normalized_seen_links:
                continue

            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.updated_parsed), timezone.utc)
            else:
                pub_date = now_utc

            # Explicit recency cutoff enforcement
            if start_time and pub_date < start_time:
                continue

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
            item["score"] = calculate_relevance_score(item, pub_date, now_utc, recent_topics, recent_categories, watch_topics)
            items.append(item)

        return url, items, True, None
    except Exception as e:
        return url, [], False, f"Unexpected error: {type(e).__name__}"

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "new", "how",
    "why", "what"
}

_PUBLISHER_SUFFIX_RE = re.compile(r'\s+[\-\|\:\•]\s+([A-Za-z0-9\s]+)$')
_VERSION_RE = re.compile(r'\b(v?\d+(?:\.\d+)*[a-z]?)\b', re.IGNORECASE)

def normalize_headline(title: str) -> Tuple[set, set]:
    """Normalizes a headline into token sets and extracted version numbers."""
    if not title:
        return set(), set()

    cleaned = title.strip()
    match = _PUBLISHER_SUFFIX_RE.search(cleaned)
    if match:
        cleaned = cleaned[:match.start()].strip()

    versions = set(m.lower() for m in _VERSION_RE.findall(cleaned))
    words = re.findall(r'\b[a-zA-Z0-9\-\.]+\b', cleaned.lower())
    tokens = {w for w in words if w not in _STOPWORDS and len(w) > 1}
    return tokens, versions

def calculate_title_similarity(tokens1: set, versions1: set, tokens2: set, versions2: set) -> bool:
    """Conservative headline similarity check: token overlap and matching versions."""
    if len(tokens1) < 2 or len(tokens2) < 2:
        return False

    if versions1 and versions2 and versions1 != versions2:
        return False

    all_tokens1 = tokens1 | versions1
    all_tokens2 = tokens2 | versions2

    intersection = all_tokens1 & all_tokens2
    union = all_tokens1 | all_tokens2
    if not union:
        return False

    jaccard = len(intersection) / len(union)
    uncommon_matches = len(intersection)

    return jaccard >= 0.25 and uncommon_matches >= 2

def cluster_articles(raw_entries: List[dict]) -> List[dict]:
    """Clusters articles by title similarity and domain corroboration."""
    if not raw_entries:
        return []

    parsed_entries = []
    for entry in raw_entries:
        tokens, versions = normalize_headline(entry.get("title", ""))
        from urllib.parse import urlparse
        domain = urlparse(entry.get("link", "")).netloc.lower()
        parsed_entries.append({
            "entry": entry,
            "tokens": tokens,
            "versions": versions,
            "domain": domain,
            "clustered": False
        })

    clusters = []
    for i, item in enumerate(parsed_entries):
        if item["clustered"]:
            continue

        current_cluster = [item]
        item["clustered"] = True

        for j in range(i + 1, len(parsed_entries)):
            other = parsed_entries[j]
            if other["clustered"]:
                continue

            if calculate_title_similarity(item["tokens"], item["versions"], other["tokens"], other["versions"]):
                current_cluster.append(other)
                other["clustered"] = True

        clusters.append(current_cluster)

    result_articles = []
    from src.config import FEED_SCORE_MAP

    for cluster_id_idx, cluster in enumerate(clusters):
        lead_item_obj = max(
            cluster,
            key=lambda x: (
                x["entry"].get("score", 0),
                FEED_SCORE_MAP.get(x["entry"].get("source_id"), 0),
                x["entry"].get("published", "")
            )
        )
        lead = dict(lead_item_obj["entry"])

        unique_domains = set(x["domain"] for x in cluster if x["domain"])
        supporting_items = [x["entry"] for x in cluster if x["entry"]["link"] != lead["link"]]

        has_corroboration = len(unique_domains) >= 2
        lead["consensus_synergy"] = has_corroboration
        if has_corroboration:
            lead["score"] = lead.get("score", 0) + SYNERGY_BONUS

        supporting_sources = [item.get("source", "Unknown") for item in supporting_items]
        supporting_links = [item.get("link", "") for item in supporting_items]

        lead["cluster_id"] = f"cluster_{cluster_id_idx}"
        lead["supporting_sources"] = supporting_sources
        lead["supporting_links"] = supporting_links

        debug = dict(lead.get("_score_debug", {}))
        debug["cluster_size"] = len(cluster)
        debug["cluster_lead"] = lead.get("source_id", "unknown")
        debug["supporting_sources"] = supporting_sources
        debug["consensus_bonus_reason"] = "domain_corroboration" if has_corroboration else "none"
        lead["_score_debug"] = debug

        result_articles.append(lead)

    return result_articles

async def fetch_news(client, seen_links=None, recent_topics=None, feed_list=None, limit=8, recent_categories=None, watch_topics=None, days_lookback=2):
    """Orchestrates parallel fetching with Consensus Synergy and Greedy Diversity, returning (articles, feed_outcomes)."""
    now_utc = datetime.now(timezone.utc)
    source_list = feed_list if feed_list is not None else RSS_FEEDS
    tasks = [fetch_single_feed(client, url, now_utc - timedelta(days=days_lookback), now_utc, seen_links or [], recent_topics, recent_categories, watch_topics) for url in source_list]
    results = await asyncio.gather(*tasks)

    feed_outcomes = []
    all_raw_entries = []
    for url, items, is_healthy, error_msg in results:
        feed_outcomes.append((url, is_healthy, error_msg))
        all_raw_entries.extend(items)

    # Exact URL deduplication
    unique_by_link = {}
    for e in all_raw_entries:
        if e['link'] not in unique_by_link:
            unique_by_link[e['link']] = e

    deduped_entries = list(unique_by_link.values())

    # Cross-source Story Clustering
    entries = cluster_articles(deduped_entries)
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

    if limit is not None:
        entries = entries[:limit]

    return entries, feed_outcomes

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
        available_models = set()
        async for m in await genai_client.aio.models.list():
            available_models.add(normalize_gemini_model_id(m.name))

        pruned = []
        for model_id in GEMINI_MODEL_PRIORITY:
            if normalize_gemini_model_id(model_id) in available_models:
                pruned.append(model_id)

        if pruned:
            SafeLogger.info(f"Gemini Model Discovery: Discovered active models: {pruned}")
            GEMINI_MODEL_PRIORITY.clear()
            GEMINI_MODEL_PRIORITY.extend(pruned)
        else:
            SafeLogger.warn("Gemini Model Discovery: None of the prioritized models were returned by the API. Keeping defaults.")
    except Exception as e:
        SafeLogger.warn(f"Gemini Model Discovery: API call failed ({e}). Falling back to configured defaults.")

def _derive_topic_locally(title: str, summary: str, source_id: str) -> str:
    """Derives a topic deterministically using TOPIC_MAP keywords, then normalized category, then General."""
    text_lower = f"{title} {summary}".lower()
    for topic, keywords in TOPIC_MAP.items():
        if topic == "General":
            continue
        if any(kw.lower() in text_lower for kw in keywords):
            return topic

    from src.config import FEED_CATEGORY_MAP
    category = FEED_CATEGORY_MAP.get(source_id, "unknown")
    if category and category != "unknown":
        return category.replace("_", " ").title()

    return "General"

async def summarize_news(news_items, context, mode="Curator", last_dialect=None, writing_style=None):
    """Synthesizes news with SDK-aware Failover Loop and randomized Dialect adaptation."""
    if not news_items: return None, None, "General", False, None

    if settings.is_dry_run:
        SafeLogger.info("Dry run: Bypassing Gemini synthesis call.")
        return "Mock Dry-Run Post Summary: BluBot is operating correctly in dry-run mode. #AI #News", news_items[0]['link'], "Dry Run Curation", False, "ANALYTICAL"

    client = genai.Client(api_key=settings.gemini_key)

    from .config import CURATOR_SYSTEM_INSTRUCTION, PERSONA_DIALECTS
    import random

    # Select Dialect (ensure variety)
    available_dialects = list(PERSONA_DIALECTS.keys())
    if last_dialect in available_dialects and len(available_dialects) > 1:
        available_dialects.remove(last_dialect)

    current_dialect = random.choice(available_dialects)
    dialect_instruction = PERSONA_DIALECTS[current_dialect]

    formatted_lines = []
    for i, item in enumerate(news_items):
        line = f"- {i+1}. {item['title']} ({item['source']})"
        if item.get('consensus_synergy') and item.get('supporting_sources'):
            line += f" [Corroborated by: {', '.join(item['supporting_sources'])}]"
        formatted_lines.append(line)
    news_text = "\n".join(formatted_lines)

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

    lead_item = news_items[0]
    lead_title = lead_item.get('title', '')
    lead_summary = lead_item.get('summary', '')
    lead_source_id = lead_item.get('source_id', 'unknown')

    for idx, model_id in enumerate(GEMINI_MODEL_PRIORITY):
        try:
            SafeLogger.info(f"Synthesizing via {model_id}...")

            config_args = {
                "system_instruction": combined_instruction
            }
            # gemini-3.7-flash and gemini-3.6-flash omit legacy temperature
            normalized = normalize_gemini_model_id(model_id)
            if normalized not in ("gemini-3.7-flash", "gemini-3.6-flash"):
                config_args["temperature"] = 0.7

            # Apply thinking config if supported
            if supports_thinking(model_id):
                budget = settings.thinking_budget if settings.thinking_budget is not None else 1024
                config_args["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)

            response = await client.aio.models.generate_content(
                model=model_id, contents=user_prompt,
                config=types.GenerateContentConfig(**config_args)
            )

            raw_text = (response.text or "").strip()
            topic = None
            summary = None

            if "TOPIC:" in raw_text and "BODY:" in raw_text:
                parts = raw_text.split("BODY:", 1)
                parsed_topic = parts[0].replace("TOPIC:", "").strip()
                parsed_body = parts[1].strip()
                if len(parsed_body) > 60:
                    summary = parsed_body
                    topic = parsed_topic if parsed_topic else _derive_topic_locally(lead_title, lead_summary, lead_source_id)
            elif "BODY:" in raw_text:
                parsed_body = raw_text.split("BODY:", 1)[1].strip()
                if len(parsed_body) > 60:
                    summary = parsed_body
                    topic = _derive_topic_locally(lead_title, lead_summary, lead_source_id)
            else:
                if len(raw_text) > 60:
                    summary = raw_text
                    topic = _derive_topic_locally(lead_title, lead_summary, lead_source_id)

            if summary and len(summary) > 60:
                is_failover = (idx > 0)
                SafeLogger.info(f"Synthesis successful via {model_id} (Topic: {topic}, Failover: {is_failover}).")
                return strip_markdown(summary), lead_item['link'], topic, is_failover, current_dialect
            else:
                SafeLogger.warn(f"Model {model_id} produced empty or insufficient body. Rotating to next model.")

        except errors.APIError as e:
            code = getattr(e, "code", "unknown")
            msg_snippet = (getattr(e, "message", None) or str(e))[:80].replace("\n", " ")
            SafeLogger.warn(f"Model {model_id} APIError ({code}, {type(e).__name__}): {msg_snippet}")
            if code in (401, 403):
                SafeLogger.error(f"Critical credential failure ({code}) on {model_id}. Halting model rotation.")
                break
            # 503 / 429 / 400 / 404 / other API errors rotate immediately
        except Exception as e:
            msg_snippet = str(e)[:80].replace("\n", " ")
            SafeLogger.warn(f"Model {model_id} unexpected failure ({type(e).__name__}): {msg_snippet}")
            if idx == len(GEMINI_MODEL_PRIORITY) - 1:
                raise e

    return None, None, "General", False, None

async def generate_mentor_insight(context):
    if settings.is_dry_run:
        SafeLogger.info("Dry run: Bypassing Gemini mentor insight call.")
        return "Mock Dry-Run Mentor Insight: Focus on strategic scaling in dry-run mode. #Strategy", None, "Strategy", False

    key = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=key)
    topic = SECONDARY_TOPICS[0]

    for idx, model_id in enumerate(GEMINI_MODEL_PRIORITY):
        try:
            SafeLogger.info(f"Generating Mentor Insight via {model_id}...")

            config_args = {
                "system_instruction": MENTOR_SYSTEM_INSTRUCTION
            }
            # gemini-3.7-flash and gemini-3.6-flash omit legacy temperature
            normalized = normalize_gemini_model_id(model_id)
            if normalized not in ("gemini-3.7-flash", "gemini-3.6-flash"):
                config_args["temperature"] = 0.8

            # Apply thinking config if supported
            if supports_thinking(model_id):
                budget = settings.thinking_budget if settings.thinking_budget is not None else 1024
                config_args["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)

            contents = f"Topic: {topic}"

            response = await client.aio.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(**config_args)
            )
            summary = (response.text or "").strip()
            if "BODY:" in summary:
                summary = summary.split("BODY:", 1)[1].strip()

            if summary:
                is_failover = (idx > 0)
                return strip_markdown(summary), None, "Strategy", is_failover
        except errors.APIError as e:
            code = getattr(e, "code", "unknown")
            msg_snippet = (getattr(e, "message", None) or str(e))[:80].replace("\n", " ")
            SafeLogger.warn(f"Mentor Insight APIError on {model_id} ({code}, {type(e).__name__}): {msg_snippet}")
            if code in (401, 403):
                SafeLogger.error(f"Critical credential failure ({code}) on {model_id}. Halting model rotation.")
                break
        except Exception as e:
            msg_snippet = str(e)[:80].replace("\n", " ")
            SafeLogger.warn(f"Mentor Fallback unexpected failure on {model_id} ({type(e).__name__}): {msg_snippet}")

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
            model=VISUAL_PROMPT_MODEL,
            contents=prompt_content,
            config=types.GenerateContentConfig(system_instruction=SAGE_DESIGNER_INSTRUCTION, temperature=0.8)
        )
        return response.text.strip()
    except Exception:
        return f"Minimalist tech illustration of {topic}"

def validate_opengraph_image(image_bytes: bytes, image_url: str) -> ImageValidationResult:
    """Validates the OpenGraph image and returns structured ImageValidationResult."""
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

def _derive_alt_text_fallback(article_title: str = "", category: str = "", topic: str = "General") -> str:
    """Derives a neutral, non-presumptuous alt-text fallback when AI Vision is unavailable."""
    if article_title:
        return f"Image accompanying news about {article_title}"
    elif category and category != "unknown":
        readable_cat = category.replace("_", " ")
        return f"Image accompanying a {readable_cat} news post"
    elif topic and topic != "General":
        return f"Image accompanying news about {topic}"
    else:
        return "Image accompanying a technology news post"

async def generate_image_alt_text(
    image_bytes: bytes,
    prompt: str = "",
    article_title: str = "",
    category: str = "",
    topic: str = "General"
) -> str:
    """Generates screen-reader-friendly alt text using Gemini Vision or accurate local fallback."""
    if not image_bytes:
        SafeLogger.info("Alt text: missing")
        return ""

    from src.utils import get_image_mime
    mime_type = get_image_mime(image_bytes)

    # Strictly validate MIME; never falsify unsupported/unknown bytes as JPEG
    if not mime_type or mime_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        SafeLogger.warn(f"Alt text: Unsupported or unrecognized image MIME type ({mime_type}). Using local fallback.")
        SafeLogger.info("Alt text: article-derived fallback")
        return _derive_alt_text_fallback(article_title, category, topic)

    client = genai.Client(api_key=settings.gemini_key)

    for model_to_use in ALT_TEXT_MODELS:
        try:
            response = await client.aio.models.generate_content(
                model=model_to_use,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                    ),
                    f"Describe this image in one concise sentence (maximum 100 characters) for use as screen-reader alt text. The prompt or topic context was: '{prompt or topic}'. Do not include metadata, preambles, or hashtags."
                ]
            )
            result = (response.text or "").strip().replace('"', '').replace('\n', ' ')
            if result:
                SafeLogger.info(f"Alt text: generated ({model_to_use})")
                return result
        except Exception as e:
            code = getattr(e, "code", None)
            msg_snippet = str(e)[:80].replace("\n", " ")
            err_info = f" ({code}, {type(e).__name__})" if code else f" ({type(e).__name__})"
            SafeLogger.warn(f"Alt text generation failed via {model_to_use}{err_info}: {msg_snippet}")

    SafeLogger.info("Alt text: article-derived fallback")
    return _derive_alt_text_fallback(article_title, category, topic)

async def generate_imagen_image(genai_client, prompt: str):
    """Calls Gemini API for image generation using active recommended models."""
    try:
        from src.config import IMAGEN_MODEL
        from google.genai import types
        SafeLogger.info(f"Sage Designer: Generating Imagen thumbnail with {IMAGEN_MODEL}...")

        if IMAGEN_MODEL.startswith("imagen-"):
            # Legacy Imagen models
            response = await genai_client.aio.models.generate_images(
                model=IMAGEN_MODEL,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio='1:1'
                )
            )
            if response.generated_images:
                img = response.generated_images[0].image
                return getattr(img, "image_bytes", None) or getattr(img, "_image_bytes", None)
        else:
            # Recommended Gemini multimodal image models (e.g. gemini-3.1-flash-image)
            response = await genai_client.aio.models.generate_content(
                model=IMAGEN_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                )
            )
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        return part.inline_data.data
    except Exception as e:
        SafeLogger.warn(f"Imagen generation failed: {e}")
    return None

from io import BytesIO
from PIL import Image, UnidentifiedImageError
from urllib.parse import quote

def validate_image_bytes(image_bytes: bytes) -> bool:
    if not image_bytes:
        return False

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
            return image.format in {"JPEG", "PNG", "WEBP"}
    except (UnidentifiedImageError, OSError, ValueError):
        return False

async def generate_pollinations_image(
    prompt: str,
    client: httpx.AsyncClient,
) -> bytes | None:
    encoded_prompt = quote(prompt, safe="")
    url = f"{settings.pollinations_api_url.rstrip('/')}/{encoded_prompt}"
    headers = {
        "Accept": "image/*",
    }

    params = {
        "width": 1024,
        "height": 1024,
        "model": "flux",
        "seed": 0,
        "nologo": "true",
    }


    try:
        # 90 seconds timeout
        timeout = httpx.Timeout(90.0, connect=10.0)
        response = await client.get(url, headers=headers, params=params, timeout=timeout)

        status_code = response.status_code
        if status_code in [401, 402, 429] or (500 <= status_code < 600):
            SafeLogger.warn(f"Pollinations HTTP error: Status={status_code}")

        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            SafeLogger.warn(f"Pollinations response content type invalid: {content_type}")
            return None

        img_bytes = response.content
        if not validate_image_bytes(img_bytes):
            SafeLogger.warn("Pollinations response returned invalid image bytes")
            return None

        return img_bytes

    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
        SafeLogger.warn(f"Pollinations failed: {e}")
        return None

async def generate_huggingface_image(
    prompt: str,
    client: httpx.AsyncClient,
) -> bytes | None:
    # Use hf API key if present, otherwise fall back to nvidia key for token backward compatibility
    token = settings.huggingface_api_key or settings.nvidia_key
    if not token:
        SafeLogger.info("Hugging Face: Skipping because neither huggingface_api_key nor nvidia_key is set.")
        return None

    model = settings.huggingface_image_model
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "width": 1024,
            "height": 1024,
            "seed": 0
        }
    }


    try:
        timeout = httpx.Timeout(90.0, connect=10.0)
        response = await client.post(url, headers=headers, json=payload, timeout=timeout)

        status_code = response.status_code
        if status_code in [401, 402, 403, 429, 503]:
            SafeLogger.warn(f"Hugging Face HTTP error: Status={status_code}")

        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            SafeLogger.warn(f"Hugging Face response content type invalid: {content_type}")
            return None

        img_bytes = response.content
        if not validate_image_bytes(img_bytes):
            SafeLogger.warn("Hugging Face response returned invalid image bytes")
            return None

        return img_bytes

    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
        SafeLogger.warn(f"Hugging Face failed: {e}")
        return None

@retry_with_backoff
async def generate_nvidia_image(
    prompt: str,
    client: httpx.AsyncClient,
) -> bytes | None:
    """Calls NVIDIA NIM for SD3-Medium image generation with robust response parsing."""
    from src.config import NVIDIA_INVOKE_URL
    if not settings.nvidia_key:
        SafeLogger.info("NVIDIA NIM: Skipping because nvidia_key is missing.")
        return None

    headers = {
        "Authorization": f"Bearer {settings.nvidia_key}",
        "Accept": "application/json",
    }
    payload = {
        "prompt": prompt,
        "aspect_ratio": "1:1",
        "mode": "text-to-image",
        "model": "sd3",
    }

    try:
        # 45 seconds timeout
        timeout = httpx.Timeout(45.0, connect=10.0)
        response = await client.post(NVIDIA_INVOKE_URL, headers=headers, json=payload, timeout=timeout)
        if 400 <= response.status_code < 500 and response.status_code not in {408, 429}:
            SafeLogger.warn(f"NVIDIA NIM returned permanent HTTP {response.status_code}. Skipping retries and falling back immediately.")
            return None
        response.raise_for_status()
        result = response.json()

        if "image" in result:
            img_bytes = base64.b64decode(result["image"])
            if not validate_image_bytes(img_bytes):
                SafeLogger.warn("NVIDIA NIM returned invalid image bytes")
                return None
            return img_bytes
    except (httpx.TimeoutException, httpx.RequestError) as e:
        SafeLogger.warn(f"NVIDIA NIM network/timeout error: {e}")
        raise e
    except httpx.HTTPStatusError as e:
        if 400 <= e.response.status_code < 500 and e.response.status_code not in {408, 429}:
            SafeLogger.warn(f"NVIDIA NIM returned permanent HTTP {e.response.status_code}. Skipping retries and falling back immediately.")
            return None
        SafeLogger.warn(f"NVIDIA NIM HTTP error {e.response.status_code}: {e}")
        raise e
    except Exception as e:
        SafeLogger.warn(f"NVIDIA NIM failed: {e}")
        return None
    return None

IMAGE_PROVIDER_CHAINS = {
    "pollinations": ["pollinations", "huggingface"],
    "huggingface": ["huggingface", "pollinations"],
    "nvidia": ["nvidia", "huggingface", "pollinations"],
}

IMAGE_GENERATORS = {
    "pollinations": generate_pollinations_image,
    "huggingface": generate_huggingface_image,
    "nvidia": generate_nvidia_image,
}

async def generate_ai_image(client: httpx.AsyncClient, genai_client, prompt: str) -> bytes | None:
    """Generates an image using the configured provider dispatcher chain, falling back to Imagen if both fail."""
    configured_provider = settings.image_provider.strip().lower()

    # Explicitly handle legacy/explicit selections.
    # If the user explicitly configured 'imagen', run it directly and skip the dynamic chain.
    if configured_provider == "imagen":
        if genai_client is not None:
            SafeLogger.info("Sage Designer: Generating Imagen 4 thumbnail...")
            try:
                return await generate_imagen_image(genai_client, prompt)
            except Exception as e:
                SafeLogger.warn(f"Imagen generation failed: {e}")
        return None

    # Handle legacy 'nvidia' setting: only remap to 'huggingface' if there is no nvidia_key configured
    if configured_provider == "nvidia" and not settings.nvidia_key:
        configured_provider = "huggingface"

    chain = IMAGE_PROVIDER_CHAINS.get(
        configured_provider,
        ["huggingface", "pollinations"],
    )

    attempted = set()
    img_bytes = None

    for provider_name in chain:
        if provider_name in attempted:
            continue

        attempted.add(provider_name)
        generator = IMAGE_GENERATORS.get(provider_name)

        if generator is None:
            continue

        try:
            img_bytes = await generator(prompt, client)
        except Exception as e:
            SafeLogger.warn(f"Unexpected image provider failure: {provider_name} ({e})")
            continue

        if img_bytes:
            SafeLogger.info(f"Image generated successfully using {provider_name}")
            return img_bytes

    SafeLogger.error("All dynamic image providers failed")

    if genai_client is not None:
        SafeLogger.info("Falling back to Imagen for image generation...")
        try:
            return await generate_imagen_image(genai_client, prompt)
        except Exception as e:
            SafeLogger.warn(f"Imagen fallback also failed: {e}")

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
