# 👨‍🔧 BluBot: Elite AI News Curator

Automated AI news curator running a three-slot weekday experiment, synthesizing updates with multi-model failover and broadcasting to **Bluesky**, **Mastodon**, and **Threads** from **GitHub Actions**.

## 📊 System Status

See [STATUS.md](STATUS.md) for live telemetry and broadcaster status.

## 🚀 Key Features

- **Sage Intelligence v3 (Self-Healing AI)**:
    - **Multi-Platform Differentiation**: Generates tailored drafts for **Bluesky** (direct, specific observation), **Threads** (conversational explanation), and **Mastodon** (technical overview with hashtags) in a single request. Questions are optional, not forced.
    - **Interactive Telegram Review & Post-Broadcast Transparency**: Interactive inline tab switcher (`[🔵 Bluesky] [🧵 Threads] [🐘 Mastodon]`) and All-in-One inspection. Allows conversational editing via replies (`remix_platform_draft`), in-place caption updates within strict 1,024-character limits, and link-safe deterministic truncation. Following broadcast, dispatches 3 dedicated plain-text messages to Telegram detailing publication status (`✅ Published`, `❌ Failed`, `⚪ Not configured / not attempted`), requested delivery mode, and the approved draft variant sent to each network.
    - **Multi-Model Failover**: Automatically rotates through prioritized models (**`gemini-3.5-flash-lite`** → **`gemini-3.7-flash`** → **`gemini-3.6-flash`** → **`gemini-2.5-flash-lite`**) with immediate status-aware rotation (503, 429, 400, 404) and local deterministic topic derivation.
    - **Task-Specific Routing**: Dedicated multimodal models (`gemini-3.5-flash-lite`, `gemini-2.5-flash-lite`) handle screen-reader alt-text with MIME detection and a neutral local fallback. `gemini-3.5-flash-lite` handles visual prompts; `GEMINI_MODEL` handles interactive replies and `/brief` synthesis.
    - **Output Repair**: Strips accidental markdown formatting, applies platform-specific hashtag policy, and repairs overlong output without splitting URLs.
    - **Model Discovery**: Lists the models available to the configured key and keeps only exact matches from the approved priority list; if discovery fails, the defaults remain available for runtime failover.
    - **Graceful Degradation**: If news volume is low or summarization fails, the bot intelligently degrades to "Mentor Fallback" mode.
- **🖼️ Unified Media Strategy Stage**:
    - **Single Media Decision Point**: Decides if a post should contain media, extracts and validates OpenGraph metadata, generates a visual prompt, uses the configured image-provider fallback chain when necessary, and compiles everything into a single `MediaAsset`.
    - **Self-Healing OpenGraph Validation**: Runs multi-criteria validation (dimensions, size, aspect ratios, decoding, known placeholder logo patterns) before selecting.
    - **Platform-Specific Adaptors**: Intelligently renders the canonical `MediaAsset` according to platform requirements:
        - *Bluesky*: Uses `AppBskyEmbedExternal` for link cards and `AppBskyEmbedImages` for scratch posts.
        - *Mastodon*: Uploads image bytes, degrading gracefully to text on upload errors.
        - *Threads*: Renders OpenGraph public URLs only, gracefully falling back to text-only mode for generated assets lacking public hosting.
    - **Configurable Image Fallbacks**: Defaults to **Cloudflare Workers AI (FLUX.1 Schnell)**, then falls back to **Pollinations** and **Hugging Face**. Imagen runs only when explicitly selected.
    - **Smart Image Compression**: Built-in **Pillow-powered optimizer** that automatically resizes thumbnails to platform-specific limits (fixing "blob too big" errors).
- **Elite Architecture**:
    - **🧵 The Weaver (Conditional Threading)**: Automatically chains high-resolution news analysis into platform-native threads.
        - *Smart Split Algorithm*: Intelligently segments text at priority boundaries (first `\n\n` for paragraphs, then `. ` for sentences, then spaces ` ` for words) instead of crude character cuts.
        - *Precision Buffers*: Implements safety offsets (`limit - 10` for Bluesky/Threads, `limit - 15` for Mastodon) to account for pagination suffixes (e.g. `(1/2)`) without API limit rejections.
        - *Thread Limits*: Enforces a strict `MAX_THREAD_PARTS=2` constraint to avoid feed fatigue, trailing summaries with `...` when truncated.
    - **🥁 Thread Rhythm**: Randomized 10-30s pauses between posts to simulate human narration and prevent burst-spam detection.
    - **🤖 Dynamic Bio Management**: Profiles now showcase an active day streak and the currently tracked topic (e.g., "AI signal, zero noise. Day 68. | Currently tracking: On-device agents").
    - **🛡️ Supply Chain Hardening**: Uses a Python 3.13 lockfile generated from the reviewed direct dependencies in `requirements.in` with `uv`.
    - **📡 Feed Vanguard**: Single-fetch RSS resilience engine with authoritative Gist state persistence (`feed_vanguard.json` in the Gist, local cache `broken_feeds.json`), eliminating duplicate network passes and silencing broken feeds with exponential backoff.
    - **Typed Pipeline Stages**: Immutable stages powered by frozen `dataclasses` and a typed `Settings` singleton.
    - **Advisory File Locking**: Cross-platform `FileLock` for state persistence, preventing race conditions during concurrent CI/local runs.
