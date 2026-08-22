from unittest.mock import AsyncMock, MagicMock

import pytest

from src.broadcaster import post_to_telegram_channel
from src.models import MediaAsset, MediaSource
from src.settings import Settings


@pytest.mark.asyncio
async def test_post_to_telegram_channel_sends_text_with_source(monkeypatch, mocker):
    monkeypatch.setattr(
        "src.broadcaster.settings",
        Settings(telegram_bot_token="123:abc", telegram_channel_id="@radar"),
    )
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    mocker.patch("telegram.Bot", return_value=bot)

    result = await post_to_telegram_channel(
        "Новый релиз Codex",
        link="https://example.com/release",
    )

    assert result is True
    bot.send_message.assert_awaited_once_with(
        chat_id="@radar",
        text="Новый релиз Codex\n\nИсточник: https://example.com/release",
        disable_web_page_preview=False,
    )


@pytest.mark.asyncio
async def test_post_to_telegram_channel_sends_short_photo_caption(monkeypatch, mocker):
    monkeypatch.setattr(
        "src.broadcaster.settings",
        Settings(telegram_bot_token="123:abc", telegram_channel_id="-100123"),
    )
    bot = MagicMock()
    bot.send_photo = AsyncMock(return_value=MagicMock(message_id=2))
    mocker.patch("telegram.Bot", return_value=bot)
    media = MediaAsset(source=MediaSource.OPENGRAPH, image_bytes=b"image")

    result = await post_to_telegram_channel("Короткий пост", media=media)

    assert result is True
    bot.send_photo.assert_awaited_once_with(
        chat_id="-100123",
        photo=b"image",
        caption="Короткий пост",
    )


@pytest.mark.asyncio
async def test_post_to_telegram_channel_requires_configuration(monkeypatch):
    monkeypatch.setattr("src.broadcaster.settings", Settings())

    assert await post_to_telegram_channel("Черновик") is False
