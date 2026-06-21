# 📄 PR v3.13.4: Comprehensive Documentation Sync

This patch release synchronizes all documentation to accurately reflect the current state of BluBot v3.13.3 and bumps the version to **v3.13.4**.

---

## Changes

### 📄 SECURITY.md
- Updated **supported versions table**: `3.13.x` (Active), `3.12.x` (security patches only), `3.11.x`/`3.10.x` (deprecated), `< 3.10` (EOL)
- Bumped **security baseline** reference from `v3.6.7` → `v3.13.3`
- Expanded hardening section with **4 previously undocumented protections**:
  - Decompression Bomb DoS (`Image.MAX_IMAGE_PIXELS = 10,000,000`)
  - Telegram impersonation gating (`TELEGRAM_USER_ID` validation on all callbacks)
  - Zero-Duplicate Threads logic (Catch & Log delivery model)
  - Resilient RSS parsing (raw bytes + safe attribute lookups)

### 🔒 PRIVACY.md
- Updated **Last Updated** date to June 21, 2026
- **Broadened scope** from Threads-only to all 4 platforms: Bluesky, Mastodon, Threads, Telegram
- Added disclosures for:
  - Interaction Engine metadata handling (`seen_interactions.json`)
  - Telegram message processing scope (scoped to `TELEGRAM_USER_ID`, nothing persisted)
  - Google Gemini / NVIDIA NIM API data handling with links to their privacy policies
- **Enumerated all 4 persisted state files** in Section 4 with contents and caps
- **Expanded revocation steps** to cover all platforms (including Telegram BotFather `/revoke`)

### 📖 docs/WIKI_MANUAL.md
- **Page 5**: Corrected feed count from "over 30" → "exactly 32 premium feeds across 4 tiers"
- **Page 6**: Added **11 missing environment variables** to the secrets table:
  `MASTODON_ACCESS_TOKEN`, `MASTODON_BASE_URL`, `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `TELEGRAM_TIMEOUT_MINUTES`, `ENABLE_TELEGRAM_APPROVAL`,
  `ENABLE_HASHTAGS_BSKY`, `ENABLE_HASHTAGS_MASTODON`, `ENABLE_HASHTAGS_THREADS`
- Clarified `THINKING_BUDGET` note: bypassed for Gemma models
- **Page 8**: Removed stale broken anchor links

### 📋 README.md
- Fixed **model failover list** to exact IDs from `config.py`:
  `gemini-3.1-flash-lite-preview → gemma-4-31b-it → gemma-4-26b-a4b-it → gemma-3-27b-it → gemini-2.5-flash-lite`
- Clarified `ENABLE_HASHTAGS_BSKY` default=`false` description
- Updated testing section version reference from `v3.6.5` → `v3.13.3`
- Added `v3.13.4` changelog entry

### 📊 STATUS.md
- Updated last run date from `2026-06-16` → `2026-06-21`

### 🔢 VERSION
- `3.13.3` → `3.13.4`

---

## 🛠️ Compliance with `AGENTS.md` Rules

### 1. What was Deleted or Simplified
- Removed 5 stale broken anchor links from WIKI_MANUAL.md Page 8.
- Removed the inaccurate version `3.2.x`/`3.1.x`/`<3.0` table from SECURITY.md.

### 2. Why the Simpler Version is Safe
- All changes are documentation-only. No logic or code was modified.

### 3. Verification & Tests Run
- All documentation cross-verified against live source files:
  `src/config.py`, `src/settings.py`, `src/telegram_gateway.py`, `bot.py`
- No automated tests required (no code changes).

## Type of Change
- [x] Documentation update
- [x] Version bump (patch)
