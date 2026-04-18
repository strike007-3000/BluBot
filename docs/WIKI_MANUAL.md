# 📖 BluBot Elite Sage: The Complete Manual

Welcome to the official Wiki for the **Elite Sage** (BluBot v3.7.0). This guide balances the technical inner workings with the "Sage" persona's philosophy.

---

## 🏠 Page 1: The Sage Philosophy

The BluBot is an **Impact-Aware Intelligence** designed to separate the *signal* from the *noise*.

### The Vision
The Sage looks for **Product Shifts** (real code) and **Technical Gems** (research papers, deep engineering blogs). It shares findings as a mentor, not just a news aggregator.

## Security & Supply Chain

BluBot uses elite hardening to protect its environment and secrets.

### Dependency Locking (pip-tools)
To prevent supply-chain attacks via unvetted transitive dependencies, BluBot uses **`pip-tools`**.
- `requirements.in`: The source file where you list high-level libraries.
- `requirements.txt`: The **lockfile** (generated) containing specific versions and cryptographic hashes.

**How to update dependencies:**
1. Add the new library to `requirements.in`.
2. Run: `pip-compile requirements.in --generate-hashes`.
3. Commit both files.

### SSRF Protection
The bot implements a **DNS Pinner** and **Public IP Validator** in `src/utils.py`. It refuses to fetch metadata or images from local or internal network addresses, thwarting potential exploits in ephemeral cloud runners.

### Secret Redaction
The `SafeLogger` automatically redacts secrets based on both keyword matching and **statistical entropy analysis**, ensuring that accidentally logged tokens are masked before hitting CI logs.

### Platform Synergy
- **Bluesky**: The central technical hub.
- **Mastodon**: The academic and decentralized pulse.
- **Threads**: The broad industry narrative.

---

## 🧠 Page 2: Breakthrough Scoring Engine v3

The "Brain" of the bot ranked by a weighted matrix.

### The Scoring Pipeline
1. **Source Tiering**: Tier 1 (+30), Tier 2 (+15), Hidden Gems (+25).
2. **Signal Boosting (+12)**: Keywords like *SOTA, Agentic, World Model, Open Weights*.
3. **Momentum (+18)**: flagship entities like *GPT-5, Llama 4, Gemini 3*.
4. **Consensus Synergy (+15)**: Applied if a story is found in multiple independent feeds.
5. **Diversity Penalty (-25)**: Prevents single-topic echo chambers.

---

## 🛡️ Page 3: Reliability & The Fortress (v3.6.5)

The Sage is designed to be **unbreakable**.

### Hardening Features
- **3-Tier State Resilience (v3.8.0)**: BluBot now implements a redundant persistence model. If the primary `seen_articles.json` is corrupted or missing, it automatically falls back to a local `.bak` rotation and finally a remote **GitHub Gist**.
- **Structured Logging (v3.6.5)**: The `SafeLogger` uses Python's `logging` module with a custom `JsonFormatter` and `RedactionFilter`. It automatically masks high-entropy strings (JWTs, API tokens) to prevent leakages.
- **Visual Integrity Defense (v3.7.6)**: Implements **Universal RGB Conversion** in the image engine to handle grayscale (ArXiv) and specialized modes, preventing solid-black/white artifact regressions.
- **SSRF Prevention Logic**: The metadata scraper (`get_link_metadata`) uses **DNS Pinning** to prevent rebinding attacks and **IP Validation** to ensure secure extraction.

---

## 🎨 Page 4: NVIDIA NIM Image Generation (v3.6)

The Sage uses **Stability AI Stable Diffusion 3 Medium** via NVIDIA's Inference Microservices as the primary image provider.

### The Designer Pipeline
1. **Lead Selection**: Scrape metadata.
2. **Logo Filter**: Automatically identifies and skips generic site logos (e.g., arXiv logo).
3. **NVIDIA Generation**: Calls the SD3 NIM with professional minimalist isometric prompts.
4. **Base64 Processing**: High-fidelity decoding into raw bytes for platform-specific broadcasting.

---

## 🛰️ Page 5: Source Intelligence

Scanning over **30 premium feeds**.
- **Tier 1**: OpenAI, DeepMind, Anthropic, HuggingFace, Mistral.
- **Hidden Gems**: ArXiv (CS.AI/LG), BAIR (Berkeley), SAIL (Stanford), NVIDIA Research.

---

## ⚙️ Page 6: Technical Configuration (v3.6.7)

### Environment Secrets
| Variable | Description |
| :--- | :--- |
| `GEMINI_KEY` | Google AI Studio Key |
| `NVIDIA_KEY` | NVIDIA Build API Key (for SD3) |
| `BSKY_HANDLE` | Your Bluesky handle |
| `BSKY_APP_PASSWORD` | BlueSky App Password |
| `GIST_ID` | Private GitHub Gist ID |
| `GIST_TOKEN` | GitHub Token with `gist` scope |
| `IMAGE_PROVIDER` | `nvidia` (default) or `imagen` |

---

## 🧪 Page 7: Local Testing & Interactive Diagnostics

The Sage provides a robust **Full Pipeline Dry Run** via `test_models.py`.

