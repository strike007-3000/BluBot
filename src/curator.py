import asyncio
import httpx
import feedparser
import re
import calendar
from datetime import datetime, timedelta, timezone
from google.genai import types
from google import genai
from .config import (
    RSS_FEEDS, TIER_1_SOURCES, TIER_2_SOURCES, HIDDEN_GEM_SOURCES, 
    TOPIC_MAP, CURATOR_SYSTEM_INSTRUCTION, MENTOR_SYSTEM_INSTRUCTION,
    SECONDARY_TOPICS, GEMINI_API_KEY, GEMINI_MODEL_PRIORITY
)
from .utils import retry_with_backoff, SafeLogger

def calculate_relevance_score(item, pub_date, now_utc, recent_topics=None):
    """Calculates a relevance score using a consistent reference time."""
    score = 0
    content_text = f"{item['title']} {item['summary']}".lower()

    # 1. Source Tier
    for domain in TIER_1_SOURCES:
        if domain in item['link']:
            score += 10
            break
    for domain in TIER_2_SOURCES:
        if domain in item['link']:
            score += 8
            break
    
    # 2. Keywords
    if any(kw in content_text for kw in ["launch", "release", "api", "feature"]):
        score += 5
    if any(kw in content_text for kw in ["breakthrough", "sota", "architecture"]):
        score += 7

    # 3. Topic Diversity Penalty
    if recent_topics:
        item_topic = "General"
        for topic, keywords in TOPIC_MAP.items():
            if any(kw.lower() in content_text for kw in keywords):
                item_topic = topic
                break
        if item_topic in recent_topics:
            score -= 12

    # 4. Time Decay (Fixed: Uses passed now_utc)
    age_hours = (now_utc - pub_date).total_seconds() / 3600
    score -= (age_hours * 0.5)

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

            summary = re.sub('<[^<]+?>', '', getattr(entry, 'summary', getattr(entry, 'description', "")))[:500]
            item = {
                "title": entry.title,
                "summary": summary,
                "link": entry.link,
                "source": getattr(feed.feed, 'title', url)
            }
            item["score"] = calculate_relevance_score(item, pub_date, now_utc, recent_topics)
            items.append(item)
        return items
    except Exception as e:
        SafeLogger.error(f"Feed error {url}: {type(e).__name__} - {e}")
        return []

async def fetch_news(client, seen_links=None, recent_topics=None):
    """Orchestrates parallel fetching of all RSS sources using a shared client."""
    if seen_links is None: seen_links = []
    # Expert Review Fix: Performance optimization O(1) lookups
    seen_set = set(seen_links)
    
    now_utc = datetime.now(timezone.utc)
    start_time = now_utc - timedelta(days=2)
    
    tasks = [fetch_single_feed(client, url, start_time, now_utc, seen_set, recent_topics) for url in RSS_FEEDS]
    results = await asyncio.gather(*tasks)

    all_entries = [e for sublist in results for e in sublist]
    
    # Bug Fix: Ensure no internal duplicates if one feed has multiple entries for same link
    unique_entries = {}
    for e in all_entries:
        if e['link'] not in unique_entries or e['score'] > unique_entries[e['link']]['score']:
            unique_entries[e['link']] = e
    
    all_entries = list(unique_entries.values())
    all_entries.sort(key=lambda x: x["score"], reverse=True)
    
    if not all_entries: return []

    # Hidden Gem Injection
    top_articles = all_entries[:7]
    remaining = all_entries[7:]
    has_gem = any(any(g in a['link'] for g in HIDDEN_GEM_SOURCES) for a in top_articles)

    if not has_gem:
        for art in remaining:
            if any(g in art['link'] for g in HIDDEN_GEM_SOURCES):
                top_articles.append(art)
                break
    
    while len(top_articles) < 8 and remaining:
        art = remaining.pop(0)
        if not any(a['link'] == art['link'] for a in top_articles):
            top_articles.append(art)
            
    return top_articles[:8]

def validate_summary(text):
    if not text or len(text) < 60: return False, "Short/Empty"
    if re.search(r'(.)\1{4,}', text): return False, "Repetition"
    if "#" not in text: return False, "No Hashtags"
    return True, "Valid"

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

@retry_with_backoff
async def summarize_news(news_items, context, mode="Curator"):
    """Synthesizes news using Gemini API with standardized Model constant."""
    if not news_items: return None, None, None

    client = genai.Client(api_key=GEMINI_API_KEY)
    news_text = "\n".join([f"- {i+1}. {item['title']} ({item['source']})" for i, item in enumerate(news_items)])
    
    instruction = MENTOR_SYSTEM_INSTRUCTION if mode == "Mentor" else CURATOR_SYSTEM_INSTRUCTION
    user_prompt = f"Day: {context['day']}, Session: {context['session']}, Mode: {mode}\nNews Data:\n{news_text}"
    
    config = types.GenerateContentConfig(system_instruction=instruction, temperature=0.7)

    response = await generate_content_with_failover(client, user_prompt, config, mode)
    raw_text = response.text.strip()

    topic = "General"
    summary = raw_text
    if "TOPIC:" in raw_text and "BODY:" in raw_text:
        parts = raw_text.split("BODY:", 1)
        topic = parts[0].replace("TOPIC:", "").strip()
        summary = parts[1].strip()

    is_valid, reason = validate_summary(summary)
    if is_valid: return summary, news_items[0]['link'], topic
    
    if reason == "No Hashtags" and len(summary) >= 30:
        return summary.strip() + " #AI #Tech", news_items[0]['link'], "General"
        
    raise ValueError(f"AI Validation Failed: {reason}")

@retry_with_backoff
async def generate_mentor_insight(context):
    """Fallback insight generation using standardized Model constant."""
    import random
    topic = random.choice(SECONDARY_TOPICS)
    SafeLogger.info(f"Triggering Mentor Fallback: {topic}")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    user_prompt = f"Current Time: {context['day']} {context['session']}\nStrategic Topic: {topic}"
    config = types.GenerateContentConfig(system_instruction=MENTOR_SYSTEM_INSTRUCTION, temperature=0.8)
    
    response = await generate_content_with_failover(client, user_prompt, config, "Mentor Fallback")
    summary = response.text.strip()
    
    if "BODY:" in summary:
        summary = summary.split("BODY:", 1)[1].strip()

    is_valid, reason = validate_summary(summary)
    if is_valid: return summary, None, "Strategy"
    
    return f"Strategy Insight: {topic}. Focus on long-term sustainability and architecture over hype. #AI #Strategy", None, "Strategy"

def get_temporal_context():
    """Calculates branding context."""
    now = datetime.now(timezone.utc)
    day = now.strftime("%A")
    session = "Morning Intelligence" if now.hour < 12 else "Afternoon Deep Dive"
    return {"day": day, "session": session, "theme": "Technical Analysis"}