- **🛡️ Industrial Stabilization**:
    - **Universal RGB Defense**: Image mode detection and conversion engine that prevents "Black/White Box" artifacts from non-standard (ArXiv) thumbnails.
    - **Isolated Status Sync**: Scheduled runs write `STATUS.md` to `automated/state`; a separate workflow copies that file to `main` through the GitHub Contents API.
    - **Smart Truncation**: Word-boundary-aware trimming for Mastodon and Threads to prevent mid-word cutoffs.
- **Fortress Hardening**:
    - **Non-Blocking I/O**: Offloads all disk persistence, social bio updates, status telemetry updates, and feed vanguard state saving to background worker threads via `asyncio.to_thread`.
    - **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield against decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
    - **Resilient RSS Parsing**: Parses raw bytes (`response.content`) and uses safe lookups to survive malformed feed entries.
    - **Structured JSON Logging**: Re-engineered `SafeLogger` to output machine-readable JSON with entropy-aware secret redaction (identifies keys by string-complexity), fixing `TypeError` formatting bugs for non-string args.
    - **SSRF Prevention Architecture**: Hardened the metadata scraper with **IP Pinning** (connects to the validated IP with the original `Host` and TLS name) and **IP validation** to block all internal/private network requests.
    - **Zero-Duplicate Threads Logic**: Implemented "Catch & Log" delivery validation to prevent duplicate posts during transient API failures.
- **🧠 Natural Writing Engine**:
    - **Shared Editorial Voice**: Synthesis, mentor posts, remixes, replies, and briefings use one compact policy: source-grounded facts, direct verbs, plain language, varied sentence rhythm, and no forced questions, fake revelations, binary contrasts, or recap endings.
    - **Content-Angle Memory**: The bot avoids repeating the previous analytical, practical, strategic, concise, or trade-off angle while keeping one consistent peer-like voice.
    - **Temporal Intelligence**: Upgraded from 2 to **5 granular sessions** (Dawn, Morning, Midday, Afternoon, Evening) for hyper-relevant time-of-day awareness.
    - **Manual Run "Intercept"**: Automatically detects manual `workflow_dispatch` runs and labels them as **"(Intercept)"**, shifting the AI into an urgent, ad-hoc reporting mode.
- **💬 Interaction Engine**:
    - **Configurable Comments & Replies**: Platforms can have comments/replies toggled independently (Bluesky `true`, Mastodon/Threads `false` by default).
    - **24-Hour Lookback Filters**: Strict timestamp boundaries filter out notifications/comments older than 24 hours to prevent scanning entire profile histories.
    - **Token Optimization**: Disables thinking models and imposes a hard limit of `100` max output tokens for replies to minimize latency and token overhead.
    - **Conversational Quality**: Replies address the actual comment as a peer, without persona introductions, canned thanks, hashtags, or forced broader lessons.
