# 👨‍🔧 BluBot: Elite AI News Curator

Automated AI news curator that fetches updates twice daily, synthesizes them using **Sage Intelligence (Multi-Model Failover)**, and broadcasts insightfully to **Bluesky**, **Mastodon**, and **Threads**—all running entirely for free on **GitHub Actions**.

## 📊 System Status

See [STATUS.md](STATUS.md) for live telemetry and broadcaster status.

## 🚀 Key Features

- **Sage Intelligence v3 (Self-Healing AI)**: 
    - **Multi-Model Failover**: Automatically rotates through prioritized models (**`Gemini 3.1 Flash Lite`**, **`Gemma 4 31B/26B`**, **`Gemma 3 27B-IT`**) if the primary provider is saturated or fails validation.
    - **Self-Healing Loop**: Automatically corrects common AI output issues (e.g., missing hashtags) and **strips accidental markdown formatting** (bolding/italics) to ensure 100% clean posts.
    - **Self-Discovery Diagnostics**: If a model fails to validate, the bot automatically **logs every available model ID** for your key.
    - **Graceful Degradation**: If news volume is low or summarization fails, the bot intelligently degrades to "Mentor Fallback" mode.
- **🖼️ Self-Healing Image Generation**: 
    - **NVIDIA NIM Integration**: Uses **Stability AI Stable Diffusion 3 Medium** via NVIDIA's Inference Microservices as the primary image provider, bypassing the 100-run "Imagen restricted" blockers.
    - **Smart Image Compression**: Built-in **Pillow-powered optimizer** that automatically resizes thumbnails to platform-specific limits (fixing "blob too big" errors).
- **Elite Architecture (v3.8.2)**:
    - **🧵 The Weaver (Conditional Threading)**: Automatically chains high-resolution news analysis into platform-native threads.
        - *Smart Split Algorithm*: Intelligently segments text at priority boundaries (first `\n\n` for paragraphs, then `. ` for sentences, then spaces ` ` for words) instead of crude character cuts.
        - *Precision Buffers*: Implements safety offsets (`limit - 10` for Bluesky/Threads, `limit - 15` for Mastodon) to account for pagination suffixes (e.g. `(1/2)`) without API limit rejections.
        - *Thread Limits*: Enforces a strict `MAX_THREAD_PARTS=2` constraint to avoid feed fatigue, trailing summaries with `...` when truncated.
    - **🥁 Thread Rhythm (v3.8.1)**: Randomized 10-30s pauses between posts to simulate human narration and prevent burst-spam detection.
    - **🤖 Dynamic Bio Management (v3.11.0)**: Profiles now showcase an active day streak and the currently tracked topic (e.g., "AI signal, zero noise. Day 68. | Currently tracking: On-device agents").
    - **🛡️ Supply Chain Hardening (v3.8.2)**: Migrated to `pip-tools` with cryptographic hashes.
    - **📡 Feed Vanguard (v3.8.2)**: Automated RSS resilience engine that audits sources for health, silencing broken feeds with exponential backoff.
    - **Typed Pipeline Stages**: Immutable stages powered by frozen `dataclasses` and a typed `Settings` singleton.
    - **Advisory File Locking**: Cross-platform `FileLock` for state persistence, preventing race conditions during concurrent CI/local runs.
- **🛡️ Industrial Stabilization**: 
    - **Universal RGB Defense**: Image mode detection and conversion engine that prevents "Black/White Box" artifacts from non-standard (ArXiv) thumbnails.
    - **Resilient Rebase Logic**: Automated conflict resolution for `README.md` dashboards (using `git checkout --ours`) ensuring 100% state persistence uptime.
    - **Smart Truncation (v3.7.5)**: Word-boundary-aware trimming for Mastodon and Threads to prevent mid-word cutoffs.
- **Fortress Hardening (v3.9.0)**: 
    - **Non-Blocking I/O**: Offloads all disk persistence, social bio updates, status telemetry updates, and feed vanguard state saving to background worker threads via `asyncio.to_thread`.
    - **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield against decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
    - **Resilient RSS Parsing**: Parses raw bytes (`response.content`) and uses safe lookups to survive malformed feed entries.
    - **Structured JSON Logging**: Re-engineered `SafeLogger` to output machine-readable JSON with entropy-aware secret redaction (identifies keys by string-complexity), fixing `TypeError` formatting bugs for non-string args.
    - **SSRF Prevention Architecture**: Hardened the metadata scraper with **DNS Pinning** and **IP validation** to block all internal/private network requests.
    - **Zero-Duplicate Threads Logic**: Implemented "Catch & Log" delivery validation to prevent duplicate posts during transient API failures.
