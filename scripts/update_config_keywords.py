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
    api_key = settings.gemini_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        SafeLogger.error("GEMINI_KEY or GEMINI_API_KEY is not set in environment. Cannot update keywords.")
        sys.exit(1)
        
    genai_client = genai.Client(api_key=api_key)
    
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
        model_name = settings.gemini_model or "models/gemini-2.5-flash-lite"
        config_args = {
            "temperature": 0.3,
            "response_mime_type": "application/json"
        }
        
        # Apply structured output schema for Gemini models to ensure guaranteed JSON compliance
        if "gemini" in model_name.lower():
            try:
                from pydantic import BaseModel, Field
                class CurationKeywords(BaseModel):
                    momentum_products: list[str] = Field(description="List of top 10 momentum products")
                    high_signal_keywords: list[str] = Field(description="List of top 12 high-signal keywords")
                config_args["response_schema"] = CurationKeywords
            except ImportError:
                pass
                
        response = genai_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_args)
        )
        
        raw_text = response.text.strip()
        
        # Robust JSON extraction utility
        data = None
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            # Attempt to strip markdown fences
            cleaned = re.sub(r"^```(?:json)?\n", "", raw_text, flags=re.IGNORECASE)
            cleaned = re.sub(r"\n```$", "", cleaned)
            cleaned = cleaned.strip()
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                # Try finding the first '{' and last '}'
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    try:
                        data = json.loads(raw_text[start_idx:end_idx+1])
                    except json.JSONDecodeError:
                        pass
                        
        if not data:
            raise ValueError(f"Could not parse valid JSON from Gemini response. First 500 characters:\n{raw_text[:500]}")
            
        momentum_products = [item.lower() for item in data.get("momentum_products", [])]
        high_signal_keywords = [item.lower() for item in data.get("high_signal_keywords", [])]
        
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
