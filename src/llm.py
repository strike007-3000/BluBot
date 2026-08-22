"""Subscription-aware text generation for the curation pipeline."""

from __future__ import annotations

from typing import Iterable, Optional

from src.logger import SafeLogger
from src.settings import settings


class LLMProviderError(RuntimeError):
    """Raised when every configured model provider fails."""


def _provider_order() -> Iterable[str]:
    configured = [settings.llm_provider]
    configured.extend(settings.llm_fallback_providers.split(","))
    seen = set()
    for provider in configured:
        provider = provider.strip().lower()
        if provider and provider not in seen:
            seen.add(provider)
            yield provider


async def _generate_with_codex(system: str, prompt: str) -> str:
    try:
        from openai_codex import AsyncCodex, Sandbox
    except ImportError as exc:
        raise LLMProviderError("openai-codex is not installed") from exc

    full_prompt = f"{system}\n\nUSER INPUT:\n{prompt}"
    async with AsyncCodex() as codex:
        kwargs = {"sandbox": Sandbox.read_only}
        if settings.codex_model:
            kwargs["model"] = settings.codex_model
        thread = await codex.thread_start(**kwargs)
        result = await thread.run(full_prompt)
    text = (result.final_response or "").strip()
    if not text:
        raise LLMProviderError("Codex returned an empty response")
    return text


async def _generate_with_claude(system: str, prompt: str) -> str:
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    except ImportError as exc:
        raise LLMProviderError("claude-agent-sdk is not installed") from exc

    options_kwargs = {
        "system_prompt": system,
        "allowed_tools": [],
        "max_turns": 1,
        "setting_sources": [],
    }
    if settings.claude_model:
        options_kwargs["model"] = settings.claude_model

    final_text: Optional[str] = None
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(**options_kwargs),
    ):
        if isinstance(message, ResultMessage):
            final_text = message.result
    text = (final_text or "").strip()
    if not text:
        raise LLMProviderError("Claude returned an empty response")
    return text


async def _generate_with_gemini(system: str, prompt: str) -> str:
    if not settings.gemini_key:
        raise LLMProviderError("GEMINI_KEY is not configured")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_key)
    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.5,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise LLMProviderError("Gemini returned an empty response")
    return text


async def generate_text(system: str, prompt: str) -> str:
    """Generate text with ordered failover across configured providers."""
    providers = {
        "codex": _generate_with_codex,
        "claude": _generate_with_claude,
        "gemini": _generate_with_gemini,
    }
    errors = []
    for provider in _provider_order():
        generate = providers.get(provider)
        if not generate:
            errors.append(f"{provider}: unsupported provider")
            continue
        try:
            SafeLogger.info(f"LLM: Generating with {provider}.")
            return await generate(system, prompt)
        except Exception as exc:
            SafeLogger.warn(f"LLM: {provider} failed: {exc}")
            errors.append(f"{provider}: {exc}")
    raise LLMProviderError("All LLM providers failed: " + "; ".join(errors))