- **Breakthrough Scoring Engine v5 (Elite Signal Processing)**:
    - **Stable-ID Curation Registry (8-Tier, 45 Feeds)**:

        | Source Category | Base Score | Notes / Source Tiers |
        | :--- | :--- | :--- |
        | **Research Labs** | `+30` | OpenAI, DeepMind, HuggingFace |
        | **Enterprise AI** | `+25`–`+27` | Microsoft Research, AWS ML, NVIDIA Deep Learning |
        | **Practitioner** | `+20` | Simon Willison, Interconnects, Latent Space, One Useful Thing, Sebastian Raschka, Jack Clark, Maarten Grootendorst |
        | **Open Source** | `+18` (GitHub Fast-Rising: `+16`) | Hugging Face Transformers Releases, vLLM, Ollama, PyTorch, Hugging Face Trending (API), GitHub Fast-Rising Repositories (API) |
        | **Infrastructure/Business** | `+15` | SemiAnalysis, Together AI, ServeTheHome, Semiconductor Engineering, Sequoia, CB Insights |
        | **Journalism** | `+12` | The Verge, Wired, MIT Tech Review, TechCrunch, VentureBeat, IEEE Spectrum, The Decoder, 404 Media, Silicon Angle, The Sequence, Marktechpost, AI Accelerator Institute |
        | **Academic** | `+10` | arXiv CS.LG, The Gradient, BAIR Blog, ML Mastery |
        | **Critical / Policy & Security** | `+5`–`+10` | AI Incident Database and EU AI Act Tracker (`+10`); AI Snake Oil, Gary Marcus, Algorithmic Bridge, Victoria Krakovna (`+5`) |
    - **Curation Boosts & Penalties**:
        - **High-Signal Keywords**: `+12` (Boosts *SOTA, agentic, world model, open weights*, etc.)
        - **Momentum Products**: `+18` (The weekly workflow refreshes the current product list in `src/config.py`.)
        - **Consensus Synergy (Story Clustering)**: `+15` (Awarded when stories from ≥2 distinct publisher domains cluster together based on title normalization and headline similarity)
        - **Watchlist Boost**: `+3` to `+8` (Bounded boost for articles matching user-defined `/watch` topics via word-boundary regex matching against title and summary text)
        - **Time Decay**: `-0.5` / hour (Linearly decays relevance score over time)
        - **Progressive Recency-weighted Category Penalty**: Automatically applies a penalty decay for recurring categories to keep feeds varied.
    - **Writing-Style Rotation**: Least-Recently-Used (LRU) selection across 4 content structures: strategic shift, practical workflow, risk/verification, and enterprise ROI.
    - **Curated Source Network**: **45 RSS feeds plus two API sources** (Hugging Face Trending and GitHub Fast-Rising Repositories) across 8 tiers, with API sources excluded from RSS health tracking.
    - **Bluesky Source Receipts**: Optionally replies to corroborated Bluesky posts with up to two aligned source links, only after the root publication has been durably settled.
    - **Friday Evening Roundup**: Automatically replaces the scheduled Friday 18:17 UTC broadcast with a weekly digest summarizing the top 1–5 stories published during the ISO week, ranked by live Bluesky engagement and threaded with exact URL preservation. Skips if already published or reserved, and falls back to normal curation if zero eligible stories are found. Can be triggered manually with `--roundup`.


## 🛠️ Setup Instructions

### ⚙️1. Platform Credentials

#### Bluesky & Mastodon
Standard API Access (See [WIKI](docs/WIKI_MANUAL.md)).

#### Cloudflare Workers AI, Pollinations & Hugging Face
- Cloudflare Workers AI is the default image provider. Create a scoped Workers AI API token and copy your Cloudflare Account ID.
- Pollinations is free and requires no API key.
- Hugging Face remains the final fallback when a token with **Inference** permissions is configured.