- **🧠 Natural Vibe Engine (v3.7.0)**:
    - **Stylistic Memory**: The bot now remembers its previous "vibe" and ensures it never repeats the same tone twice in a row, switching between **Analytical**, **Practical**, **Sage**, **Concise**, and **Philosophical** dialects.
    - **Temporal Intelligence**: Upgraded from 2 to **5 granular sessions** (Dawn, Morning, Midday, Afternoon, Evening) for hyper-relevant time-of-day awareness.
    - **Manual Run "Intercept"**: Automatically detects manual `workflow_dispatch` runs and labels them as **"(Intercept)"**, shifting the AI into an urgent, ad-hoc reporting mode.
- **💬 Interaction Engine (v3.11.0)**:
    - **Configurable Comments & Replies**: Platforms can have comments/replies toggled independently (Bluesky `true`, Mastodon/Threads `false` by default).
    - **24-Hour Lookback Filters**: Strict timestamp boundaries filter out notifications/comments older than 24 hours to prevent scanning entire profile histories.
    - **Token Optimization**: Disables thinking models and imposes a hard limit of `100` max output tokens for replies to minimize latency and token overhead.
    - **Conversational Quality & Persona**: System prompts are highly tailored to speak in a natural, peer-like mentor/analyst voice, stripping robotic introductory pre-ambles and hashtags.
- **Breakthrough Scoring Engine v3 (Elite Signal Processing)**: 
    - **Weighted Curation Matrix**:
        
        | Factor / Signal | Weight / Modification | Notes |
        | :--- | :--- | :--- |
        | **Tier 1 Sources** | `+30` | Top-tier AI Labs (OpenAI, DeepMind, etc.) |
        | **Hidden Gems / Tier 3** | `+15` | Research/Academic (ArXiv, BAIR, Stanford) |
        | **Tier 2 Sources** | `+15` | Elite Analysts & Newsletters |
        | **High-Signal Keywords** | `+12` | Boosts *SOTA, agentic, world model, open weights*, etc. |
        | **Momentum Products** | `+18` | Boosts *GPT-5, Llama 4, Gemini 3, Gemma 4*, etc. |
        | **Consensus Synergy** | `+15` | Story present across multiple independent feeds |
        | **Topic Diversity Penalty**| `-12` * | Applied if topic is in recent_topics (config lists penalty as `25`) |
        | **Time Decay** | `-0.5` / hour | Linearly decays relevance score over time |
    - **Curated Feed Network**: **32 active feeds** across 4 tiers (AI Labs, Elite Analysts, Research, Journalism), dynamically audited for freshness.


## 🛠️ Setup Instructions

### ⚙️1. Platform Credentials

#### Bluesky & Mastodon
Standard API Access (See [WIKI](docs/WIKI_MANUAL.md)).

