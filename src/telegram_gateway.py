import asyncio
import time
import httpx
from typing import Optional, Tuple, Any
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from src.settings import settings
from src.utils import SafeLogger
from src.models import MediaAsset, MediaSource

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

async def send_draft_for_approval(
    text: str,
    media: Optional[MediaAsset] = None,
    client: Optional[httpx.AsyncClient] = None,
    genai_client: Optional[Any] = None,
    topic: str = "General"
) -> Tuple[Optional[str], Optional[MediaAsset]]:
    """
    Sends the generated post draft and image to Telegram for approval.
    Waits up to settings.telegram_timeout_minutes (default 5) for user callback or text reply.
    If the timeout expires, defaults to the current text and media asset, and posts.
    Returns a Tuple: (approved_text, approved_media).
    Returns (None, None) if rejected.
    """
    if not settings.telegram_bot_token or not settings.telegram_user_id:
        SafeLogger.info("Telegram: Missing bot token or user ID. Skipping Telegram approval stage.")
        return text, media

    # Do not request approval in dry-run mode
    if settings.is_dry_run:
        SafeLogger.info("Telegram: DRY_RUN enabled. Skipping approval message dispatch.")
        return text, media

    try:
        bot = Bot(token=settings.telegram_bot_token)
        chat_id = settings.telegram_user_id

        # Create the inline keyboard buttons (with Option A options)
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data="approve"),
                InlineKeyboardButton("❌ Reject", callback_data="reject")
            ],
            [
                InlineKeyboardButton("🔄 Regenerate Text", callback_data="regenerate_text"),
                InlineKeyboardButton("🎨 Regenerate Image", callback_data="regenerate_image")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send text + image or just text
        sent_message = None
        image_bytes = media.image_bytes if media else None
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
        start_time = time.monotonic()

        waiting_for_feedback = False
        feedback_prompt_id = None

        SafeLogger.info(f"Telegram: Waiting up to {settings.telegram_timeout_minutes} minutes for approval or edits...")
        while (time.monotonic() - start_time) < timeout_seconds:
            try:
                updates = await bot.get_updates(offset=offset, timeout=1)
                for update in updates:
                    offset = update.update_id + 1
                    
                    # Handle callback query (Approve/Reject/Regen buttons)
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
                                return text, media
                            elif action == "reject":
                                SafeLogger.info("Telegram: User rejected draft.")
                                await query.answer("Draft rejected.")
                                await bot.send_message(chat_id=chat_id, text="❌ Rejected. Run aborted.")
                                return None, None
                            elif action == "regenerate_text":
                                SafeLogger.info("Telegram: User requested text regeneration.")
                                prompt_msg = await bot.send_message(
                                    chat_id=chat_id,
                                    text="📥 Reply to this message with a feedback hint for text regeneration (or reply `/skip` to regenerate with default settings):",
                                    reply_to_message_id=sent_message.message_id
                                )
                                feedback_prompt_id = prompt_msg.message_id
                                waiting_for_feedback = True
                                await query.answer("Provide feedback for text regeneration...")
                            elif action == "regenerate_image":
                                SafeLogger.info("Telegram: User requested image regeneration.")
                                if not genai_client or not client:
                                    await bot.send_message(chat_id=chat_id, text="⚠️ API clients are missing; image regeneration not possible.")
                                    await query.answer()
                                    continue
                                
                                status_msg = await bot.send_message(chat_id=chat_id, text=f"🎨 Regenerating image card using {settings.image_provider.upper()}...")
                                await query.answer("Regenerating image...")
                                
                                try:
                                    from src.curator import generate_visual_prompt, generate_ai_image, generate_image_alt_text
                                    from PIL import Image
                                    import io
                                    from src.utils import get_image_mime
                                    
                                    # 1. Generate new visual prompt
                                    visual_prompt = await generate_visual_prompt(genai_client, text, topic)
                                    
                                    # 2. Generate AI image
                                    new_image_data = await generate_ai_image(client, genai_client, visual_prompt)
                                    
                                    from src.curator import validate_image_bytes

                                    if new_image_data and validate_image_bytes(new_image_data):
                                        # 3. Generate image alt text
                                        alt_prompt = visual_prompt if visual_prompt else f"Minimalist tech illustration of {topic}"
                                        new_alt_text = await generate_image_alt_text(new_image_data, alt_prompt)
                                        
                                        # Get dimensions and mime
                                        mime_type = get_image_mime(new_image_data)
                                        width, height = None, None
                                        try:
                                            img = Image.open(io.BytesIO(new_image_data))
                                            width, height = img.size
                                        except Exception:
                                            pass
                                            
                                        # Construct new MediaAsset
                                        new_media = MediaAsset(
                                            source=MediaSource.GENERATED,
                                            image_bytes=new_image_data,
                                            public_url=None,
                                            mime_type=mime_type,
                                            width=width,
                                            height=height,
                                            alt_text=new_alt_text,
                                            attribution_url=media.attribution_url if media else None
                                        )
                                        
                                        # 4. Update preview message media
                                        original_has_media = media is not None and media.image_bytes is not None
                                        if sent_message and original_has_media:
                                            await bot.edit_message_media(
                                                chat_id=chat_id,
                                                message_id=sent_message.message_id,
                                                media=InputMediaPhoto(
                                                    media=new_image_data,
                                                    caption=f"📝 **DRAFT POST**:\n\n{text}",
                                                    parse_mode="Markdown"
                                                ),
                                                reply_markup=reply_markup
                                            )
                                            media = new_media
                                            SafeLogger.info("Telegram: Image regenerated successfully.")
                                            await bot.send_message(chat_id=chat_id, text="🎨 Image card regenerated successfully!", reply_to_message_id=status_msg.message_id)
                                        else:
                                            # If original was text-only, we can't edit media, so send new photo instead
                                            sent_photo = await bot.send_photo(
                                                chat_id=chat_id,
                                                photo=new_image_data,
                                                caption=f"📝 **DRAFT POST**:\n\n{text}",
                                                reply_markup=reply_markup,
                                                parse_mode="Markdown"
                                            )
                                            sent_message = sent_photo
                                            media = new_media
                                            SafeLogger.info("Telegram: Image generated and attached successfully.")
                                            await bot.send_message(chat_id=chat_id, text="🎨 Image card generated and attached successfully!", reply_to_message_id=status_msg.message_id)
                                    else:
                                        await bot.send_message(chat_id=chat_id, text="Image regeneration failed. The previous image has been preserved and the draft can still be approved.", reply_to_message_id=status_msg.message_id)
                                except Exception as e:
                                    SafeLogger.error(f"Telegram: Image regeneration failed: {e}")
                                    await bot.send_message(chat_id=chat_id, text="Image regeneration failed. The previous image has been preserved and the draft can still be approved.", reply_to_message_id=status_msg.message_id)

                    # Handle incoming text messages (direct edits, replies, or feedback)
                    elif update.message and update.message.text:
                        msg = update.message
                        
                        # Validate sender matches settings.telegram_user_id
                        if str(msg.from_user.id) != str(chat_id):
                            continue

                        text_val = msg.text.strip()
                        if text_val.startswith("/topic ") or text_val.startswith("/curate "):
                            from src.config import PENDING_TOPIC_FILE_PATH
                            import json
                            topic_cmd = "/topic " if text_val.startswith("/topic ") else "/curate "
                            topic_str = text_val.replace(topic_cmd, "", 1).strip()
                            if topic_str:
                                try:
                                    with open(PENDING_TOPIC_FILE_PATH, "w", encoding="utf-8") as f:
                                        json.dump({"topic": topic_str, "timestamp": time.time()}, f)
                                    SafeLogger.info(f"Telegram Loop: Persisted topic '{topic_str}' to pending_topic.json")
                                    await bot.send_message(chat_id=chat_id, text=f"📥 Topic request recorded for next run: *{topic_str}*.", reply_to_message_id=msg.message_id)
                                except Exception as persist_err:
                                    SafeLogger.error(f"Telegram Loop: Failed to persist topic: {persist_err}")
                            continue

                        # Scenario A: User is replying to the text feedback prompt
                        if waiting_for_feedback and msg.reply_to_message and msg.reply_to_message.message_id == feedback_prompt_id:
                            waiting_for_feedback = False
                            feedback = msg.text.strip()
                            if feedback.lower() == '/skip':
                                feedback = "Refine the wording and present the insight from a slightly different perspective."

                            status_msg = await bot.send_message(chat_id=chat_id, text="🔄 Regenerating text draft...", reply_to_message_id=msg.message_id)
                            
                            try:
                                from src.config import CURATOR_SYSTEM_INSTRUCTION
                                from google.genai import types
                                from src.curator import strip_markdown
                                
                                rewrite_prompt = (
                                    f"You are a professional editor. Please rewrite the following technical post draft based on the user's feedback.\n\n"
                                    f"Current Draft:\n\"\"\"\n{text}\n\"\"\"\n\n"
                                    f"User Feedback: {feedback}\n\n"
                                    f"Follow all system instructions for style, tone, and length constraints."
                                )
                                
                                response = await genai_client.aio.models.generate_content(
                                    model=settings.gemini_model,
                                    contents=rewrite_prompt,
                                    config=types.GenerateContentConfig(
                                        system_instruction=CURATOR_SYSTEM_INSTRUCTION,
                                        temperature=0.7
                                    )
                                )
                                new_text = strip_markdown(response.text.strip())

                                # Update the sent message preview
                                original_has_media = media is not None and media.image_bytes is not None
                                if original_has_media:
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
                                
                                text = new_text
                                SafeLogger.info(f"Telegram: Text regenerated to: {text}")
                                await bot.send_message(chat_id=chat_id, text="📝 Draft text updated successfully!", reply_to_message_id=msg.message_id)

                                # Validate limits and generate feedback message
                                warning_msg = validate_text_limits(text)
                                if warning_msg:
                                    await bot.send_message(
                                        chat_id=chat_id,
                                        text=warning_msg,
                                        parse_mode="Markdown"
                                    )
                            except Exception as e:
                                SafeLogger.error(f"Telegram: Text regeneration failed: {e}")
                                await bot.send_message(chat_id=chat_id, text=f"❌ Text regeneration failed: {e}", reply_to_message_id=msg.message_id)

                        # Scenario B: Manual editing via direct reply or command
                        else:
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
                                original_has_media = media is not None and media.image_bytes is not None
                                if original_has_media:
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

        # Timeout occurred: auto-post
        SafeLogger.info("Telegram: Approval timeout expired. Automatically publishing draft.")
        await bot.send_message(chat_id=chat_id, text="🕒 Timeout expired. Automatically publishing draft.")
        return text, media

    except Exception as e:
        SafeLogger.error(f"Telegram approval engine encountered an error: {e}")
        return text, media  # Fallback to current text and media to maintain robustness_bytes, image_alt_text  # Fallback to current text and images to maintain robustness

async def check_for_telegram_topic() -> Optional[str]:
    """
    Checks if there's a recent /topic or /curate command sent by the authorized user,
    either from pending_topic.json or directly from Telegram updates.
    Returns the topic string if found and valid (under 15 minutes old), else None.
    """
    from src.config import PENDING_TOPIC_FILE_PATH
    import os
    import json
    import time
    
    # 1. Check pending_topic.json first
    topic_to_use = None
    if os.path.exists(PENDING_TOPIC_FILE_PATH):
        try:
            with open(PENDING_TOPIC_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            topic_to_use = data.get("topic")
        except Exception as e:
            SafeLogger.warn(f"Telegram: Error reading pending topic file: {e}")
        finally:
            try:
                os.remove(PENDING_TOPIC_FILE_PATH)
            except Exception:
                pass

    if topic_to_use:
        SafeLogger.info(f'Received topic: "{topic_to_use}"')
        SafeLogger.info("Using topic override...")
        SafeLogger.info("Topic override cleared.")
        # Notify user on Telegram
        if settings.telegram_bot_token and settings.telegram_user_id:
            try:
                bot = Bot(token=settings.telegram_bot_token)
                await bot.send_message(chat_id=settings.telegram_user_id, text=f"📥 Using pending topic override: *{topic_to_use}*.")
            except Exception:
                pass
        return topic_to_use

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
                    topic = None
                    if text.startswith("/topic "):
                        topic = text.replace("/topic ", "", 1).strip()
                    elif text.startswith("/curate "):
                        topic = text.replace("/curate ", "", 1).strip()
                    
                    if topic:
                        SafeLogger.info(f'Received topic: "{topic}"')
                        SafeLogger.info("Using topic override...")
                        SafeLogger.info("Topic override cleared.")
                        
                        # Acknowledge this update and all previous ones to consume it
                        try:
                            await bot.get_updates(offset=update.update_id + 1, limit=1)
                        except Exception as e:
                            SafeLogger.warn(f"Telegram: Failed to acknowledge updates: {e}")
                        
                        await bot.send_message(chat_id=chat_id, text=f"📥 Received topic request: *{topic}*. Curating now...")
                        return topic
        return None
    except Exception as e:
        SafeLogger.warn(f"Telegram: Error checking for topic intercept: {e}")
        return None