#### Google Gemini
- Get a free API key from [Google AI Studio](https://aistudio.google.com/).

### 🤫2. Configure GitHub Secrets

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `BSKY_HANDLE` | **Yes** | Your Bluesky handle |
| `BSKY_APP_PASSWORD` | **Yes** | Your Bluesky App Password |
| `GEMINI_KEY` | **Yes** | Your Google Gemini API Key (also used for Active Model Discovery) |
| `CLOUDFLARE_ACCOUNT_ID` | No | Cloudflare account used for Workers AI image generation; required for the default provider |
| `CLOUDFLARE_API_TOKEN` | No | Scoped API token with Workers AI permissions; required for the default provider |
| `POLLINATIONS_API_KEY` | No | Deprecated compatibility setting; the current Pollinations request does not use it |
| `HUGGINGFACE_API_KEY` | No | Hugging Face token with **Inference** permissions; used by the final fallback |
| `HUGGINGFACE_IMAGE_MODEL` | No | Hugging Face model (default: `stabilityai/stable-diffusion-3-medium-diffusers`) |
| `THINKING_BUDGET` | No | (Optional) Thinking budget for Gemini 2.0/2.5 models (default: 1024; bypassed for Gemma) |
| `GEMINI_MODEL` | No | (Optional) Model used for interactive replies, on-demand topics, and `/brief` synthesis (default: `models/gemini-3.5-flash-lite`) |
| `IMAGE_PROVIDER` | No | Default: `cloudflare`. Options: `cloudflare`, `pollinations`, `huggingface`, `nvidia`, `imagen`. Imagen is explicit-only. |
| `NVIDIA_KEY` | No | NVIDIA image API key; also retained as a legacy token fallback for Hugging Face |
| `POLLINATIONS_API_URL` | No | Override the Pollinations image endpoint |
| `ENABLE_IMAGE_GEN` | No | Enable generated-image fallbacks (default: `true`) |
| `ENABLE_BIO_MGMT` | No | Enable profile bio updates (default: `true`) |
| `ENABLE_INTERACTIONS` | No | Enable mention/comment processing (default: `true`) |
| `MAX_THREAD_PARTS` | No | Maximum posts in a platform thread (default: `2`) |
| `LOG_FORMAT` | No | `pretty` locally or `json` in CI by default |
| `MASTODON_ACCESS_TOKEN` | No | Your Mastodon Access Token |
| `MASTODON_BASE_URL` | No | Your Mastodon Instance URL |
| `THREADS_ACCESS_TOKEN` | No | Your Threads Long-Lived Access Token |
| `THREADS_USER_ID` | No | Your Threads User ID |
| `GIST_ID` | No | (Optional) Private GitHub Gist ID for remote state |
| `GIST_TOKEN` | No | (Optional) GitHub PAT with `gist` scope |
| `GITHUB_TOKEN` | No | (Optional) GitHub Token (PAT or automatic Actions `${{ secrets.GITHUB_TOKEN }}`) for higher REST API limits (1,000 req/hr) when fetching fast-rising repositories |
| `ENABLE_BSKY_COMMENT_REPLIES` | No | (Optional) Enable/disable replying to comments on Bluesky (default: `true`) |
| `ENABLE_MASTODON_COMMENT_REPLIES` | No | (Optional) Enable/disable replying to comments on Mastodon (default: `false`) |
| `ENABLE_THREADS_COMMENT_REPLIES` | No | (Optional) Enable/disable replying to comments on Threads (default: `false`) |
| `TELEGRAM_BOT_TOKEN` | No | (Optional) Your Telegram Bot API Token (supports commands: `/topic`, `/curate`, `/news`, `/watch`, `/unwatch`, `/watches`, `/brief`). See [Telegram Command Reference](#-telegram-command-reference) below. |
| `TELEGRAM_USER_ID` | No | (Optional) Your numeric Telegram User ID (for authentication) |
| `TELEGRAM_TIMEOUT_MINUTES` | No | (Optional) Telegram polling timeout in minutes (default: `5`) |
| `ENABLE_TELEGRAM_APPROVAL` | No | (Optional) Toggle Telegram draft approval (default: `true`; has no effect without a bot token and user ID) |
| `REPO_TOKEN` | No | (Optional) PAT used by `weekly_config_update.yml` and `sync_status.yml` so pull requests and `STATUS.md` syncs trigger required checks |
| `DRY_RUN` | No | (Optional, local use) `true` skips all external posting/persistence and injects mock credentials |
| `ENABLE_HASHTAGS_BSKY` | No | (Optional) Enable/disable hashtags on Bluesky (default: `false` — hashtags stripped to keep Bluesky posts clean) |
| `ENABLE_HASHTAGS_MASTODON` | No | (Optional) Enable/disable hashtags on Mastodon (default: `true`) |
| `ENABLE_HASHTAGS_THREADS` | No | (Optional) Enable/disable hashtags on Threads (default: `true`) |

### Repository Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_SOURCE_RECEIPTS_BSKY` | `false` | Reply to corroborated Bluesky posts with up to two source links after durable settlement |
| `STORY_UPDATE_DETECTION_ENABLED` | `false` | Enable automated story continuity detection and threaded update replies (Bluesky, Mastodon, Threads) |


## 🛡️ Resilience Architecture

BluBot implements a **Gist-Authoritative 3-Tier Persistence** system to reduce stale state and duplicate posts across ephemeral CI environments.

```
[Load Sequence]
(Start) ──► [Check GIST_ID & GIST_TOKEN] ──(Configured)──► [Pull Remote Gist State]
                  │                                                │
           (Not Configured)                              (Revision Comparison)
                  ▼                                                ▼
     [Tier 1: Local primary file] ◄──────── (Local Revision > Gist) ┘
                  │
          (Corrupt/Missing)
                  ▼
     [Tier 2: Local backup .bak]
                  │
          (Corrupt/Missing)
                  ▼
     [Fallback: Sanitized Schema v2 Default]

[Two-Phase Broadcast Sequence]
(Pre-Broadcast)  ──► Write Pending Story Reservation to Gist/Local State ──► Abort if Gist Write Fails
(Broadcast)      ──► Execute Multi-Platform Broadcast
(Post-Broadcast) ──► If any platform succeeds: Transition Reservation to 'published'
                 ──► If all platforms fail: Clear Pending Reservation & Exit Nonzero
```

1. **Gist-Authoritative Runtime State**: When `GIST_ID` and `GIST_TOKEN` are set, GitHub Gist is loaded as the primary state source. State comparison uses `schema_version: 2`, `revision`, and `updated_at` timestamps to prefer newer Gist state over stale local or branch data. Writes are read-merge-write without a server-side version check: the Actions concurrency group serializes CI runs, but a local run against the live Gist can still overwrite a concurrent run's newer state, so use `DRY_RUN=true` locally.
2. **Two-Phase Pre-Broadcast Reservation Protocol**: Before publishing, BluBot writes a `pending_stories` reservation to Gist and local state. If Gist reservation fails, publication is aborted. If broadcast succeeds, status transitions to `published`. If broadcast fails, pending reservation is cleared.
3. **Local Primary & Backup Rotation**: Saves perform atomic writes (`.tmp` -> `seen_articles.json`) and rotate previous valid state to `.bak` under advisory `FileLock`. If Gist write fails during post-broadcast settlement, state is saved locally with `unsynced_gist: true` for recovery.
4. **Durable Published-Post Ledger**: Each settled publication appends a `published_posts` entry (canonical URL, title, supporting links, `published_at`, and per-platform root post references: Bluesky `uri`/`cid`, Mastodon/Threads `id`). Only platforms that succeeded and returned an ID are recorded. Unlike the 14-day `recent_stories` duplicate window, the ledger is capped at 500 entries and never time-pruned.



## 📂 Project Structure

- `bot.py`: Main Orchestrator (Staged Pipeline).
- `src/`: Modular logic layers (Config, Settings, Models, Logger, Curator, Utils, Broadcaster, Engagement, Feed Vanguard, Telegram Gateway).
- `src/tests/`: **Automated Test Suite** (Security, Scoring, Redaction).
- `scripts/diagnostic.py`: **Interactive Diagnostic Suite** (Unified RSS & AI validation).
- `scripts/build_archive.py`: **Static Site & RSS Builder** (Generates HTML archive and RSS 2.0 feed from ledger).
- `scripts/feed_audit.py`, `scripts/update_config_keywords.py`: **Feed audit & weekly config update** tooling.
- `scripts/test_telegram_setup.py`, `setup_threads.py`: **Telegram and Threads setup helpers**.

## 📡 Telegram Command Reference

| Command | Description |
| :--- | :--- |
| `/topic <keyword>` | Curate and broadcast a post on a specific topic, grounded against live RSS feeds |
| `/curate <keyword>` | Alias for `/topic` |
| `/news <headline> [https url]` | Report a **confirmed** event. Skips feed matching and drafts as fact from your headline plus the fetched page title/description (URL must be public https). Becomes the lead link; the ledger source is the URL host |
| `/watch <keyword>` | Add a topic to your persistent watchlist (max 10). Watched topics receive a bounded `+3` to `+8` scoring boost during curation |
| `/unwatch <keyword>` | Remove a topic from your watchlist |
| `/watches` | List all active watchlist topics |
| `/brief <keyword>` | Generate a **7-day executive briefing** for a topic. Fetches all RSS articles from the past 7 days, clusters corroborated stories, and synthesizes a Gemini-powered analytical report delivered directly to Telegram with no platform character limits |

> **Fail-closed approval:** posts from `/topic`, `/curate` and `/news` are never auto-published. If Telegram approval times out or errors, nothing is posted and the topic is re-queued in `pending_topic.json` (with its command kind) for the next run. Scheduled posts still auto-publish on timeout.

## 🗒️ Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.


## 🧪 Testing

BluBot uses automated regression tests plus an interactive diagnostic suite. The test count is intentionally not pinned here because coverage grows independently of releases.

### 1. Automated Regression (CI-Ready)
Run the test suite with the repository virtual environment:
```bash
.venv/bin/python -m pytest src/tests/
```
Targeting **SSRF protection**, **Scoring fidelity**, **Secret redaction**, **Story clustering**, **Watchlist boost scoring**, **Topic grounding**, **Telegram command parsing** (including `/news`, `/brief`, `/watch`, `/unwatch`), **Dry-run pipeline bypasses**, and **Media pipeline integrity**.

### 2. Interactive Diagnostic (Developer Tool)
Run the playground to see manual scoring breakdowns and AI drafts:
```bash
python scripts/diagnostic.py
```

---

## 🤝 Community & Security
- **Wiki**: Find the full technical blueprint in the [Elite Sage Manual](docs/WIKI_MANUAL.md).

*Built with ❤️ for the AI Community*
