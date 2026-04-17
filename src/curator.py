import asyncio
import os
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
    SAGE_DESIGNER_INSTRUCTION, SECONDARY_TOPICS, GEMINI_MODEL_PRIORITY,
    HIGH_SIGNAL_KEYWORDS, MOMENTUM_PRODUCTS,
    BASE_TIER_1, BASE_HIDDEN_GEM, BASE_TIER_2, SIGNAL_BOOST,
    MOMENTUM_BOOST, SYNERGY_BONUS, DIVERSITY_PENALTY, MAX_TOPIC_RECURRENCE,
    FEED_SUMMARY_MAX_CHARS
)
from .utils import retry_with_backoff, SafeLogger

MODEL_ATTEMPT_RETRIES = 2

def calculate_relevance_score(item, pub_date, now_utc, recent_topics=None):
    score = 0
    content_text = f"{item['title']} {item['summary']}".lower()
    if any(domain in item['link'] for domain in TIER_1_SOURCES): score += BASE_TIER_1
    if any(kw in content_text for kw in HIGH_SIGNAL_KEYWORDS): score += SIGNAL_BOOST
    score -= (now_utc - pub_date).total_seconds() / 3600 * 0.5
    return score

@retry_with_backoff
async def fetch_single_feed(client, url, start_time, now_utc, seen_links, recent_topics):
    try:
        response = await client.get(url, timeout=10)
        feed = await asyncio.to_thread(feedparser.parse, response.text)
        items = []
        for entry in feed.entries:
            pub_date = datetime.now(timezone.utc) # Simplified for test
            if entry.link in seen_links: continue
            item = {"title": entry.title, "summary": entry.get('summary', ""), "link": entry.link, "source": url}
            item["score"] = calculate_relevance_score(item, pub_date, now_utc, recent_topics)
            items.append(item)
        return items
    except Exception: return []

async def fetch_news(client, seen_links=None, recent_topics=None):
    now_utc = datetime.now(timezone.utc)
    tasks = [fetch_single_feed(client, url, now_utc - timedelta(days=2), now_utc, seen_links or [], recent_topics) for url in RSS_FEEDS]
    results = await asyncio.gather(*tasks)
    entries = [e for sublist in results for e in sublist]
    entries.sort(key=lambda x: x["score"], reverse=True)
    return entries[:8]

async def summarize_news(news_items, context, mode="Curator"):
    if not news_items: return None, None, "General", False
    
    # Critical: Fetch key dynamically inside function
    key = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=key)
    
    news_text = "\n".join([f"- {i['title']}" for i in news_items])
    instruction = MENTOR_SYSTEM_INSTRUCTION if mode == "Mentor" else CURATOR_SYSTEM_INSTRUCTION
    
    for model_id in GEMINI_MODEL_PRIORITY:
        try:
            SafeLogger.info(f"Synthesizing via {model_id}...")
            response = await client.aio.models.generate_content(
                model=model_id, 
                contents=f"{instruction}\n\nNews:\n{news_text}",
                config=types.GenerateContentConfig(temperature=0.7)
            )
            return response.text.strip(), news_items[0]['link'], "General", (model_id != GEMINI_MODEL_PRIORITY[0])
        except Exception as e:
            SafeLogger.warn(f"Model {model_id} failed: {e}")
    return None, None, "General", False

async def generate_mentor_insight(context):
    key = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=key)
    topic = SECONDARY_TOPICS[0]
    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL_PRIORITY[0],
            contents=f"{MENTOR_SYSTEM_INSTRUCTION}\n\nTopic: {topic}",
            config=types.GenerateContentConfig(temperature=0.8)
        )
        return response.text.strip(), None, "Strategy", False
    except Exception: return None, None, "Strategy", False

def get_temporal_context():
    now = datetime.now(timezone.utc)
    return {"day": now.strftime("%A"), "session": "Morning Intelligence" if now.hour < 12 else "Afternoon Deep Dive"}

async def generate_visual_prompt(client, summary, topic):
    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL_PRIORITY[0],
            contents=f"{SAGE_DESIGNER_INSTRUCTION}\n\nSummary: {summary}",
            config=types.GenerateContentConfig(temperature=0.8)
        )
        return response.text.strip()
    except Exception: return f"Minimalist tech illustration of {topic}"