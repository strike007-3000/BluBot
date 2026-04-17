# 👨‍🔧 BluBot: Elite AI News Curator

Automated AI news curator that fetches updates twice daily, synthesizes them using **Sage Intelligence (Multi-Model Failover)**, and broadcasts insightfully to **Bluesky**, **Mastodon**, and **Threads**—all running entirely for free on **GitHub Actions**.

## 📊 System Status
| Component | Status | Last Run | Mode |
|:---|:---|:---|:---|
| **Broadcaster** | Operational | 2026-04-18 | 🖼️ NVIDIA SD3 Generation |
| **Signal Strength** | Elite (Natural) | -- | -- |

## 🚀 Key Features

- **Sage Intelligence v3 (Self-Healing AI)**: 
    - **Multi-Model Failover**: Automatically rotates through prioritized models (**`Gemini 3.1 Flash Lite`**, **`Gemma 4 31B/26B`**, **`Gemma 3 27B-IT`**) if the primary provider is saturated or fails validation.
    - **Self-Healing Loop**: Automatically corrects common AI output issues (e.g., missing hashtags) and **strips accidental markdown formatting** (bolding/italics) to ensure 100% clean posts.
    - **Self-Discovery Diagnostics**: If a model fails to validate, the bot automatically **logs every available model ID** for your key.
    - **Graceful Degradation**: If news volume is low or summarization fails, the bot intelligently degrades to "Mentor Fallback" mode.
- **🖼️ Self-Healing Image Generation (v3.6)**: 
    - **NVIDIA NIM Integration**: Uses **Stability AI Stable Diffusion 3 Medium** via NVIDIA's Inference Microservices as the primary image provider, bypassing the 100-run "Imagen restricted" blockers.
    - **Smart Image Compression**: Built-in **Pillow-powered optimizer** that automatically resizes thumbnails to platform-specific limits (fixing "blob too big" errors).
- **Elite Architecture (v3.8.2)**:
    - **🧵 The Weaver (Conditional Threading)**: Automatically chains high-resolution news analysis into platform-native threads (Bluesky, Mastodon, Threads).
    - **🥁 Thread Rhythm (v3.8.1)**: Randomized 10-30s pauses between posts to simulate human narration and prevent burst-spam detection.
    - **🤖 Dynamic Bio Management (v3.8.1)**: Profiles now showcase live telemetry and curation statistics (e.g., "1,245 stories narrated | Voice: Analytical").
    - **🛡️ Supply Chain Hardening (v3.8.2)**: Migrated to `pip-tools` with cryptographic hashes.
    - **📡 Feed Vanguard (v3.8.2)**: Automated RSS resilience engine that audits sources for health, silencing broken feeds with exponential backoff.
    - **Typed Pipeline Stages**: Immutable stages powered by frozen `dataclasses` and a typed `Settings` singleton.
    - **Advisory File Locking**: Cross-platform `FileLock` for state persistence, preventing race conditions during concurrent CI/local runs.
- **🛡️ Industrial Stabilization (v3.7.6)**: 
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
- **Breakthrough Scoring Engine v3 (Elite Signal Processing)**: 
    - **Impact-Aware Intelligence**: Prioritizes breakthrough news (Agents, SOTA) and boosts articles mentioning flagship 2026 models.
    - **Consensus Synergy Pass**: Automatically boosts "Consensus Events" reported by multiple independent feeds.
    - **Curated Feed Network**: **28 validated feeds** across 4 tiers (AI Labs, Elite Analysts, Research, Journalism), audited for freshness and availability.

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

## 🛡️ Resilience Architecture (v3.8.0)

BluBot now implements a **3-Tier State Persistence** system to ensure it never "forgets" which articles it has curated, even if local storage is wiped (e.g., in ephemeral CI environments).

1.  **Tier 1: Atomic Local Storage**: Primary state is saved using atomic writes to prevent data corruption.
2.  **Tier 2: Automatic Local Backups**: On every save, the previous state is rotated to `seen_articles.json.bak`. If the primary file is corrupted, BluBot automatically restores from this backup.
3.  **Tier 3: Remote Gist Synchronization**: If `GIST_ID` and `GIST_TOKEN` are configured, BluBot pulls the state from a private GitHub Gist on startup and pushes updates back after each run. This acts as a "cloud memory" for the bot.

## 📂 Project Structure

- `bot.py`: Main Orchestrator (Staged Pipeline).
- `src/`: Modular logic layers (Config, Settings, Models, Logger, Curator, Utils, Broadcaster).
- `src/tests/`: **Automated Test Suite** (Security, Scoring, Redaction).
- `scripts/diagnostic.py`: **Interactive Diagnostic Suite** (Unified RSS & AI validation).

## 🗒️ Updates & History

- **v3.7.0 (Current)**: **The Natural Vibe Engine Release**.
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
python test_models.py
```

---

## 🤝 Community & Security
- **Wiki**: Find the full technical blueprint in the [Elite Sage Manual](docs/WIKI_MANUAL.md).

*Built with ❤️ for the AI Community*
