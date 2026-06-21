# 🚀 PR v3.13.0: Interactive Text & Image Regeneration from Telegram

This PR introduces real-time text and image regeneration capabilities directly inside the Telegram draft approval queue, allowing for rapid loop feedback and draft updates before broadcasting.

## Proposed Upgrades

### 🔄 1. Interactive Text Curation Regeneration
- **Feedback Loops**: User can click `[🔄 Regenerate Text]` and reply to the bot with custom editing instructions (e.g. "shorter", "make it more practical") or send `/skip` to trigger default regeneration.
- **Dynamic Rewrite Engine**: Gemini rewrites the current draft inline based on the feedback hint, validating the new length constraints and updating the active inline buttons preview.

### 🎨 2. Nvidia Image & Alt-Text Regeneration
- **Visual Regeneration**: User can click `[🎨 Regenerate Image]` to automatically generate a new visual prompt based on the latest draft text.
- **Nvidia SD3 NIM integration**: Fetches and downscales a new isometric image card under the 900KB Cap.
- **Gemini Vision Alt-Text Sync**: Generates a new 100-character description for the updated card, which is then updated dynamically in the chat preview using Telegram's `edit_message_media` API.

---

## 🛠️ Compliance with `AGENTS.md` Rules

### 1. What was Deleted or Simplified
- Unified `send_draft_for_approval` to return a `Tuple[Optional[str], Optional[bytes], Optional[str]]` containing the final text, image, and alt text. This simplifies the bot lifecycle by keeping all media assets stateless and mutable during the review loop.

### 2. Why the Simpler Version is Safe
- Uses Telegram's standard `edit_message_media` and `edit_message_caption` APIs to modify existing preview messages, preserving active inline button sessions and avoiding infinite message spam.
- In case of transient API errors, the outer catch block safely falls back to auto-posting the current draft instead of aborting.

### 3. Verification & Tests Run
- Added comprehensive unit tests in [test_telegram_gateway.py](file:///d:/Code/BlueSky/src/tests/test_telegram_gateway.py):
  - `test_send_draft_for_approval_regenerate_text`: Verifies text regeneration callback, feedback prompt reply matching, Gemini call integration, and limits warnings.
  - `test_send_draft_for_approval_regenerate_image`: Verifies image regeneration callback, prompt calculation, image generation, alt-text generation, and media editing.
- Ran **46 tests successfully** using `pytest`.
- Ran `python bot.py --dry-run` to verify end-to-end integration and dry-run safety.