### Interactive Key Management
You can test the entire bot locally **without social media credentials**. 
1. **Interactive Entry**: If `GEMINI_KEY` or `NVIDIA_KEY` are missing from your `.env`, the script will prompt you to paste them in the console.
2. **Elite Rigidity**: The `Settings.from_env()` engine automatically injects "Mock" values for `BSKY_HANDLE` during dry runs, allowing you to verify synthesis logic with only AI keys.

### Running the Diagnostic
```bash
python test_models.py
```
Select **Option 2 (FULL PIPELINE DRY RUN)** to see a draft review of exactly what will be posted.

---

## 💾 Page 8: 3-Tier State Resilience (v3.8.0)

- [3-Tier State Resilience](#3-tier-state-resilience)
- [Security & Supply Chain](#security--supply-chain)
- [The Weaver (Threading)](#the-weaver-threading)
To ensure the Sage never "forgets" even in ephemeral runner environments, we use a tiered persistence model.

### The Recovery Sequence
1. **Primary Local**: Fast loading from `seen_articles.json` with advisory `FileLock`.
2. **Local Backup**: On every run, the previous state is saved to `.bak`. If the primary is corrupted, the bot auto-restores from this file.
3. **Remote Gist (The Cloud Memory)**: Syncs state with a private GitHub Gist. This allows the bot to maintain "Seen Articles" across different CI/CD runners without incurring Git merge conflicts.

---
## 🧪 Page 9: Automated Quality Control (v3.6.5)

BluBot v3.6.5 introduces a professional **Automated Test Suite** powered by `pytest`.

### The Test Layers
1. **Security (SSRF)**: Every URL metadata fetch is automatically tested against private IP ranges and redirect-spoofing attacks.
2. **Intelligence (Scoring)**: The Breakthrough Scoring Engine weights are verified to ensure "Signal over Noise" remains mathematically consistent.
3. **Hardening (Redaction)**: The `SafeLogger` is tested against high-entropy string detection to ensure no API keys leak into production logs.
4. **Transparency (Diagnostic Scoring)**: The curation engine attaches `_score_debug` metadata to every article, providing a granular breakdown (Source, Signal, Momentum, Penalty, Decay) visible during dry-runs.

### Running Automated Tests
```bash
pytest src/tests/
```

---

## 🎭 Page 10: The Natural Vibe Engine (v3.7.0)

Version 3.7.0 transforms the bot from a script into a **living editorial entity**.

### 1. The Editorial Pulse (Stylistic Memory)
The bot now tracks its previous tone to ensure consecutive updates feel varied:
- **Style Memory**: Saves the `last_dialect` to `seen_articles.json`.
- **The Diversity Pool**: 
    - **Analytical**: High-fidelity technical specs and benchmarks.
    - **Practical**: Developer utility and "How-to" engineering.
    - **Sage**: Visionary strategic impact and industry shifts.
    - **Concise**: Zero-fluff, minimalist scanner-friendly items.
    - **Philosophical**: Ethical considerations and world-shifting nature.

### 2. High-Resolution Temporal Intelligence
Resolved from a 2-session split into **5 granular sessions**:
- **Night Reflection** (00:00-06:00)
- **Morning Intelligence** (06:00-11:00)
- **Midday Briefing** (11:00-15:00)
- **Afternoon Deep Dive** (15:00-19:00)
- **Evening Synthesis** (19:00-24:00)

### 3. Manual Intercept Mode
The Sage now detects if it was triggered via a manual GitHub **workflow_dispatch**. 
- **Urgency Shift**: Appends **"(Intercept)"** to the session name.
- **Tone Modification**: Signifies to the AI that this is an ad-hoc briefing rather than a standard daily run, shifting the synthesis towards urgent insights.

---

## 🧵 Page 11: The Weaver (Multi-Post Threading)

Version 3.8.0 introduces the **Conditional Threading** engine, allowing for high-resolution narration.

### 1. Smart Split Logic
Instead of hard truncation, the bot now uses `smart_split` to chunk text at natural boundaries:
- **Priority 1**: Paragraph breaks (`\n\n`)
- **Priority 2**: Sentence endings (`. `)
- **Pagination**: Automatically appends `(1/N)` markers to keep the user oriented.

### 2. Platform-Native Chaining
- **Bluesky**: Uses depth-aware `root` and `parent` pointers to maintain reply integrity.
- **Mastodon**: Chains via `in_reply_to_id`.
- **Threads**: Sequentially publishes media containers with a `reply_to` link to the parent post.

### 3. Narrative Expansion
The Weaver allows the AI to use a **1000-character budget**, transforming the daily brief into a deep technical deep-dive without the fear of character limits.

---

## 📊 Page 12: System Telemetry Dashboards

Version 3.8.0 introduces high-resolution telemetry separated from the main documentation.

### The STATUS.md Advantage
To eliminate "Rebase Conflicts" in CI, live status updates (Operational status, Last Run, Session Mode, and Current Topic) are now maintained in **STATUS.md**.
- **Auto-Initialization**: If the file is missing, the bot bootstraps it with a professional header.
- **CI-Friendly**: Because `README.md` is no longer churned by every run, your main repository remains clean and conflict-free.

---
*Built with ❤️ for the AI Community*
