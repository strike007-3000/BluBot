# 📄 PR v3.13.5: Curation Engine v4 (Stable ID Registry, Category Rotation, and Telegram Overrides)

This minor release introduces Curation Engine v4, resolving on-demand Telegram topic queue intercepts and enhancing curation diversity through stable source IDs, progressive category recurrence penalties, and writing style rotations.

---

## Changes

### 📡 Curation Engine & Registry Refinement
- **Stable ID Registry**: Transitioned `RSS_FEEDS` in `src/config.py` to a structured `SOURCE_REGISTRY` mapping each feed to a stable ID, category, quality assessment, and base score.
- **Enterprise & Labs Rebalance**: Set Tier 1 Research Labs to base score `30`, and Enterprise AI Blogs to `25`–`27` to prevent product announcements from dominating research releases.
- **Open-source additions**: Integrated `vLLM`, `Ollama`, and `LM Studio` at base `18`.
- **Academic score reduction**: Reclassified `arxiv.org` under the `academic` category with base score `10` (down from `15`).
- **Critical voices constraint**: Reduced base scores of critical voices (e.g. AI Snake Oil, Gary Marcus) to `5` and added strict post-filtering in `fetch_news` ensuring critical voices are treated as supporting context only (never defining the lead story when non-critical alternatives exist).

### 🛠️ Telegram Topic Persistence
- **Queue Intercept Cache**: Implemented [pending_topic.json](file:///d:/Code/BlueSky/pending_topic.json) to persist topics captured during the draft approval polling loop, resolving race conditions where previous polling cycles consumed the Telegram update queue.
- **One-Shot Telemetry**: Ensures the topic override clears immediately upon use and logs the exact sequence of 3 logs for debug visibility.

### 🧠 Curation Diversity & Writing-Style Rotation
- **Progressive Recency Penalty**: Added a recency-weighted decay penalty for category recurrence to push feed variety dynamically.
- **Style Rotation**: Implemented LRU style selection across 5 distinct writing structures (`STRATEGIC_CONTRAST`, `PRACTICAL_WORKFLOW`, `RISK_VERIFICATION`, `ENTERPRISE_ROI`, `QUESTION_FIRST`) based on feed category compatibility.

---

## 🛠️ Compliance with `AGENTS.md` Rules

### 1. What was Deleted or Simplified
- Deleted cascading domain string matches in `curator.py` in favor of O(1) dictionary lookups (`FEED_SCORE_MAP` and `FEED_CATEGORY_MAP`).
- Simplified double-negative conditionals in `bot.py`'s `synthesis_stage` to clear boolean flags.
- Removed broad, noise-introducing feeds (`Apple Newsroom` and `Google Blog`).

### 2. Why the Simpler Version is Safe
- Dictionary lookups on registry IDs prevent mismatches when feed URLs change.
- Simplification of the synthesis routing prevents silent fallthroughs and ensures overrides are consistently processed.

### 3. Verification & Tests Run
- Added `test_registry_validation` and `test_fallback_behavior_unknown_source` to `src/tests/test_curator.py`.
- Ran the full test suite with 50 passing tests:
  ```bash
  python -m pytest src/tests/ -v
  ```
- Tested bot dry-run execution:
  ```bash
  python bot.py --dry-run
  ```
