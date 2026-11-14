"""Gemini call helper for the LinkedIn weekly draft feature."""
from typing import Optional

from google.genai import types

from src.config import GEMINI_MODEL_PRIORITY, normalize_gemini_model_id
from src.curator import supports_thinking
from src.logger import SafeLogger
from src.settings import settings


async def gemini_generate(genai_client, prompt: str, system_instruction: str, json_mode: bool = False) -> Optional[str]:
    """Rotate GEMINI_MODEL_PRIORITY; return stripped text, or None if every model fails or returns empty."""
    for model_id in GEMINI_MODEL_PRIORITY:
        try:
            args = {"system_instruction": system_instruction}
            if normalize_gemini_model_id(model_id) not in ("gemini-3.7-flash", "gemini-3.6-flash"):
                args["temperature"] = 0.7
            if json_mode:
                args["response_mime_type"] = "application/json"
            if supports_thinking(model_id):
                args["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=settings.thinking_budget if settings.thinking_budget is not None else 1024
                )
            response = await genai_client.aio.models.generate_content(
                model=model_id, contents=prompt, config=types.GenerateContentConfig(**args)
            )
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as e:
            SafeLogger.warn(f"LinkedIn Gemini call failed on {model_id} ({e}). Rotating if possible...")
    return None
