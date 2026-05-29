import sys
import os
import re
import httpx
import asyncio
import feedparser
import json
from google import genai
from google.genai import types

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.settings import settings
from src.config import RSS_FEEDS
from src.utils import SafeLogger

async def fetch_feed_headlines(client, url):
    """Fetches first 5 headlines from a single RSS feed."""
    try:
        response = await client.get(url, timeout=10)
        feed = feedparser.parse(response.content)
        headlines = []
        for entry in feed.entries[:5]:
            title = getattr(entry, 'title', '')
            summary = getattr(entry, 'summary', '')
            if title:
                headlines.append(f"{title} - {summary[:100]}")
        return headlines
    except Exception as e:
        SafeLogger.warn(f"Failed to fetch headlines for {url}: {e}")
        return []

async def main():
    SafeLogger.info("Weekly Curation Config Update: Starting feed headlines query...")
    
    # 1. Fetch headlines in parallel
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        tasks = [fetch_feed_headlines(client, url) for url in RSS_FEEDS]
        results = await asyncio.gather(*tasks)
    
    all_headlines = [headline for sublist in results for headline in sublist]
    headlines_text = "\n".join(all_headlines[:150])  # Cap to prevent too much context
    
    SafeLogger.info(f"Collected {len(all_headlines)} headlines. Invoking Gemini model for trending insights...")

    # 2. Call Gemini
    genai_client = genai.Client(api_key=settings.gemini_key)
    
    prompt = f"""
Analyze the following recent news headlines to extract the top 10 most trending AI products/developer releases (momentum products) and top 12 high-signal developer event/technical keywords.

Include both anticipated systems (e.g. gpt-5, claude 4, llama 4, agentic siri, gemma 4) and active tech event concepts (e.g. google i/o, wwdc, apple intelligence, keynote).

Recent Headlines:
{headlines_text}

Respond STRICTLY with a JSON object in this format (no markdown, no backticks, just raw JSON):
{{
  "momentum_products": ["gpt-5", "claude 4", "llama 4", "gemini 3", "gemma 4", "sora", "devin", "grok 4", "mistral 4", "strawberry"],
  "high_signal_keywords": ["sota", "benchmark", "breakthrough", "agentic", "autonomous", "world model", "test-time compute", "moe", "reasoning", "open weights", "open source", "scaling law"]
}}
"""
    try:
        response = genai_client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json"
            )
        )
        
        raw_text = response.text.strip()
        data = json.loads(raw_text)
        
        momentum_products = data.get("momentum_products", [])
        high_signal_keywords = data.get("high_signal_keywords", [])
        
        if not momentum_products or not high_signal_keywords:
            SafeLogger.error("Empty response or missing fields from Gemini.")
            sys.exit(1)

        # 3. Update src/config.py
        config_path = os.path.join(os.path.dirname(__file__), "..", "src", "config.py")
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex replacement for HIGH_SIGNAL_KEYWORDS
        content = re.sub(
            r"HIGH_SIGNAL_KEYWORDS = \[[^\]]*\]",
            f"HIGH_SIGNAL_KEYWORDS = {json.dumps(high_signal_keywords, indent=4)}",
            content,
            flags=re.DOTALL
        )

        # Regex replacement for MOMENTUM_PRODUCTS
        content = re.sub(
            r"MOMENTUM_PRODUCTS = \[[^\]]*\]",
            f"MOMENTUM_PRODUCTS = {json.dumps(momentum_products, indent=4)}",
            content,
            flags=re.DOTALL
        )

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

        SafeLogger.info("Weekly Curation Config Update: Successfully updated src/config.py!")
        SafeLogger.info(f"New Momentum Products: {momentum_products}")
        SafeLogger.info(f"New High Signal Keywords: {high_signal_keywords}")
        
    except Exception as e:
        SafeLogger.error(f"Failed to update curation config: {e}")
        raise e

if __name__ == "__main__":
    asyncio.run(main())
