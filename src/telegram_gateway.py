import asyncio
import time
import httpx
import re
import json
from datetime import datetime, timezone
from typing import Optional, Tuple, Any, List
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

def _build_telegram_markup(current_tab: str = "bluesky", view_mode: str = "tabs", remix_state: str = "idle") -> InlineKeyboardMarkup:
    """Constructs inline keyboard with platform tabs, view toggles, approval, and remix buttons."""
    if remix_state == "in_flight":
        # Disable action buttons while remix request is in flight
        return InlineKeyboardMarkup([[InlineKeyboardButton("⏳ AI Remix In Progress...", callback_data="noop")]])

    # Row 1: Platform tabs (if in tabs view)
    tab_row = [
        InlineKeyboardButton(f"{'👉 ' if current_tab == 'bluesky' else ''}🔵 Bluesky", callback_data="tab:bsky"),
        InlineKeyboardButton(f"{'👉 ' if current_tab == 'threads' else ''}🧵 Threads", callback_data="tab:threads"),
        InlineKeyboardButton(f"{'👉 ' if current_tab == 'mastodon' else ''}🐘 Mastodon", callback_data="tab:mastodon"),
    ]

    # Row 2: View toggle & Remix
    control_row = []
    if view_mode == "tabs":
        control_row.append(InlineKeyboardButton("📋 Show All", callback_data="view:all"))
        control_row.append(InlineKeyboardButton(f"✨ Remix {current_tab.title()}", callback_data=f"remix:{current_tab}"))
    else:
        control_row.append(InlineKeyboardButton("📑 Show Tabs", callback_data="view:tabs"))
        control_row.append(InlineKeyboardButton("✨ Remix All", callback_data="remix:all"))

    # Row 3: Approval & Rejection
    action_row = [
        InlineKeyboardButton("✅ Approve", callback_data="approve"),
        InlineKeyboardButton("❌ Reject", callback_data="reject"),
    ]

    # Row 4: Image Regen
    regen_row = [
        InlineKeyboardButton("🎨 Regenerate Image", callback_data="regenerate_image")
    ]

    return InlineKeyboardMarkup([tab_row, control_row, action_row, regen_row])

def _format_preview_text(drafts: Any, current_tab: str = "bluesky", view_mode: str = "tabs") -> str:
    """Formats preview text ensuring strict compliance with Telegram caption / text budgets."""
    from src.models import PlatformDrafts
    if isinstance(drafts, str):
        drafts = PlatformDrafts.from_single(drafts)

    if view_mode == "tabs":
        tab_content = drafts.get(current_tab)
        limit = 290 if current_tab == "bluesky" else (490 if current_tab == "threads" else 485)
        title_map = {"bluesky": "🔵 Bluesky View", "threads": "🧵 Threads View", "mastodon": "🐘 Mastodon View"}
        title = title_map.get(current_tab, "Draft View")
        return f"📝 **DRAFT POST ({title})**:\n\n{tab_content}\n\n`[{len(tab_content)}/{limit} chars]`"
    else:
        return (
            "📝 **MULTI-PLATFORM DRAFTS**:\n\n"
            f"🔵 **Bluesky** ({len(drafts.bluesky)}/290):\n{drafts.bluesky}\n\n"
            f"🧵 **Threads** ({len(drafts.threads)}/490):\n{drafts.threads}\n\n"
            f"🐘 **Mastodon** ({len(drafts.mastodon)}/485):\n{drafts.mastodon}"
        )

def _get_caption_payload(drafts: Any, current_tab: str, view_mode: str) -> Tuple[str, Optional[str]]:
    """
    Returns (primary_caption, optional_followup_text) for media messages.
    If view_mode is 'all' and full preview exceeds 950 characters (Telegram caption limit is 1024),
    splits into a concise primary caption and a full markdown follow-up message.
    """
    preview_text = _format_preview_text(drafts, current_tab=current_tab, view_mode=view_mode)
    if view_mode == "all" and len(preview_text) > 950:
        concise_caption = "📝 **MULTI-PLATFORM DRAFTS**:\n(See full breakdown below)\n\n" + f"🔵 Bluesky: {drafts.bluesky[:200]}..."
        return concise_caption, preview_text
    return preview_text, None

