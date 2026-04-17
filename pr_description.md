# 🚀 PR v3.12.0: Interactive Telegram Control, Alt Text, and Hashtag Management

This PR introduces interactive Telegram bot control (remote curating and approval queue), screen-reader multimodal alt-text generation, per-platform hashtag alignment, and a side-effect-free dry-run execution mode.

## Proposed Upgrades

### 🎮 1. Telegram Control & Approval Queue
- **Wait-and-Poll Approval**: Intercepts the post pipeline to request manual review (`[✅ Approve]`, `[❌ Reject]`) via a Telegram message. Automatically posts on timeout (default 5 minutes) to avoid runner hang-ups.
- **On-Demand Topic Curation**: Intercepts curation to fetch, score, and summarize a custom topic if a `/topic <keyword>` command is received from the authorized `TELEGRAM_USER_ID` within the last 15 minutes.

### ♿ 2. Screen Reader Multimodal Alt-Text
- Implemented `generate_image_alt_text` using Gemini Vision (`models/gemini-2.5-flash-lite`) to generate 100-character descriptions for all visual assets. Alt-text is attached to Mastodon and Threads uploads.

### 🏷️ 3. Per-Platform Hashtags
- Toggles hashtags per platform via settings (`ENABLE_HASHTAGS_BSKY=false` by default). Safely strips standalone hashtags and preserves inline keywords by stripping formatting characters.

### 🛡️ 4. Side-Effect-Free Dry Run
- The `--dry-run` flag bypasses all external broadcasts, state file persistence, and live AI API calls (substituting mock summaries and alt-text) to enable offline local diagnostics.

---

## 🛠️ Compliance with `AGENTS.md` Rules

### 1. What was Deleted or Simplified
- **Simplified Scopes in `src/curator.py`**: Removed local import statements for configuration parameters (`from .config import GEMINI_MODEL_PRIORITY`) that caused `UnboundLocalError` when accessed inside fallback functions.
- **Bypassed Action Complexity**: Implemented inline Telegram updates polling instead of persistent webhook listeners, keeping the architecture extremely simple and fit for ephemeral CI runners.

### 2. Why the Simpler Version is Safe
- Inline polling using the official `python-telegram-bot` wrapper avoids running persistent threads or opening network ports in GitHub Actions.
- Local dry-run checks in `summarize_news`, `broadcast_stage`, and `persistence_stage` guarantee that runs executed with `--dry-run` are 100% side-effect-free, even with invalid API keys.

### 3. Verification & Tests Run
- Added `test_dry_run_broadcaster_bypasses_real_posts` and `test_dry_run_persistence_does_not_save` to verify the new diagnostic flag.
- Added `test_telegram_settings_defaults` to verify environment mapping.
- Ran **37 tests successfully** using `pytest src/tests/`.
- Ran `python bot.py --dry-run` to verify end-to-end telemetry and dry-run safety.
