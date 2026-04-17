import asyncio
import time
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from src.settings import settings
from src.utils import SafeLogger

async def send_draft_for_approval(text: str, image_bytes: Optional[bytes] = None) -> bool:
    """
    Sends the generated post draft and image to Telegram for approval.
    Waits up to settings.telegram_timeout_minutes (default 5) for user callback.
    If the timeout expires, defaults to True (approve) and posts.
    """
    if not settings.telegram_bot_token or not settings.telegram_user_id:
        SafeLogger.info("Telegram: Missing bot token or user ID. Skipping Telegram approval stage.")
        return True

    # Do not request approval in dry-run mode
    if settings.is_dry_run:
        SafeLogger.info("Telegram: DRY_RUN enabled. Skipping approval message dispatch.")
        return True

    try:
        bot = Bot(token=settings.telegram_bot_token)
        chat_id = settings.telegram_user_id

        # Create the inline keyboard buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data="approve"),
                InlineKeyboardButton("❌ Reject", callback_data="reject")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send text + image or just text
        sent_message = None
        if image_bytes:
            SafeLogger.info("Telegram: Sending draft and image for approval...")
            sent_message = await bot.send_photo(
                chat_id=chat_id,
                photo=image_bytes,
                caption=f"📝 **DRAFT POST**:\n\n{text}",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            SafeLogger.info("Telegram: Sending draft for approval...")
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=f"📝 **DRAFT POST**:\n\n{text}",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

        # Clear existing updates to avoid acting on old clicks
        updates = await bot.get_updates(limit=100)
        offset = updates[-1].update_id + 1 if updates else None

        # Start waiting/polling loop
        timeout_seconds = settings.telegram_timeout_minutes * 60
        poll_interval = 2
        elapsed = 0

        SafeLogger.info(f"Telegram: Waiting up to {settings.telegram_timeout_minutes} minutes for approval...")
        while elapsed < timeout_seconds:
            try:
                updates = await bot.get_updates(offset=offset, timeout=1)
                for update in updates:
                    offset = update.update_id + 1
                    if update.callback_query:
                        query = update.callback_query
                        
                        # Validate sender matches settings.telegram_user_id
                        if str(query.from_user.id) != str(chat_id):
                            SafeLogger.warn(f"Telegram: Unauthorized interaction from user ID: {query.from_user.id}")
                            continue

                        # Check if callback is on our sent message
                        if sent_message and query.message and query.message.message_id == sent_message.message_id:
                            action = query.data
                            if action == "approve":
                                SafeLogger.info("Telegram: User approved draft.")
                                await query.answer("Draft approved! Publishing...")
                                await bot.send_message(chat_id=chat_id, text="🚀 Approved. Posting to platforms...")
                                return True
                            elif action == "reject":
                                SafeLogger.info("Telegram: User rejected draft.")
                                await query.answer("Draft rejected.")
                                await bot.send_message(chat_id=chat_id, text="❌ Rejected. Run aborted.")
                                return False
            except Exception as e:
                # Silently catch network hiccups, but log warnings
                SafeLogger.warn(f"Telegram: Error checking updates: {e}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout occurred: auto-post
        SafeLogger.info("Telegram: Approval timeout expired. Automatically publishing draft.")
        await bot.send_message(chat_id=chat_id, text="🕒 Timeout expired. Automatically publishing draft.")
        return True

    except Exception as e:
        SafeLogger.error(f"Telegram approval engine encountered an error: {e}")
        return True  # Fallback to True to maintain automated scheduling robustness

async def check_for_telegram_topic() -> Optional[str]:
    """
    Checks if there's a recent /topic or /curate command sent by the authorized user.
    Returns the topic string if found, else None.
    """
    if not settings.telegram_bot_token or not settings.telegram_user_id:
        return None

    try:
        bot = Bot(token=settings.telegram_bot_token)
        chat_id = settings.telegram_user_id
        
        updates = await bot.get_updates(limit=50)
        if not updates:
            return None

        # Look for the latest message from the authorized user in the last 15 minutes
        now = time.time()
        for update in reversed(updates):
            if update.message and str(update.message.from_user.id) == str(chat_id):
                msg = update.message
                # Verify it was sent in the last 15 minutes
                if msg.date and (now - msg.date.timestamp()) < 900:
                    text = msg.text or ""
                    if text.startswith("/topic "):
                        topic = text.replace("/topic ", "", 1).strip()
                        if topic:
                            SafeLogger.info(f"Telegram: Received on-demand topic intercept: '{topic}'")
                            await bot.send_message(chat_id=chat_id, text=f"📥 Received topic request: *{topic}*. Curating now...")
                            return topic
                    elif text.startswith("/curate "):
                        topic = text.replace("/curate ", "", 1).strip()
                        if topic:
                            SafeLogger.info(f"Telegram: Received on-demand topic intercept: '{topic}'")
                            await bot.send_message(chat_id=chat_id, text=f"📥 Received topic request: *{topic}*. Curating now...")
                            return topic
        return None
    except Exception as e:
        SafeLogger.warn(f"Telegram: Error checking for topic intercept: {e}")
        return None