#### NVIDIA AI (Required for v3.6+)
- Get a free API key from [build.nvidia.com](https://build.nvidia.com/).
- Integrated for **Stable Diffusion 3 Medium**.

#### Google Gemini
- Get a free API key from [Google AI Studio](https://aistudio.google.com/).

### 🤫2. Configure GitHub Secrets

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `BSKY_HANDLE` | **Yes** | Your Bluesky handle |
| `BSKY_APP_PASSWORD` | **Yes** | Your Bluesky App Password |
| `GEMINI_KEY` | **Yes** | Your Google Gemini API Key (also used for Active Model Discovery) |
| `NVIDIA_KEY` | **Yes** | Your NVIDIA API Key (for SD3) |
| `THINKING_BUDGET` | No | (Optional) Thinking budget for Gemini 2.0/2.5 models (default: 1024; bypassed for Gemma) |
| `GEMINI_MODEL` | No | (Optional) Primary model used for interactive replies (default: `models/gemini-2.5-flash-lite`) |
| `IMAGE_PROVIDER` | No | Default: `nvidia`. Set to `imagen` to switch back. |
| `MASTODON_ACCESS_TOKEN` | No | Your Mastodon Access Token |
| `MASTODON_BASE_URL` | No | Your Mastodon Instance URL |
| `THREADS_ACCESS_TOKEN` | No | Your Threads Long-Lived Access Token |
| `THREADS_USER_ID` | No | Your Threads User ID |
| `GIST_ID` | No | (Optional) Private GitHub Gist ID for remote state |
| `GIST_TOKEN` | No | (Optional) GitHub PAT with `gist` scope |
| `ENABLE_BSKY_COMMENT_REPLIES` | No | (Optional) Enable/disable replying to comments on Bluesky (default: `true`) |
| `ENABLE_MASTODON_COMMENT_REPLIES` | No | (Optional) Enable/disable replying to comments on Mastodon (default: `false`) |
| `ENABLE_THREADS_COMMENT_REPLIES` | No | (Optional) Enable/disable replying to comments on Threads (default: `false`) |
| `TELEGRAM_BOT_TOKEN` | No | (Optional) Your Telegram Bot API Token |
| `TELEGRAM_USER_ID` | No | (Optional) Your numeric Telegram User ID (for authentication) |
| `TELEGRAM_TIMEOUT_MINUTES` | No | (Optional) Telegram polling timeout in minutes (default: `5`) |
| `ENABLE_TELEGRAM_APPROVAL` | No | (Optional) Toggle Telegram draft approval (default: `true` if bot token set) |
| `ENABLE_HASHTAGS_BSKY` | No | (Optional) Enable/disable hashtags on Bluesky (default: `false`) |
| `ENABLE_HASHTAGS_MASTODON` | No | (Optional) Enable/disable hashtags on Mastodon (default: `true`) |
| `ENABLE_HASHTAGS_THREADS` | No | (Optional) Enable/disable hashtags on Threads (default: `true`) |

## 🛡️ Resilience Architecture

BluBot implements a **3-Tier State Persistence** system to ensure it never "forgets" which articles it has curated, even if local storage is wiped (e.g., in ephemeral CI environments).

```
[Load Sequence]
(Start) ──► [Tier 1: Read seen_articles.json (FileLocked)] ──(Success)──► (Load Done)
                  │
               (Corrupt / Missing)
                  ▼
            [Tier 2: Read seen_articles.json.bak] ──────────(Success)──► (Load Done)
                  │
               (Corrupt / Missing)
                  ▼
            [Tier 3: Pull GitHub Gist (GIST_ID)] ──────────(Success)──► (Load Done)
                  │
               (Missing Credentials / Fail)
                  ▼
            [Fallback: Empty Default State] ───────────────────────────► (Load Done)

[Save Sequence]
(Save State) ──► [Rotate: seen_articles.json to .bak]
                       ▼
                 [Write: temporary file seen_articles.json.tmp]
                       ▼
                 [Atomic Rename: .tmp to seen_articles.json]
                       ▼
                 [Remote Gist Sync: PATCH seen_articles.json to Gist]
```

1.  **Tier 1: Atomic Local Storage**: Primary state is saved using atomic writes (writing to `.tmp` first, then renaming) under advisory `FileLock` to prevent data corruption.
2.  **Tier 2: Automatic Local Backups**: On every save, the previous state is rotated to `seen_articles.json.bak`. If the primary file is corrupted, BluBot automatically restores from this backup.
3.  **Tier 3: Remote Gist Synchronization**: If `GIST_ID` and `GIST_TOKEN` are configured, BluBot pulls the state from a private GitHub Gist on startup and pushes updates back after each run. This acts as a "cloud memory" for the bot across ephemeral runner environments.


## 📂 Project Structure

- `bot.py`: Main Orchestrator (Staged Pipeline).
- `src/`: Modular logic layers (Config, Settings, Models, Logger, Curator, Utils, Broadcaster).
- `src/tests/`: **Automated Test Suite** (Security, Scoring, Redaction).
- `scripts/diagnostic.py`: **Interactive Diagnostic Suite** (Unified RSS & AI validation).

## 🗒️ Updates & History

- **v3.12.0 (Current)**: **Telegram Control, Alt-Text, and Hashtag Management**.
    - 🎮 **Telegram Control & Approval Queue**: Intercepts the post pipeline to request manual review (`[✅ Approve]`, `[❌ Reject]`) via a Telegram message. Automatically posts on timeout (default 5 minutes) to avoid runner hang-ups.
    - 📥 **On-Demand Topic Curation**: Send a message starting with `/topic <keyword>` or `/curate <keyword>` to your Telegram Bot. During its startup sequence, the bot checks for recent user commands (last 15 minutes) and curates a post specifically on that topic instead of the normal RSS loop.
    - ♿ **Alt-Text Generation**: Added Gemini Vision integration (`models/gemini-2.5-flash-lite`) to automatically generate descriptive, screen-reader-ready alt text (under 100 characters) for generated thumbnails, publishing to Mastodon and Threads.
    - 🏷️ **Platform Hashtags Toggle**: Adds toggleable configurations per platform to strip or keep hashtags depending on social norms (`ENABLE_HASHTAGS_BSKY=false` by default).
    - 🛡️ **Side-Effect-Free Dry-Run**: The `--dry-run` flag bypasses all external broadcasts, state file persistence, and live AI API calls (substituting mock summaries and alt-text) to enable offline local diagnostics.
- **v3.11.2**: **Supply Chain Resilience & Dependabot Mitigation**.
    - 🛡️ **Supply Chain Constraints**: Adjusted `cryptography` range dependency in `requirements.in` to `>=46.0.7,<47` to comply with the transitive constraint restrictions of the `atproto` SDK client library.
    - 🤖 **Dependabot Security Gates**: Configured Dependabot to ignore version upgrades `>= 47.0.0` for `cryptography`, resolving the unresolvable dependency updater loop while keeping active path checks.
- **v3.11.1**: **Refactored Persistence & Humanized Short-Form Prompts**.
    - 🛠️ **Refactored Persistence Helpers**: Integrated generic `load_json_state` and `save_json_state` functions in `src/utils.py` to consolidate local state storage and prevent duplicate code.
    - 🔒 **Performance Optimization**: Moved the regular expression compilation inside `strip_markdown` in `src/curator.py` to module scope.
    - ✍️ **Humanized Short-Form Prompts**: Overhauled `CURATOR_SYSTEM_INSTRUCTION` and dialect descriptions to target engaging, short-form posts (260-290 characters) naturally, avoiding buzzwords/clichés and adding anti-patterns and strategic structures.
    - 📁 **Repository Ignorance**: Added `graphify-out/` to `.gitignore` to prevent local graph visualizations from polluting Git tracking.
- **v3.11.0**: **Dynamic Bio Engagement & Precision Counting**.
    - 🤖 **Dynamic Bio Overhaul**: Profiles now display an active day count (streak) and the currently tracked topic instead of raw/confusing stats.
    - 📊 **Accurate Post Incrementing**: Fixed a logic bug where `total_posts_curated` was incremented by the raw incoming article count rather than the actual published synthesis posts.
- **v3.10.1**: **Curation Script Hardening & Documentation Sync**.
    - 🔒 **Weekly Curation Hardening**: Added structured Pydantic response schemas and robust regex-based JSON boundary extraction to `update_config_keywords.py` to prevent JSON decode failures. Added API key environment guards.
    - 📖 **Documentation Synchronization**: Updated `README.md` and manual wiki with exact scoring engine weights, 3-tier persistence flowcharts, Weaver splits, and comment system configurations.
- **v3.10.0**: **Configurable & Token-Efficient Comment Replies**.
    - 🧶 **The Weaver Cap**: Limited multi-post threads to a strict 2-part maximum to maintain high signal-to-noise.
    - 🛡️ **Character Safety**: Implemented pagination buffers to prevent platform character limit rejections (Mastodon/Threads).
    - 🎨 **Sage Console**: Introduced human-friendly, colorized logging for local development (toggleable via `LOG_FORMAT`).
    - ⚡ **Failover Resilience**: Hardened AI synthesis with 503 retry delays and robust model rotation.
- **v3.8.4**: **Final Infrastructure & Security Hardening**.
    - 🛡️ **Harden Masking**: Relocated session metadata masking to the absolute first step of CI to prevent ID leaks in logs.
    - 🛠️ **Universal Manual Bypass**: Extended scheduling logic to regard ALL non-scheduled events (Push/Dispatch/PR) as manual runs, ensuring zero weekend development blocks.
- **v3.8.3**: **Infrastructure Modernization**.
    - 🐍 **Python 3.13 Upgrade**: Realigned the entire CI/CD pipeline and delivery environment to Python 3.13.
    - ⚡ **Node.js 24 Actions**: Migrated to `actions/checkout@v6`, `actions/setup-python@v6`, and `actions/cache@v5`.
- **v3.8.2**: **Hardening, Humanization & The Interaction Engine**.
    - 🛡️ **Feed Vanguard**: Automated RSS resilience engine with soft-disable backoff and pre-flight auditing.
    - 💬 **Interactive Sage**: Conversational AI (Mention Replies) for Bluesky and Mastodon with persona-aligned logic.
    - 🛰️ **Elite Expansion**: Added high-signal sources: **AlphaSignal**, **TLDR AI**, and **TheSequence**.
    - 🔒 **Supply Chain Hardening**: Transitioned to `pip-tools` for strict dependency locking with hashes.
    - 🐛 **Bug Remediation**: Resolved critical P0/P1 issues in threading and broadcaster logic.
    - **Thread Rhythm**: Implemented randomized pauses between thread posts.
    - **Dynamic Bio**: Profiles now update automatically with live curation telemetry.
- **v3.8.0**: **The Weaver & Resilience Engine**.
    - **The Weaver**: Integrated a conditional multi-post threading engine with paragraph-aware `smart_split` logic.
    - **Narrative Expansion**: Expanded AI synthesis capacity to 1000 characters to leverage the new multi-post architecture.
    - **3-Tier Persistence**: Implemented a redundant state model (Primary → Local Backup → Remote Gist) with automatic corruption recovery.
    - **Dashboard Migration**: Moved high-churn telemetry to a dedicated `STATUS.md` to eliminate Git rebase conflicts in CI.
    - **CI Hardening**: Resolved "EDITOR unset" rebase failures in GitHub Actions.
- **v3.7.6**: **Visual Integrity Hardening**.
    - **Black/White Box Fix**: Implemented universal `RGB` mode conversion in the compression engine to prevent corrupted renders on ArXiv-style links.
    - **Fidelity Guards**: Hardened broadcasting logic to ensure atomic image delivery and graceful text fallbacks to prevent placeholder distortions.
- **v3.7.5**: **Content & Infrastructure Optimization**.
    - **Smart Truncate**: Implemented word-boundary-aware truncation for Mastodon and Threads to prevent mid-word cutoffs.
    - **Persistence Hardening**: Resolved automated `README.md` rebase conflicts and implemented session ID masking in CI logs.
- **v3.7.3**: **Stabilization & Visibility Patch**.
    - **Stability Fix**: Restored the missing `published` timestamp in the curation engine to satisfy `Article` model requirements.
    - **Session Visibility**: Enhanced the broadcast stage with explicit logging for Bluesky session cache restoration.
- **v3.7.2**: **Production Hardening Patch**.
    - **Model Stability**: Resolved a critical `TypeError` in the Article dataclass by supporting diagnostic `_score_debug` metadata.
    - **Infra Alignment**: Updated GitHub Actions environment to cleanly support Node.js 24 runners.
- **v3.7.0**: **The Natural Vibe Engine Release**.
    - **Style Memory**: Integrated stylistic persistence to ensure editorial variety between consecutive runs.
    - **Session Granularity**: Increased temporal resolution to 5 sessions with manual intercept awareness.
    - **Architectural Cleanup**: Formalized absolute `src.` imports across the entire project, resolving `pytest` isolation issues.
- **v3.6.7**: **Elite Architecture Overhaul**.
    - **Staged Pipeline**: Refactored `bot.py` into distinct functional stages powered by `src/models.py`.
    - **Typed Settings**: Centralized configuration into `src/settings.py` for professional-grade environment management.
    - **Thread-Safe State**: Integrated cross-platform `FileLock` for robust state persistence and atomic `seen_articles.json` writes.
    - **Refined Normalization**: Resolved protocol-relative links (//) and stripped aggressive tracking queries while preserving redirect integrity (P1 Codex fix).
- **v3.6.5**: **Hardening & Automated Quality Control**.
- **v3.6.4**: **Threads & Documentation Sync**.
    - **Failure Propagation**: Hardened Threads publishing to correctly signal delivery failures to the orchestrator.
- **v3.6.3**: **Threads Stability Patch**.
    - **Zero-Duplicate Strategy**: Implemented initial Threads delivery validation.
- **v3.6.0**: **NVIDIA NIM Image Integration**.
    - Bypassed Imagen 4 restrictions by moving to NVIDIA SD3.
    - Added interactive console input for keys in `scripts/diagnostic.py`.
- **v3.5.12**: **Persistence & Retry Hardening**.
    - Implemented `--autostash` for state updates and branch bootstrapping logic.
    - Narrowed retry behavior to skip terminal 403/400 errors.
## 🧪 Testing

BluBot v3.6.5 features a dual-layer testing strategy:

### 1. Automated Regression (CI-Ready)
Run the professional test suite via `pytest`:
```bash
pytest src/tests/
```
Targeting **SSRF protection**, **Scoring fidelity**, and **Secret redaction**.

### 2. Interactive Diagnostic (Developer Tool)
Run the playground to see manual scoring breakdowns and AI drafts:
```bash
python scripts/diagnostic.py
```

---

## 🤝 Community & Security
- **Wiki**: Find the full technical blueprint in the [Elite Sage Manual](docs/WIKI_MANUAL.md).

*Built with ❤️ for the AI Community*
