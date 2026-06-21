import asyncio
import time
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from src.settings import settings
from src.utils import SafeLogger

def validate_text_limits(text: str) -> Optional[str]:
    """
    Validates text length against platform limits and returns a warning or info string if limits are exceeded.
    """
    bsky_single = settings.bluesky_limit - 10
    mastodon_single = settings.mastodon_limit - 15
    threads_single = settings.threads_limit - 10

    bsky_max = bsky_single * settings.max_thread_parts
    mastodon_max = mastodon_single * settings.max_thread_parts
    threads_max = threads_single * settings.max_thread_parts

    length = len(text)
    warnings = []

    # Check truncation limits
    if length > bsky_max:
        warnings.append(f"Bluesky max limit is {bsky_max} chars (with {settings.max_thread_parts} parts). Your draft is {length} chars and will be truncated.")
    if length > mastodon_max:
        warnings.append(f"Mastodon max limit is {mastodon_max} chars (with {settings.max_thread_parts} parts). Your draft is {length} chars and will be truncated.")
    if length > threads_max:
        warnings.append(f"Threads max limit is {threads_max} chars (with {settings.max_thread_parts} parts). Your draft is {length} chars and will be truncated.")

    if warnings:
        return "⚠️ **Warning**:\n" + "\n".join([f"- {w}" for w in warnings])

    # Check thread splitting
    thread_infos = []
    if length > bsky_single:
        thread_infos.append(f"Bluesky (limit {bsky_single})")
    if length > mastodon_single:
        thread_infos.append(f"Mastodon (limit {mastodon_single})")
    if length > threads_single:
        thread_infos.append(f"Threads (limit {threads_single})")

    if thread_infos:
        return f"ℹ️ *Note: This text is long ({length} chars) and will be split into a thread for: " + ", ".join(thread_infos) + ".*"

    return None

async def send_draft_for_approval(text: str, image_bytes: Optional[bytes] = None) -> Optional[str]:
    """
    Sends the generated post draft and image to Telegram for approval.
    Waits up to settings.telegram_timeout_minutes (default 5) for user callback or text reply.
    If the timeout expires, defaults to the current text and posts.
    Returns the approved/edited text, or None if rejected.
    """
    if not settings.telegram_bot_token or not settings.telegram_user_id:
        SafeLogger.info("Telegram: Missing bot token or user ID. Skipping Telegram approval stage.")
        return text

    # Do not request approval in dry-run mode
    if settings.is_dry_run:
        SafeLogger.info("Telegram: DRY_RUN enabled. Skipping approval message dispatch.")
        return text

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

        SafeLogger.info(f"Telegram: Waiting up to {settings.telegram_timeout_minutes} minutes for approval or edits...")
        while elapsed < timeout_seconds:
            try:
                updates = await bot.get_updates(offset=offset, timeout=1)
                for update in updates:
                    offset = update.update_id + 1
                    
                    # Handle callback query (Approve/Reject buttons)
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
                                return text
                            elif action == "reject":
                                SafeLogger.info("Telegram: User rejected draft.")
                                await query.answer("Draft rejected.")
                                await bot.send_message(chat_id=chat_id, text="❌ Rejected. Run aborted.")
                                return None

                    # Handle incoming text messages (direct edits or replies)
                    elif update.message and update.message.text:
                        msg = update.message
                        
                        # Validate sender matches settings.telegram_user_id
                        if str(msg.from_user.id) != str(chat_id):
                            continue

                        new_text = None
                        is_edit = False

                        # Check for /edit command or reply to the draft message
                        if msg.text.startswith("/edit "):
                            new_text = msg.text[6:].strip()
                            is_edit = True
                        elif msg.reply_to_message and msg.reply_to_message.message_id == sent_message.message_id:
                            new_text = msg.text.strip()
                            is_edit = True

                        if is_edit and new_text:
                            # Update the sent message with new draft text first (before committing)
                            if image_bytes:
                                await bot.edit_message_caption(
                                    chat_id=chat_id,
                                    message_id=sent_message.message_id,
                                    caption=f"📝 **DRAFT POST**:\n\n{new_text}",
                                    reply_markup=reply_markup,
                                    parse_mode="Markdown"
                                )
                            else:
                                await bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=sent_message.message_id,
                                    text=f"📝 **DRAFT POST**:\n\n{new_text}",
                                    reply_markup=reply_markup,
                                    parse_mode="Markdown"
                                )

                            # Only update the stored text if the Telegram API update succeeded
                            text = new_text
                            SafeLogger.info(f"Telegram: Draft updated by user to: {text}")

                            # Validate limits and generate feedback message
                            warning_msg = validate_text_limits(text)
                            if warning_msg:
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text=warning_msg,
                                    parse_mode="Markdown",
                                    reply_to_message_id=msg.message_id
                                )
                            else:
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text="📝 Draft updated!",
                                    reply_to_message_id=msg.message_id
                                )

            except Exception as e:
                # Silently catch network hiccups, but log warnings
                SafeLogger.warn(f"Telegram: Error checking updates: {e}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout occurred: auto-post
        SafeLogger.info("Telegram: Approval timeout expired. Automatically publishing draft.")
        await bot.send_message(chat_id=chat_id, text="🕒 Timeout expired. Automatically publishing draft.")
        return text

    except Exception as e:
        SafeLogger.error(f"Telegram approval engine encountered an error: {e}")
        return text  # Fallback to current text to maintain automated scheduling robustness

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
