import pytest
from unittest.mock import AsyncMock

from src import llm
from src.settings import Settings


@pytest.mark.asyncio
async def test_generate_text_uses_configured_provider(monkeypatch):
    monkeypatch.setattr(
        llm,
        "settings",
        Settings(
            llm_provider="codex",
            llm_fallback_providers="claude",
            telegram_channel_id="@channel",
        ),
    )
    codex = AsyncMock(return_value="codex result")
    claude = AsyncMock(return_value="claude result")
    monkeypatch.setattr(llm, "_generate_with_codex", codex)
    monkeypatch.setattr(llm, "_generate_with_claude", claude)

    assert await llm.generate_text("system", "prompt") == "codex result"
    codex.assert_awaited_once_with("system", "prompt")
    claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_text_falls_back_to_claude(monkeypatch):
    monkeypatch.setattr(
        llm,
        "settings",
        Settings(
            llm_provider="codex",
            llm_fallback_providers="claude",
            telegram_channel_id="@channel",
        ),
    )
    codex = AsyncMock(side_effect=RuntimeError("limit reached"))
    claude = AsyncMock(return_value="claude result")
    monkeypatch.setattr(llm, "_generate_with_codex", codex)
    monkeypatch.setattr(llm, "_generate_with_claude", claude)

    assert await llm.generate_text("system", "prompt") == "claude result"
    codex.assert_awaited_once()
    claude.assert_awaited_once()
