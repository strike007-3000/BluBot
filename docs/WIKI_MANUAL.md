# 📖 BluBot Elite Sage: The Complete Manual

Welcome to the official Wiki for the **Elite Sage** (BluBot v3.7.0). This guide balances the technical inner workings with the "Sage" persona's philosophy.

---

## 🏠 Page 1: The Sage Philosophy

The BluBot is an **Impact-Aware Intelligence** designed to separate the *signal* from the *noise*.

### The Vision
The Sage looks for **Product Shifts** (real code) and **Technical Gems** (research papers, deep engineering blogs). It shares findings as a mentor, not just a news aggregator.

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
- **Structured Logging (v3.6.5)**: The `SafeLogger` uses Python's `logging` module with a custom `JsonFormatter` and `RedactionFilter`. It automatically masks high-entropy strings (JWTs, API tokens) even if they aren't in the environment variables.
- **Elite Architecture (v3.6.7)**: Transitions the bot from a monolithic script to a professional **Staged Pipeline** (`Curation` → `Synthesis` → `Broadcast` → `Persistence`) using frozen dataclasses and a typed `Settings` singleton.
- **SSRF Prevention Logic**: The metadata scraper (`get_link_metadata`) uses **DNS Pinning** to prevent rebinding attacks and **IP Validation** to ensure the bot only connects to public, routable internet addresses.
- **Advisory File Locking**: Integrated cross-platform `FileLock` (supporting both `fcntl` on Unix and `msvcrt` on Windows) for all state persistence operations, ensuring 100% integrity for `seen_articles.json`.
- **Zero-Clobber Persistence**: Uses a linear rebase-and-push strategy on the `automated/state` branch with `--autostash` to prevent dirty worktree aborts.
- **Zero-Duplicate Threads Strategy**: Wraps final Threads delivery in a "Catch & Log" block. If the response fails, it logs a warning instead of retrying the whole post, preventing accidental duplicate threads.
- **The Fortress**: Unified logging system that dynamically masks all environment secrets and tokens.

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

## 💾 Page 8: Linear State Persistence

To protect your "Seen Articles" history on a restricted repository, the bot uses a dedicated `automated/state` branch.

### The 'Zero-Clobber' Strategy
1. **Concurrency Guard**: Ensures only one bot run updates the state at a time.
2. **Autostash Rebase**: Performs `git pull --rebase --autostash` to merge `seen_articles.json` and `README.md` safely without workspace conflicts.

---
## 🧪 Page 9: Automated Quality Control (v3.6.5)

BluBot v3.6.5 introduces a professional **Automated Test Suite** powered by `pytest`.

### The Test Layers
1. **Security (SSRF)**: Every URL metadata fetch is automatically tested against private IP ranges and redirect-spoofing attacks.
2. **Intelligence (Scoring)**: The Breakthrough Scoring Engine weights are verified to ensure "Signal over Noise" remains mathematically consistent.
3. **Hardening (Redaction)**: The `SafeLogger` is tested against high-entropy string detection to ensure no API keys leak into production logs.

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
*Built with ❤️ for the AI Community*
