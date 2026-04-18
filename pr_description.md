# PR Description: Natural Vibe Engine (v3.7.0) 🎭🚀

This PR evolves BluBot from a scheduled automation script into a **Dynamic Editorial Entity**. It introduces high-resolution temporal intelligence, stylistic memory, and automated manual-run detection to make the bot feel significantly more natural and varied in its social media feed.

## 🌟 Key Features (v3.7.0)

### 1. The Natural Vibe Engine (Stylistic Memory)
BluBot now has "memory" of its own persona. It records its last used style and ensures the next run uses a different one from a pool of 5 distinct dialects:
- **ANALYTICAL**: Data-driven specs and arch impact.
- **PRACTICAL**: Engineering utility and "How-to".
- **SAGE**: Visionary strategy and industry shifts.
- **CONCISE**: High-velocity scanner updates.
- **PHILOSOPHICAL**: Ethical exploration and the "Big Picture".

### 2. High-Resolution Temporal Intelligence
Resolved the "Session" logic from 2 slots to **5 granular sessions**, ensuring content is perfectly aligned with the time of day:
- **Night Reflection** (00:00 - 06:00)
- **Morning Intelligence** (06:00 - 11:00)
- **Midday Briefing** (11:00 - 15:00)
- **Afternoon Deep Dive** (15:00 - 19:00)
- **Evening Synthesis** (19:00 - 24:00)

### 3. Feed Vanguard Automation
Implemented an industrial-grade health engine to manage our elite **29-feed network**:
- **Hiccup Resilience**: The first failure only triggers a warning. Silent mode (1h → 12h → 72h) only begins on consecutive failures to prevent transient dropouts.
- **Pre-flight Audit**: The bot validates all sources before curation, ensuring zero cycles are wasted on broken links.
- **Elite Coverage**: Expanded to include **AlphaSignal**, **TheSequence**, and **TLDR AI**.

### 4. Architectural Hardening
- **Absolute Imports**: Converted all relative imports to absolute `src.` paths to resolve `pytest` isolation issues and standardizing the source tree.
- **State Persistence**: Extended the atomic persistence logic to track `last_dialect`.

## 🧪 Verification Results

- **Automated Tests**: Passed 100% of the 15-test regression suite (`pytest src/tests/`).
- **Regression Check**: Verified internal constant consistency (restored `CURATOR_SYSTEM_INSTRUCTION`).
- **Dry-Run Validation**: Successful execution via `test_models.py` with mock-ad-hoc interception.

## 📊 Documentation Updates
- **README.md**: Updated with v3.7.0 key features and Status Dashboard.
- **WIKI_MANUAL.md**: Added Page 10 (The Natural Vibe Engine).

---
*Built for the Elite Sage released under v3.7.0*
