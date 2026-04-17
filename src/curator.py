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
from .config import (
    RSS_FEEDS, TIER_1_SOURCES, TIER_2_SOURCES, HIDDEN_GEM_SOURCES, 
    TOPIC_MAP, CURATOR_SYSTEM_INSTRUCTION, MENTOR_SYSTEM_INSTRUCTION,
    SAGE_DESIGNER_INSTRUCTION, SECONDARY_TOPICS, GEMINI_MODEL_PRIORITY,
    HIGH_SIGNAL_KEYWORDS, MOMENTUM_PRODUCTS,
    BASE_TIER_1, BASE_HIDDEN_GEM, BASE_TIER_2, SIGNAL_BOOST,
    MOMENTUM_BOOST, SYNERGY_BONUS, DIVERSITY_PENALTY, MAX_TOPIC_RECURRENCE,
    FEED_SUMMARY_MAX_CHARS, NVIDIA_MODEL_ID, NVIDIA_INVOKE_URL
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
            
    # 5. Time Decay
    age_hours = (now_utc - pub_date).total_seconds() / 3600
    decay = age_hours * 0.5
    score -= decay
    
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
        feed = await asyncio.to_thread(feedparser.parse, response.text)
        items = []
        for entry in feed.entries:
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc)
            else:
                pub_date = now_utc
            
            if entry.link in seen_links: continue
                
            clean_summary = BeautifulSoup(getattr(entry, 'summary', getattr(entry, 'description', "")), "html.parser").get_text()
            item = {
                "title": entry.title,
                "summary": clean_summary[:FEED_SUMMARY_MAX_CHARS],
                "link": entry.link,
                "source": getattr(feed.feed, 'title', url)
            }
            item["score"] = calculate_relevance_score(item, pub_date, now_utc, recent_topics)
            items.append(item)
        return items
    except Exception: return []

async def fetch_news(client, seen_links=None, recent_topics=None):
    """Orchestrates parallel fetching with Consensus Synergy and Greedy Diversity."""
    now_utc = datetime.now(timezone.utc)
    tasks = [fetch_single_feed(client, url, now_utc - timedelta(days=2), now_utc, seen_links or [], recent_topics) for url in RSS_FEEDS]
    results = await asyncio.gather(*tasks)
    
    all_raw_entries = [e for sublist in results for e in sublist]
    
    unique_by_link = {}
    for e in all_raw_entries:
        if e['link'] not in unique_by_link: unique_by_link[e['link']] = e
        else:
            unique_by_link[e['link']]['score'] += SYNERGY_BONUS
            
    entries = list(unique_by_link.values())
    entries.sort(key=lambda x: x["score"], reverse=True)
    return entries[:8]

def strip_markdown(text):
    if not text: return text
    return re.sub(r'(\*\*|__|\*)', '', text).strip()

async def summarize_news(news_items, context, mode="Curator"):
    """Synthesizes news with full Failover Loop and adaptation logic."""
    if not news_items: return None, None, "General", False
    
    # Dynamic identity fetch (v3.5.12)
    key = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=key)
    
    news_text = "\n".join([f"- {i+1}. {item['title']} ({item['source']})" for i, item in enumerate(news_items)])
    instruction = MENTOR_SYSTEM_INSTRUCTION if mode == "Mentor" else CURATOR_SYSTEM_INSTRUCTION
    user_prompt = f"Day: {context['day']}, Session: {context['session']}, Mode: {mode}\nNews Data:\n{news_text}"
    
    for idx, model_id in enumerate(GEMINI_MODEL_PRIORITY):
        for attempt in range(1, MODEL_ATTEMPT_RETRIES + 1):
            try:
                SafeLogger.info(f"Synthesizing via {model_id} (Attempt {attempt})...")
                
                # Expert Review Fix: Gemma vs Gemini Adaptation
                if "gemma" in model_id.lower():
                    contents = f"{instruction}\n\nUSER INPUT:\n{user_prompt}"
                    response = await client.aio.models.generate_content(
                        model=model_id, contents=contents,
                        config=types.GenerateContentConfig(temperature=0.7)
                    )
                else:
                    response = await client.aio.models.generate_content(
                        model=model_id, contents=user_prompt,
                        config=types.GenerateContentConfig(system_instruction=instruction, temperature=0.7)
                    )
                
                raw_text = response.text.strip()
                topic = "General"
                summary = raw_text
                
                if "TOPIC:" in raw_text and "BODY:" in raw_text:
                    parts = raw_text.split("BODY:", 1)
                    topic = parts[0].replace("TOPIC:", "").strip()
                    summary = parts[1].strip()
                
                if len(summary) > 60:
                    return strip_markdown(summary), news_items[0]['link'], topic, (idx > 0)
                    
            except Exception as e:
                SafeLogger.warn(f"Model {model_id} attempt {attempt} failed: {e}")
                if attempt == MODEL_ATTEMPT_RETRIES and idx == len(GEMINI_MODEL_PRIORITY) - 1:
                    raise e
    return None, None, "General", False

async def generate_mentor_insight(context):
    key = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=key)
    topic = SECONDARY_TOPICS[0]
    
    for model_id in GEMINI_MODEL_PRIORITY:
        try:
            SafeLogger.info(f"Generating Mentor Insight via {model_id}...")
            response = await client.aio.models.generate_content(
                model=model_id, 
                contents=f"Topic: {topic}",
                config=types.GenerateContentConfig(system_instruction=MENTOR_SYSTEM_INSTRUCTION, temperature=0.8)
            )
            summary = response.text.strip()
            if "BODY:" in summary:
                summary = summary.split("BODY:", 1)[1].strip()
            return strip_markdown(summary), None, "Strategy", (model_id != GEMINI_MODEL_PRIORITY[0])
        except Exception as e:
            SafeLogger.warn(f"Mentor Fallback failed on {model_id}: {e}")
    return None, None, "Strategy", False

def get_temporal_context():
    now = datetime.now(timezone.utc)
    return {"day": now.strftime("%A"), "session": "Morning Intelligence" if now.hour < 12 else "Deep Dive"}

async def generate_visual_prompt(client, summary, topic):
    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL_PRIORITY[0],
            contents=f"Topic: {topic}\nSummary: {summary}",
            config=types.GenerateContentConfig(system_instruction=SAGE_DESIGNER_INSTRUCTION, temperature=0.8)
        )
        return response.text.strip()
    except Exception: return f"Minimalist tech illustration of {topic}"

@retry_with_backoff
async def generate_nvidia_image(client, prompt):
    """Calls NVIDIA NIM for SD3-Medium image generation."""
    nv_key = os.getenv("NVIDIA_KEY")
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
        response = await client.post(NVIDIA_INVOKE_URL, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        result = response.json()
        
        # NVIDIA NIM usually returns images as base64 in the 'image' field
        if "image" in result:
            return base64.b64decode(result["image"])
    except Exception as e:
        SafeLogger.warn(f"NVIDIA NIM failed: {e}")
    return None