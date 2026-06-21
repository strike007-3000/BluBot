# 🚀 PR v3.13.1: Threads Media Propagation and Stale Image Prevention

This PR fixes a bug where the stale crawled `synthesis.image_url` was preserved even after regenerating or editing the image via the Telegram approval gateway. This led to Threads broadcasting the original crawled image rather than the approved/regenerated media.

## Proposed Upgrades

### 🔄 1. Stale Image URL Clearing
- When the final approved image bytes (`final_image`) differ from the original synthesis image bytes (`synthesis.image_data`), the bot now automatically clears `synthesis.image_url` (setting it to `None`).
- This ensures the broadcaster (`post_to_threads`) does not attempt to post the stale original image to Threads.

---

## 🛠️ Compliance with `AGENTS.md` Rules

### 1. What was Deleted or Simplified
- Simplified the state management of the synthesis dataclass replacement inside `bot.py` during approval. Rather than needing a complex image-upload pipeline, we clear the stale image URL to prevent publishing incorrect or old media.

### 2. Why the Simpler Version is Safe
- It is completely side-effect free. If the image is not regenerated, the original URL is preserved. If the image is changed, the URL is cleared, which is the correct and safe behavior to prevent posting stale content.

### 3. Verification & Tests Run
- Added comprehensive unit tests in [test_telegram_propagation.py](file:///d:/Code/BlueSky/src/tests/test_telegram_propagation.py):
  - `test_telegram_approval_image_url_propagation_changed`: Verifies that `image_url` is set to `None` if the approved image differs from the original.
  - `test_telegram_approval_image_url_propagation_unchanged`: Verifies that `image_url` is preserved if the approved image remains unchanged.
- Ran **48 tests successfully** using `pytest`.
- Ran `python bot.py --dry-run` to verify end-to-end integration and dry-run safety.