async def _render_and_update_preview(
    bot: Bot,
    chat_id: Any,
    sent_message: Any,
    drafts: Any,
    current_tab: str,
    view_mode: str,
    reply_markup: InlineKeyboardMarkup,
    image_bytes: Optional[bytes]
) -> bool:
    """
    Renders preview text and updates the authoritative Telegram preview message.
    Protects against Telegram's 1024-character caption limit when media + all-in-one mode is active
    by posting a concise caption on the photo and the full breakdown in a follow-up message.
    Returns True if update succeeded, False otherwise.
    """
    try:
        if image_bytes:
            caption, followup = _get_caption_payload(drafts, current_tab=current_tab, view_mode=view_mode)
            await bot.edit_message_caption(
                chat_id=chat_id, message_id=sent_message.message_id,
                caption=caption, reply_markup=reply_markup, parse_mode="Markdown"
            )
            if followup:
                try:
                    await bot.send_message(chat_id=chat_id, text=followup, parse_mode="Markdown")
                except Exception as followup_err:
                    SafeLogger.warn(f"Failed to send all-in-one breakdown follow-up message: {followup_err}")
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="⚠️ Full breakdown follow-up message could not be sent. Authoritative draft updated in photo caption; switch tabs to view full platform variants."
                        )
                    except Exception:
                        pass
        else:
            preview_text = _format_preview_text(drafts, current_tab=current_tab, view_mode=view_mode)
            await bot.edit_message_text(
                chat_id=chat_id, message_id=sent_message.message_id,
                text=preview_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
        return True
    except Exception as e:
        SafeLogger.warn(f"Failed to update Telegram preview message: {e}")
        return False

async def send_draft_for_approval(
    drafts: Any = None,  # PlatformDrafts | str
    media: Optional[MediaAsset] = None,
    client: Optional[httpx.AsyncClient] = None,
    genai_client: Optional[Any] = None,
    topic: str = "General",
    text: Optional[str] = None  # Backward-compatible keyword alias
) -> Tuple[Optional[Any], Optional[MediaAsset]]:
    """
    Sends generated post drafts and image to Telegram for approval.
    Maintains one authoritative preview message (photo if media present, else text).
    Returns Tuple: (approved_drafts, approved_media) or (None, None) if rejected.
    """
    from src.models import PlatformDrafts
    raw_input = drafts if drafts is not None else text
    current_drafts = raw_input if isinstance(raw_input, PlatformDrafts) else PlatformDrafts.from_single(str(raw_input or ""))

    if not settings.telegram_bot_token or not settings.telegram_user_id:
        SafeLogger.info("Telegram: Missing bot token or user ID. Skipping Telegram approval stage.")
        return current_drafts, media

    if settings.is_dry_run:
        SafeLogger.info("Telegram: DRY_RUN enabled. Skipping approval message dispatch.")
        return current_drafts, media

    try:
        bot = Bot(token=settings.telegram_bot_token)
        chat_id = settings.telegram_user_id

        current_tab = "bluesky"
        view_mode = "tabs"
        remix_state = "idle"  # "idle" | "awaiting_instruction" | "in_flight"
        active_prompt_id = None
        remix_target = "bluesky"  # "bluesky" | "threads" | "mastodon" | "all"

        reply_markup = _build_telegram_markup(current_tab=current_tab, view_mode=view_mode, remix_state=remix_state)
        preview_text = _format_preview_text(current_drafts, current_tab=current_tab, view_mode=view_mode)

        sent_message = None
        image_bytes = media.image_bytes if media else None
        if image_bytes:
            SafeLogger.info("Telegram: Sending draft and image for approval...")
            caption, followup = _get_caption_payload(current_drafts, current_tab=current_tab, view_mode=view_mode)
            sent_message = await bot.send_photo(
                chat_id=chat_id,
                photo=image_bytes,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            if followup:
                await bot.send_message(chat_id=chat_id, text=followup, parse_mode="Markdown")
        else:
            SafeLogger.info("Telegram: Sending draft for approval...")
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=preview_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

        updates = await bot.get_updates(limit=100)
        offset = updates[-1].update_id + 1 if updates else None

        timeout_seconds = settings.telegram_timeout_minutes * 60
        poll_interval = 2
        start_time = time.monotonic()

        SafeLogger.info(f"Telegram: Waiting up to {settings.telegram_timeout_minutes} minutes for approval or edits...")
        while (time.monotonic() - start_time) < timeout_seconds:
            try:
                updates = await bot.get_updates(offset=offset, timeout=1)
                for update in updates:
                    offset = update.update_id + 1

                    # 1. Callback query handling
                    if update.callback_query:
                        query = update.callback_query

                        # Ownership validation
                        if str(query.from_user.id) != str(chat_id):
                            SafeLogger.warn(f"Telegram: Unauthorized interaction from user ID: {query.from_user.id}")
                            continue

                        # Stale callback validation
                        if not sent_message or not query.message or query.message.message_id != sent_message.message_id:
                            try:
                                await query.answer("Stale or expired draft session.", show_alert=True)
                            except Exception:
                                pass
                            continue

                        action = query.data
                        if action == "noop":
                            await query.answer()
                            continue

                        # Concurrency rule: ignore additional remix actions if not idle
                        if action.startswith("remix:") and remix_state != "idle":
                            await query.answer("A remix request is already in progress or awaiting feedback.", show_alert=True)
                            continue

                        if action == "approve":
                            SafeLogger.info("Telegram: User approved draft.")
                            await query.answer("Draft approved! Publishing...")
                            await bot.send_message(chat_id=chat_id, text="🚀 Approved. Posting to platforms...")
                            return current_drafts, media

                        elif action == "reject":
                            SafeLogger.info("Telegram: User rejected draft.")
                            await query.answer("Draft rejected.")
                            await bot.send_message(chat_id=chat_id, text="❌ Rejected. Run aborted.")
                            return None, None

                        elif action.startswith("tab:"):
                            tab_key = action.split(":")[1]
                            target_tab = "bluesky" if tab_key == "bsky" else ("threads" if tab_key == "threads" else "mastodon")
                            reply_markup = _build_telegram_markup(current_tab=target_tab, view_mode="tabs", remix_state=remix_state)
                            success = await _render_and_update_preview(
                                bot=bot, chat_id=chat_id, sent_message=sent_message,
                                drafts=current_drafts, current_tab=target_tab, view_mode="tabs",
                                reply_markup=reply_markup, image_bytes=image_bytes
                            )
                            if success:
                                current_tab = target_tab
                                view_mode = "tabs"
                                await query.answer(f"Switched to {current_tab.title()} tab.")
                            else:
                                await query.answer("Failed to switch tab.", show_alert=True)

                        elif action.startswith("view:"):
                            target_view = action.split(":")[1]
                            reply_markup = _build_telegram_markup(current_tab=current_tab, view_mode=target_view, remix_state=remix_state)
                            success = await _render_and_update_preview(
                                bot=bot, chat_id=chat_id, sent_message=sent_message,
                                drafts=current_drafts, current_tab=current_tab, view_mode=target_view,
                                reply_markup=reply_markup, image_bytes=image_bytes
                            )
                            if success:
                                view_mode = target_view
                                await query.answer(f"View mode: {view_mode.title()}")
                            else:
                                await query.answer("Failed to switch view.", show_alert=True)

                        elif action.startswith("remix:"):
                            remix_target = action.split(":")[1]
                            remix_state = "awaiting_instruction"
                            prompt_msg = await bot.send_message(
                                chat_id=chat_id,
                                text=f"✨ Reply to this message with your instruction to remix the **{remix_target.title()}** draft (e.g., 'make it punchier', 'remove company name'):",
                                reply_to_message_id=sent_message.message_id
                            )
                            active_prompt_id = prompt_msg.message_id
                            await query.answer("Awaiting edit instruction...")

                        elif action == "regenerate_text":
                            remix_target = current_tab
                            remix_state = "awaiting_instruction"
                            prompt_msg = await bot.send_message(
                                chat_id=chat_id,
                                text="📥 Reply to this message with a feedback hint for text regeneration (or reply `/skip` to regenerate with default settings):",
                                reply_to_message_id=sent_message.message_id
                            )
                            active_prompt_id = prompt_msg.message_id
                            await query.answer("Provide feedback for text regeneration...")

                        elif action == "regenerate_image":
                            SafeLogger.info("Telegram: User requested image regeneration.")
                            if not genai_client or not client:
                                await bot.send_message(chat_id=chat_id, text="⚠️ API clients missing; image regeneration unavailable.")
                                await query.answer()
                                continue

                            status_msg = await bot.send_message(chat_id=chat_id, text=f"🎨 Regenerating image card using {settings.image_provider.upper()}...")
                            await query.answer("Regenerating image...")

                            try:
                                from src.curator import generate_visual_prompt, generate_ai_image, generate_image_alt_text, validate_image_bytes
                                from PIL import Image
                                import io
                                from src.utils import get_image_mime

                                active_text = current_drafts.get(current_tab)
                                visual_prompt = await generate_visual_prompt(genai_client, active_text, topic)
                                new_image_data = await generate_ai_image(client, genai_client, visual_prompt)

                                if new_image_data and validate_image_bytes(new_image_data):
                                    alt_prompt = visual_prompt or f"Minimalist tech illustration of {topic}"
                                    new_alt_text = await generate_image_alt_text(new_image_data, prompt=alt_prompt, topic=topic)
                                    mime_type = get_image_mime(new_image_data)
                                    width, height = None, None
                                    try:
                                        img = Image.open(io.BytesIO(new_image_data))
                                        width, height = img.size
                                    except Exception:
                                        pass

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

                                    caption, followup = _get_caption_payload(current_drafts, current_tab=current_tab, view_mode=view_mode)
                                    if sent_message and image_bytes:
                                        await bot.edit_message_media(
                                            chat_id=chat_id,
                                            message_id=sent_message.message_id,
                                            media=InputMediaPhoto(
                                                media=new_image_data,
                                                caption=caption,
                                                parse_mode="Markdown"
                                            ),
                                            reply_markup=reply_markup
                                        )
                                        # Commit authoritative media state immediately
                                        media = new_media
                                        image_bytes = new_image_data
                                        if followup:
                                            try:
                                                await bot.send_message(chat_id=chat_id, text=followup, parse_mode="Markdown")
                                            except Exception as fe:
                                                SafeLogger.warn(f"Failed to send follow-up after image regeneration: {fe}")
                                    else:
                                        sent_photo = await bot.send_photo(
                                            chat_id=chat_id,
                                            photo=new_image_data,
                                            caption=caption,
                                            reply_markup=reply_markup,
                                            parse_mode="Markdown"
                                        )
                                        # Commit authoritative media state immediately
                                        sent_message = sent_photo
                                        media = new_media
                                        image_bytes = new_image_data
                                        if followup:
                                            try:
                                                await bot.send_message(chat_id=chat_id, text=followup, parse_mode="Markdown")
                                            except Exception as fe:
                                                SafeLogger.warn(f"Failed to send follow-up after image regeneration: {fe}")

                                    await bot.send_message(chat_id=chat_id, text="🎨 Image card regenerated successfully!", reply_to_message_id=status_msg.message_id)
                                else:
                                    await bot.send_message(chat_id=chat_id, text="Image regeneration failed. The previous image has been preserved and the draft can still be approved.", reply_to_message_id=status_msg.message_id)
                            except Exception as e:
                                SafeLogger.error(f"Telegram: Image regeneration error: {e}")
                                await bot.send_message(chat_id=chat_id, text="Image regeneration failed. The previous image has been preserved and the draft can still be approved.", reply_to_message_id=status_msg.message_id)

                    # 2. Text message handling
                    elif update.message and update.message.text:
                        msg = update.message
                        if str(msg.from_user.id) != str(chat_id):
                            continue

                        text_val = msg.text.strip()
                        cmd_res = process_authorized_command(text_val)
                        if cmd_res:
                            if cmd_res.get("action") == "topic" and cmd_res.get("topic"):
                                from src.config import PENDING_TOPIC_FILE_PATH
                                try:
                                    with open(PENDING_TOPIC_FILE_PATH, "w", encoding="utf-8") as f:
                                        json.dump({"topic": cmd_res["topic"], "timestamp": time.time()}, f)
                                    SafeLogger.info(f"Telegram Loop: Persisted topic '{cmd_res['topic']}' to pending_topic.json")
                                except Exception as persist_err:
                                    SafeLogger.error(f"Telegram Loop: Failed to persist topic: {persist_err}")

                            if cmd_res.get("response"):
                                await bot.send_message(chat_id=chat_id, text=cmd_res["response"], reply_to_message_id=msg.message_id)
                            continue

                        # Scenario A: Replying to the active remix prompt
                        if (
                            remix_state == "awaiting_instruction"
                            and active_prompt_id
                            and msg.reply_to_message
                            and msg.reply_to_message.message_id == active_prompt_id
                        ):
                            remix_state = "in_flight"
                            instruction = msg.text.strip()
                            status_msg = await bot.send_message(
                                chat_id=chat_id,
                                text=f"✨ Remixing {remix_target.title()} draft with Gemini...",
                                reply_to_message_id=msg.message_id
                            )

                            # Temporarily update primary controls to in_flight
                            try:
                                await bot.edit_message_reply_markup(
                                    chat_id=chat_id,
                                    message_id=sent_message.message_id,
                                    reply_markup=_build_telegram_markup(remix_state="in_flight")
                                )
                            except Exception:
                                pass

                            try:
                                from src.curator import remix_platform_draft, remix_all_drafts
                                candidate_drafts = current_drafts
                                if remix_target == "all" or instruction.startswith("/remix_all "):
                                    clean_inst = instruction.replace("/remix_all ", "", 1).strip() or instruction
                                    remix_ok, new_drafts = await remix_all_drafts(genai_client, current_drafts, clean_inst)
                                    if remix_ok:
                                        candidate_drafts = new_drafts
                                else:
                                    target_p = remix_target if remix_target in ("bluesky", "threads", "mastodon") else current_tab
                                    current_p_text = current_drafts.get(target_p)
                                    remix_ok, remixed_text = await remix_platform_draft(genai_client, current_p_text, instruction, target_p.title())
                                    if remix_ok:
                                        candidate_drafts = current_drafts.with_update(target_p, remixed_text)

                                reply_markup = _build_telegram_markup(current_tab=current_tab, view_mode=view_mode, remix_state="idle")
                                update_ok = await _render_and_update_preview(
                                    bot=bot, chat_id=chat_id, sent_message=sent_message,
                                    drafts=candidate_drafts, current_tab=current_tab, view_mode=view_mode,
                                    reply_markup=reply_markup, image_bytes=image_bytes
                                )

                                if remix_ok and update_ok:
                                    current_drafts = candidate_drafts
                                    await bot.send_message(chat_id=chat_id, text="✨ Draft successfully remixed!", reply_to_message_id=msg.message_id)
                                elif not update_ok and remix_ok:
                                    # Edit to Telegram preview failed; preserve previous in-memory draft so approval matches preview
                                    await bot.send_message(chat_id=chat_id, text="⚠️ Preview update failed. Previous draft preserved.", reply_to_message_id=msg.message_id)
                                else:
                                    await bot.send_message(chat_id=chat_id, text="⚠️ Remix failed (quota or network error). Previous draft preserved.", reply_to_message_id=msg.message_id)
                            except Exception as e:
                                SafeLogger.warn(f"Remix execution failed: {e}")
                                await bot.send_message(chat_id=chat_id, text=f"⚠️ Remix failed ({e}). Previous draft preserved.", reply_to_message_id=msg.message_id)
                            finally:
                                remix_state = "idle"
                                active_prompt_id = None
                                reply_markup = _build_telegram_markup(current_tab=current_tab, view_mode=view_mode, remix_state="idle")
                                try:
                                    await bot.edit_message_reply_markup(
                                        chat_id=chat_id, message_id=sent_message.message_id, reply_markup=reply_markup
                                    )
                                except Exception:
                                    pass

                        # Scenario B: Manual direct replacement via /edit or direct reply to draft
                        else:
                            new_text = None
                            is_edit = False
                            if msg.text.startswith("/edit "):
                                new_text = msg.text[6:].strip()
                                is_edit = True
                            elif msg.reply_to_message and msg.reply_to_message.message_id == sent_message.message_id:
                                new_text = msg.text.strip()
                                is_edit = True

                            if is_edit and new_text:
                                candidate_drafts = current_drafts.with_update(current_tab, new_text)
                                reply_markup = _build_telegram_markup(current_tab=current_tab, view_mode=view_mode, remix_state=remix_state)
                                update_ok = await _render_and_update_preview(
                                    bot=bot, chat_id=chat_id, sent_message=sent_message,
                                    drafts=candidate_drafts, current_tab=current_tab, view_mode=view_mode,
                                    reply_markup=reply_markup, image_bytes=image_bytes
                                )
                                if update_ok:
                                    current_drafts = candidate_drafts
                                    await bot.send_message(chat_id=chat_id, text=f"📝 Updated {current_tab.title()} draft!", reply_to_message_id=msg.message_id)
                                else:
                                    await bot.send_message(chat_id=chat_id, text="⚠️ Failed to update draft preview. Previous draft preserved.", reply_to_message_id=msg.message_id)

            except Exception as e:
                SafeLogger.warn(f"Telegram: Error checking updates: {e}")

            await asyncio.sleep(poll_interval)

        SafeLogger.info("Telegram: Approval timeout expired. Automatically publishing draft.")
        await bot.send_message(chat_id=chat_id, text="🕒 Timeout expired. Automatically publishing draft.")
        return current_drafts, media

    except Exception as e:
        SafeLogger.error(f"Telegram approval engine encountered an error: {e}")
        return current_drafts, media

def process_authorized_command(text: str) -> Optional[dict]:
    """
    Consolidated handler for authorized Telegram text commands.
    Recognizes: /topic <t>, /curate <t>, /watch <t>, /unwatch <t>, /watches, /brief <t>.
    Returns a result dictionary describing the command action or None if unhandled.
    """
    if not text:
        return None

    cmd_text = text.strip()

    if cmd_text.startswith("/brief "):
        topic = cmd_text.replace("/brief ", "", 1).strip()
        if not topic or len(topic) > 100 or "http://" in topic or "https://" in topic:
            return {"action": "brief_invalid", "response": "⚠️ Invalid brief topic. Provide a clean topic string under 100 characters."}
        return {"action": "brief", "topic": topic, "response": f"📊 Generating grounded briefing for *{topic}* across past 7 days..."}
    elif cmd_text.startswith("/topic "):
        topic = cmd_text.replace("/topic ", "", 1).strip()
        return {"action": "topic", "topic": topic, "response": f"📥 Received topic request: *{topic}*. Curating now..."} if topic else None
    elif cmd_text.startswith("/curate "):
        topic = cmd_text.replace("/curate ", "", 1).strip()
        return {"action": "topic", "topic": topic, "response": f"📥 Received topic request: *{topic}*. Curating now..."} if topic else None
    elif cmd_text.startswith("/watch "):
        raw_topic = cmd_text.replace("/watch ", "", 1).strip()
        if not raw_topic or len(raw_topic) > 100 or "http://" in raw_topic or "https://" in raw_topic:
            return {"action": "watch_invalid", "response": "⚠️ Invalid watch topic. Provide a clean topic string under 100 characters."}

        norm_topic = raw_topic.lower()
        from src.utils import load_seen_articles, save_seen_articles
        state = load_seen_articles()
        watches = state.get("watch_topics", [])

        if len(watches) >= 10:
            return {"action": "watch_limit", "response": "⚠️ Maximum of 10 watch topics reached. Remove one using /unwatch first."}

        if any((w.get("topic") if isinstance(w, dict) else str(w).lower()) == norm_topic for w in watches):
            return {"action": "watch_exists", "response": f"📌 Topic *{raw_topic}* is already in your watchlist."}

        new_entry = {
            "topic": norm_topic,
            "display_name": raw_topic,
            "created": datetime.now(timezone.utc).isoformat(),
            "keywords": [k for k in re.findall(r'\b\w+\b', norm_topic) if len(k) > 1],
            "last_matched": None
        }
        watches.append(new_entry)
        state["watch_topics"] = watches
        save_seen_articles(state)
        return {"action": "watch_added", "topic": raw_topic, "response": f"✅ Added *{raw_topic}* to watchlist ({len(watches)}/10 topics active)."}

    elif cmd_text.startswith("/unwatch "):
        raw_topic = cmd_text.replace("/unwatch ", "", 1).strip().lower()
        from src.utils import load_seen_articles, save_seen_articles
        state = load_seen_articles()
        watches = state.get("watch_topics", [])

        initial_len = len(watches)
        updated_watches = [w for w in watches if (w.get("topic") if isinstance(w, dict) else str(w).lower()) != raw_topic]

        if len(updated_watches) == initial_len:
            return {"action": "unwatch_not_found", "response": f"🔍 Topic *{raw_topic}* not found in your watchlist."}

        state["watch_topics"] = updated_watches
        save_seen_articles(state)
        return {"action": "unwatch_removed", "topic": raw_topic, "response": f"🗑️ Removed *{raw_topic}* from watchlist ({len(updated_watches)}/10 remaining)."}

    elif cmd_text == "/watches" or cmd_text.startswith("/watches "):
        from src.utils import load_seen_articles
        state = load_seen_articles()
        watches = state.get("watch_topics", [])

        if not watches:
            return {"action": "watches_list", "response": "📋 Your topic watchlist is empty. Add topics using `/watch <topic>`."}

        lines = ["📋 *Active Topic Watchlist:*"]
        for idx, w in enumerate(watches):
            name = w.get("display_name", w.get("topic", "Unknown")) if isinstance(w, dict) else str(w)
            date_str = w.get("created", "")[:10] if isinstance(w, dict) else ""
            suffix = f" (added {date_str})" if date_str else ""
            lines.append(f"{idx+1}. *{name}*{suffix}")
        return {"action": "watches_list", "response": "\n".join(lines)}

    return None

async def check_for_telegram_topic() -> Tuple[Optional[str], Optional[str]]:
    """
    Checks if there's a recent command sent by the authorized user,
    either from pending_topic.json or directly from Telegram updates.
    Processes /watch, /unwatch, /watches in-place.
    Returns (command_type, topic) tuple where command_type is "topic" or "brief", or (None, None).
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
        return ("topic", topic_to_use)

    if not settings.telegram_bot_token or not settings.telegram_user_id:
        return (None, None)

    try:
        bot = Bot(token=settings.telegram_bot_token)
        chat_id = settings.telegram_user_id

        updates = await bot.get_updates(limit=50)
        if not updates:
            return (None, None)

        # Look for the latest message from the authorized user in the last 15 minutes
        now = time.time()
        for update in reversed(updates):
            if update.message and str(update.message.from_user.id) == str(chat_id):
                msg = update.message
                # Verify it was sent in the last 15 minutes
                if msg.date and (now - msg.date.timestamp()) < 900:
                    text = msg.text or ""
                    result = process_authorized_command(text)
                    if result:
                        # Acknowledge this update and all previous ones
                        try:
                            await bot.get_updates(offset=update.update_id + 1, limit=1)
                        except Exception as e:
                            SafeLogger.warn(f"Telegram: Failed to acknowledge updates: {e}")

                        if result.get("response"):
                            await bot.send_message(chat_id=chat_id, text=result["response"])

                        if result.get("action") in ("topic", "brief"):
                            return (result.get("action"), result.get("topic"))
                        else:
                            # Non-topic/brief command (/watch, /unwatch, /watches) handled and acknowledged. Stop polling to prevent processing older stale updates.
                            return (None, None)
        return (None, None)
    except Exception as e:
        SafeLogger.warn(f"Telegram: Error checking for topic intercept: {e}")
        return (None, None)

async def send_broadcast_platform_messages(
    bot_token: str,
    chat_id: Any,
    results: List[Any],
    synthesis: Any,
) -> bool:
    """
    Sends 3 dedicated plain-text messages to Telegram (one per platform: Bluesky, Threads, Mastodon).
    Provides immediate full transparency on published post variants, status, and requested delivery mode.
    Attempts all platforms independently so a failure on one does not block the others.
    Returns True if all sends succeeded, False if any send failed.
    """
    if not bot_token or not chat_id:
        return False

    try:
        bot = Bot(token=bot_token)
    except Exception as e:
        SafeLogger.warn(f"Telegram: Failed to initialize bot for broadcast summary: {e}")
        return False

    platform_specs = [
        ("bluesky", "🔵 Bluesky"),
        ("threads", "🧵 Threads"),
        ("mastodon", "🐘 Mastodon"),
    ]

    all_succeeded = True
    media = getattr(synthesis, "media", None)
    lead_link = getattr(synthesis, "lead_link", None)

    for p_key, p_label in platform_specs:
        try:
            # 1. Resolve outcome from broadcast results
            matched_res = None
            for res in (results or []):
                res_platform = getattr(res, "platform", "")
                if res_platform and res_platform.lower() == p_key:
                    matched_res = res
                    break

            if matched_res:
                if matched_res.success:
                    status_str = "✅ Published"
                else:
                    err_detail = matched_res.error or "Unknown error"
                    status_str = f"❌ Failed ({err_detail})"
            else:
                status_str = "⚪ Not configured / not attempted"

            # 2. Determine requested delivery mode
            has_bytes = bool(media and getattr(media, "image_bytes", None))
            has_public_url = bool(media and getattr(media, "public_url", None))
            if p_key == "bluesky":
                delivery_mode = f"External card ({lead_link})" if lead_link else ("Image embed" if has_bytes else "Text only")
            elif p_key == "mastodon":
                delivery_mode = "Uploaded media" if has_bytes else "Text only"
            elif p_key == "threads":
                delivery_mode = "Hosted image" if has_public_url else "Text only"
            else:
                delivery_mode = "Text only"

            # 3. Retrieve draft sent to broadcaster
            draft_content = ""
            if hasattr(synthesis, "get_platform_content"):
                draft_content = synthesis.get_platform_content(p_key)
            elif hasattr(synthesis, "content"):
                draft_content = synthesis.content or ""

            # 4. Compose clean plain-text message
            msg_text = (
                f"{p_label} • {status_str}\n"
                f"Requested delivery: {delivery_mode}\n\n"
                f"Draft sent to broadcaster:\n"
                f"{draft_content}"
            )

            # 5. Dispatch plain-text message
            await bot.send_message(chat_id=chat_id, text=msg_text)
        except Exception as p_err:
            SafeLogger.warn(f"Telegram: Failed to send broadcast message for {p_label}: {p_err}")
            all_succeeded = False

    return all_succeeded
