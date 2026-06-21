# 🚀 PR v3.12.2: Telegram Draft Editing via Reply and Character Limit Warnings

This PR introduces interactive draft editing via Telegram replies or command intercept, accompanied by real-time character limit validation and platform-specific warnings.

## Proposed Upgrades

### 🎮 1. Interactive Telegram Draft Editing
- **Reply Intercept**: Intercepts user replies to the sent draft message in Telegram. It updates the draft preview dynamically so that you can see the latest text version with active `[✅ Approve]` and `[❌ Reject]` buttons.
- **`/edit` Command**: Allows sending `/edit <new text>` directly to modify the active draft.
- **Zero-State Regression**: Returning `Optional[str]` from `send_draft_for_approval` cleanly integrates with the main execution pipeline, replacing the synthesized content with the approved edit.

### ⚠️ 2. Character Limit Validation & Warnings
- **Dynamic Limit Calculation**: Checks the updated draft length against the single-post and multi-post limits of Bluesky, Mastodon, and Threads.
- **Split Warning**: Warns the user if the text is long and will be split into a multi-part thread.
- **Truncation Warning**: Alerts the user if the text length exceeds the thread limit (e.g. 580 characters for Bluesky) to prevent silent truncation.

---

## 🛠️ Compliance with `AGENTS.md` Rules

### 1. What was Deleted or Simplified
- Removed boolean return constraints from `send_draft_for_approval`. Returning the final string directly simplifies the execution logic and avoids having to maintain external mutable state for drafts.

### 2. Why the Simpler Version is Safe
- Inline updates polling with the official `python-telegram-bot` wrapper remains completely stateless and runs without persistent listener threads or open ports.
- Fallback logic remains robust: if the runner times out or encounters network glitches, it automatically posts the latest approved/edited draft.

### 3. Verification & Tests Run
- Added comprehensive unit tests in `src/tests/test_telegram_gateway.py` to cover:
  - `test_validate_text_limits`: Verifies correct warning/note logic for short, medium, and long texts.
  - `test_send_draft_for_approval_approve`: Verifies approvals return the correct text.
  - `test_send_draft_for_approval_reject`: Verifies rejections return `None`.
  - `test_send_draft_for_approval_edit_by_reply`: Verifies replies update the draft message and return the updated text.
- Ran **44 tests successfully** using `pytest`.
- Ran `python bot.py --dry-run` to verify end-to-end pipeline compatibility.
