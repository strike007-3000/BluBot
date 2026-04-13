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
    TOPIC_MAP, SYSTEM_INSTRUCTION, GEMINI_API_KEY
)
from .utils import retry_with_backoff

def calculate_relevance_score(item, pub_date, recent_topics=None):
    """Calculates a relevance score based on source tier, keywords, and topic diversity."""
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

    # 4. Time Decay
    age_hours = (datetime.now(timezone.utc) - pub_date).total_seconds() / 3600
    score -= (age_hours * 0.5)

    return score

@retry_with_backoff
async def fetch_single_feed(client, url, start_time, seen_links, recent_topics):
    """Fetches and parses a single RSS feed."""
    try:
        response = await client.get(url, timeout=10)
        if response.status_code != 200:
            return []
            
        feed = feedparser.parse(response.text)
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
            item["score"] = calculate_relevance_score(item, pub_date, recent_topics)
            items.append(item)
        return items
    except Exception:
        return []

async def fetch_news(seen_links=None, recent_topics=None):
    """Orchestrates parallel fetching of all RSS sources."""
    if seen_links is None: seen_links = []
    
    start_time = datetime.now(timezone.utc) - timedelta(days=2)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_single_feed(client, url, start_time, seen_links, recent_topics) for url in RSS_FEEDS]
        results = await asyncio.gather(*tasks)

    all_entries = [e for sublist in results for e in sublist]
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
        if art not in top_articles: top_articles.append(art)
            
    return top_articles[:8]

def validate_summary(text):
    if not text or len(text) < 60: return False, "Short/Empty"
    if re.search(r'(.)\1{4,}', text): return False, "Repetition"
    if "#" not in text: return False, "No Hashtags"
    return True, "Valid"

@retry_with_backoff
async def summarize_news(news_items, context):
    """Synthesizes news using Gemini API."""
    if not news_items: return None, None, None

    client = genai.Client(api_key=GEMINI_API_KEY)
    news_text = "\n".join([f"- {i+1}. {item['title']} ({item['source']})" for i, item in enumerate(news_items)])
    
    user_prompt = f"Day: {context['day']}, Session: {context['session']}\nNews:\n{news_text}"
    config = types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.7)

    response = await client.aio.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=user_prompt, config=config)
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

def get_temporal_context():
    """Calculates the temporal branding for the current run."""
    now = datetime.now(timezone.utc)
    day = now.strftime("%A")
    session = "Morning Intelligence" if now.hour < 12 else "Afternoon Deep Dive"
    return {"day": day, "session": session, "theme": "Technical Analysis"}
