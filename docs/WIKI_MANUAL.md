# 📖 BluBot Elite Sage: The Complete Manual

Welcome to the official Wiki for the **Elite Sage** (BluBot). This guide balances the technical inner workings with the "Sage" persona's philosophy.

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

## 🧠 Page 2: Breakthrough Scoring Engine v5

The "Brain" of the bot ranked by a weighted matrix.

### The Curation & Scoring Pipeline

1. **Source Tiering (8-Tier Stable-ID Registry)**:
   - **Tier 1 (Research Labs)**: `+30` score boost.
   - **Tier 2 (Enterprise AI)**: `+25`–`+27` score boost.
   - **Tier 3 (Practitioner)**: `+20` score boost.
   - **Tier 4 (Open Source)**: `+18` score boost.
   - **Tier 5 (Infrastructure/Business)**: `+15` score boost.
   - **Tier 6 (Policy & Journalism)**: `+10`–`+12` score boost.
   - **Tier 7 (Academic)**: `+10` score boost.
   - **Tier 8 (Critical/Balancing)**: `+5` score boost.
2. **Signal Boosting**: `+12` boost if title or summary contains high-signal keywords (e.g. *SOTA, agentic, world model, open weights*, etc.).
3. **Momentum Product Boosting**: `+18` boost if title contains momentum products (e.g. *gpt-5, llama 4, gemini 3, gemma 4*, etc.).
4. **Consensus Synergy Pass (Story Clustering)**: `+15` synergy bonus added when stories from ≥2 distinct publisher domains cluster together based on title normalization and headline similarity.
5. **Watchlist Topic Boosting**: Bounded `+3` to `+8` boost for articles matching user-defined `/watch` topics. Uses word-boundary regex matching: `+8` for exact topic match in title, `+5` for keyword match in title, `+3` for keyword match in summary. Maximum boost across all watches capped at `+8`.
6. **Diversity Penalty**: Subtracts `-12` if the article's classified topic is already in `recent_topics` list, preventing repetition.
7. **Category Recurrence Penalty**: Progressive `-5` penalty step for each repeat of the same source category within a single run.
8. **Time Decay**: Subtracts `-0.5` score for each hour since the article's publication to keep the feed fresh.

---

## 🛡️ Page 3: Reliability & The Fortress

The Sage is designed to be **unbreakable**.

### Hardening Features
- **3-Tier State Resilience**: BluBot implements a redundant persistence model. If the primary `seen_articles.json` is corrupted or missing, it automatically falls back to a local `.bak` rotation and finally a remote **GitHub Gist**.
- **Structured Logging**: The `SafeLogger` uses Python's `logging` module with a custom `JsonFormatter` and `RedactionFilter`. It automatically masks high-entropy strings (JWTs, API tokens) using entropy and keyword matching to prevent leakages in CI.
- **Visual Integrity Defense**: Implements **Universal RGB Conversion** in the image engine (`compress_image`) to handle grayscale (ArXiv) and specialized modes (such as CMYK), converting them to RGB before compression to avoid solid black/white artifact regressions.
- **SSRF Prevention Logic**: The metadata scraper (`get_link_metadata`) uses **DNS Pinning** to lock down the hostname to pre-resolved IPs and **IP Validation** to ensure no private/internal network addresses are called (mitigating Server-Side Request Forgery).
- **Zero-Duplicate Threads Logic ("Catch & Log")**: Prevents duplicate postings during transient API failures or runner timeouts. If a stage fails after publishing partial thread contents, the exception is caught, logged, and state is immediately persisted with successfully broadcast post identifiers. This ensures that a subsequent run does not publish the same content again.
- **Decompression Bomb Protection**: Restricts Pillow's image loading engine (`Image.MAX_IMAGE_PIXELS`) to a maximum of `10,000,000` pixels to shield the app from memory exhaustion attacks when retrieving large media files.
- **Resilient RSS Parsing**: Rather than relying on string-based feed parser scraping, the engine reads raw bytes via `response.content` and performs graceful lookups on optional attributes (`getattr(entry, 'link', None)`) to tolerate malformed XML schemas.

---

## 🎨 Page 4: Pollinations & Hugging Face Image Generation

The Sage uses **Pollinations** (Flux) as the primary image provider with serverless **Hugging Face Inference Providers** (Flux Schnell) as the immediate fallback.

### The Designer & Image Pipeline

```
              [Scrape Article URL]
                       │
                       ▼
          [Check og:image in Metadata]
           /                        \
      (Found)                     (Not Found)
         ▼                            ▼
  [Normalize URL]            [Call Pollinations / Hugging Face]
         ▼                    (Generate Isometric Prompt)
  [Filter Generic Logos]              ▼
  (Skip if e.g. "arxiv-logo") [Convert Base64 to Bytes]
         ▼                            │
  [Download Original Image]           │
         │                            │
         └─────────────┬──────────────┘
                       │
                       ▼
            [RGB Mode Normalization]
          (Convert CMYK/Grayscale -> RGB)
                       │
                       ▼
            [Pillow Image Optimizer]
         (Scale JPEG quality down to 80-30%
          until file size is under 900 KB)
                       │
                       ▼
          [Broadcast to Platform APIs]
```

1. **Lead Selection & Scraper**: The metadata scraper extracts metadata tags like `og:image` from the target article.
2. **URL Normalization & Logo Filter**: Resolves protocol-relative link formats (e.g. `//site.com/img.png` to `https://site.com/img.png`) and checks the path against `GENERIC_IMAGE_PATTERNS`. If a site logo is detected, it is discarded.
3. **Pollinations & Hugging Face Generation (Fallback)**: If no original image is found, the system requests a minimalist isometric tech graphic prompt using the active Gemini model, then invokes the Pollinations API (falling back to Hugging Face serverless API) to generate the image.
4. **RGB Conversion**: Standardizes image mode representations by converting CMYK or Grayscale source images to standard RGB, preventing rendering distortions.
5. **Iterative Quality Compression**: Fits the binary payload under the strict 900KB platform upload cap. The optimizer iteratively scales JPEG quality down (from 85% to 30%, in steps of 10%) and writes to an in-memory buffer (`io.BytesIO()`) until the constraints are met.

---

## 📡 Page 5: Source Intelligence

Scanning exactly **45 premium feeds** across 8 tiers.

---

## ⚙️ Page 6: Technical Configuration

### Environment Secrets
| Variable | Description |
| :--- | :--- |
| `GEMINI_KEY` | Google AI Studio Key (also used for Active Model Discovery) |
| `POLLINATIONS_API_KEY` | Optional token for Pollinations custom accounts |
| `HUGGINGFACE_API_KEY` | Hugging Face Hub User Access Token |
| `HUGGINGFACE_IMAGE_MODEL` | Hugging Face model target (default: `stabilityai/stable-diffusion-3-medium-diffusers`) |
| `THINKING_BUDGET` | (Optional) Thinking budget for Gemini 2.0/2.5 models (default: 1024; bypassed for Gemma models) |
| `GEMINI_MODEL` | (Optional) Primary model used for interactive replies (default: `models/gemini-2.5-flash-lite`) |
| `BSKY_HANDLE` | Your Bluesky handle |
| `BSKY_APP_PASSWORD` | Bluesky App Password |
| `MASTODON_ACCESS_TOKEN` | Your Mastodon Access Token |
| `MASTODON_BASE_URL` | Your Mastodon Instance URL |
| `THREADS_ACCESS_TOKEN` | Your Threads Long-Lived Access Token |
| `THREADS_USER_ID` | Your Threads User ID |
| `GIST_ID` | Private GitHub Gist ID |
| `GIST_TOKEN` | GitHub Token with `gist` scope |
| `IMAGE_PROVIDER` | `huggingface` (default) or `pollinations` or `nvidia` or `imagen` |
| `TELEGRAM_BOT_TOKEN` | (Optional) Your Telegram Bot API Token |
| `TELEGRAM_USER_ID` | (Optional) Your numeric Telegram User ID (for authentication) |
| `TELEGRAM_TIMEOUT_MINUTES` | (Optional) Telegram polling timeout in minutes (default: `5`) |
| `ENABLE_TELEGRAM_APPROVAL` | (Optional) Toggle Telegram draft approval (default: `true` if bot token set) |
| `ENABLE_BSKY_COMMENT_REPLIES` | (Optional) Enable/disable replying to comments on Bluesky (default: `true`) |
| `ENABLE_MASTODON_COMMENT_REPLIES` | (Optional) Enable/disable replying to comments on Mastodon (default: `false`) |
| `ENABLE_THREADS_COMMENT_REPLIES` | (Optional) Enable/disable replying to comments on Threads (default: `false`) |
| `ENABLE_HASHTAGS_BSKY` | (Optional) Enable/disable hashtags on Bluesky (default: `false`) |
| `ENABLE_HASHTAGS_MASTODON` | (Optional) Enable/disable hashtags on Mastodon (default: `true`) |
| `ENABLE_HASHTAGS_THREADS` | (Optional) Enable/disable hashtags on Threads (default: `true`) |

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

---

## 🧪 Page 7: Local Testing & Interactive Diagnostics

The Sage provides a robust **Full Pipeline Dry Run** via `scripts/diagnostic.py`.

### Execution
```bash
python scripts/diagnostic.py
```

### 🎨 Sage Console (Logging)
As of **v3.8.5**, BluBot supports multiple logging formats:
- **`LOG_FORMAT=pretty`** (Default for local): Colored, human-friendly text.
- **`LOG_FORMAT=json`** (Default for CI): Structured JSON for long-term auditability.
*Note: Secret redaction remains active in BOTH modes.*
You can test the entire bot locally **without social media credentials**. 
1. **Interactive Entry**: If `GEMINI_KEY` or `NVIDIA_KEY` are missing from your `.env`, the script will prompt you to paste them in the console.
2. **Elite Rigidity**: The `Settings.from_env()` engine automatically injects "Mock" values for `BSKY_HANDLE` during dry runs, allowing you to verify synthesis logic with only AI keys.

Select **Option 2 (FULL PIPELINE DRY RUN)** to see a draft review of exactly what will be posted.

---

## 💾 Page 8: 3-Tier State Resilience


To ensure the Sage never "forgets" even in ephemeral runner environments, we use a tiered persistence model.

### The Recovery Sequence
1. **Remote Gist (Gist-Authoritative Cloud Memory)**: Syncs state with a private GitHub Gist using `schema_version: 2` revision tracking and updated timestamps.
2. **Two-Phase Pre-Broadcast Reservation Protocol**: Writes a `pending_stories` reservation to Gist/local state before broadcasting, aborting publication if Gist reservation fails, and transitioning to `published` upon success.
3. **Primary Local & Backup Rotation**: Saves perform atomic writes (`.tmp` -> `seen_articles.json`) and rotate previous valid state to `.bak` under advisory `FileLock`. If Gist write fails during settlement, local recovery state is saved with `unsynced_gist: true`.

---
## 🧪 Page 9: Automated Quality Control

BluBot v3.19.0 maintains a professional **Automated Test Suite** powered by `pytest` with **99 tests** across 12 modules.

### The Test Layers
1. **Security (SSRF)**: Every URL metadata fetch is automatically tested against private IP ranges and redirect-spoofing attacks.
2. **Intelligence (Scoring)**: The Breakthrough Scoring Engine weights are verified to ensure "Signal over Noise" remains mathematically consistent. Includes watchlist boost scoring and category penalty verification.
3. **Hardening (Redaction)**: The `SafeLogger` is tested against high-entropy string detection to ensure no API keys leak into production logs.
4. **Transparency (Diagnostic Scoring)**: The curation engine attaches `_score_debug` metadata to every article, providing a granular breakdown (Source, Signal, Momentum, Watchlist, Penalty, Category Penalty, Decay) visible during dry-runs.
5. **Story Clustering**: Validates title normalization, headline similarity, and cross-source consensus synergy bonus assignment.
6. **Telegram Commands**: Validates `/topic`, `/curate`, `/watch`, `/unwatch`, `/watches`, and `/brief` command parsing, input sanitization, and state persistence.
7. **Topic Grounding**: Verifies RSS-grounded topic matching and curation pipeline bypasses.
8. **Dry-Run Bypasses**: Ensures all external API calls (Gemini, social broadcasting, state persistence) are correctly bypassed in dry-run mode, including the `/brief` briefing synthesis.
9. **Media Pipeline**: Validates OpenGraph scraping, image compression, alt-text generation, and platform-specific media rendering.

### Running Automated Tests
```bash
pytest src/tests/
```

---

## 🎭 Page 10: The Natural Vibe Engine

Version 3.7.0 transforms the bot from a script into a **living editorial entity**.

### 1. The Editorial Pulse (Stylistic Memory)
The bot now tracks its previous tone to ensure consecutive updates feel varied:
- **Style Memory**: Saves the `last_dialect` key to `seen_articles.json` after successfully posting.
- **Tone Rotation Logic**: During news synthesis in `summarize_news`, the system loads the `last_dialect` from the state. It dynamically prunes the active dialect choice pool (`available_dialects = list(PERSONA_DIALECTS.keys())`) by removing the `last_dialect`. This guarantees the bot never uses the same editorial persona twice in a row.
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

---

## 📡 Page 13: Feed Vanguard Automation

To maintain 100% signal quality, BluBot uses the **Feed Vanguard** to automatically manage RSS health.

### The Auditing Logic
Every run begins with a pre-flight health scan using `VanguardManager._check_feed()`:
1. **Network Fetch**: Fetches each feed with a 15-second timeout and follows redirects.
2. **Response Code check**: Returns a failure if status is not `200`.
3. **Parse Check**: Processes raw content with `feedparser.parse()`. If parser reports `bozo` (malformed XML) and there are no entries, or if the feed is entirely empty, it is marked as unhealthy.

### The "Soft-Disable" Strategy
Instead of hard-deleting feeds when they flake out, the Vanguard uses a **Transient Blacklist**:
1. **Audit**: Every run begins with a pre-flight health check using `VanguardManager`.
2. **Penalty (Hiccup Resilience)**: 
   - **1st failure**: Marked as a `WARNING` only; the feed remains active.
   - **2nd failure**: Silenced for 1 hour.
   - **3rd failure**: Silenced for 12 hours.
   - **4th failure**: Silenced for 24 hours.
   - **5th failure**: Silenced for 48 hours.
   - **6th+ failure**: Silenced for 72 hours max. Marked as `TERMINAL` state once failures hit 6+.
3. **Recovery**: Once the backoff period expires, the Vanguard attempts a recovery fetch. Success restores the feed; multiple failures result in a `TERMINAL` flag.

### Curation Feed Network (45 Validated Feeds)

#### Tier 1: AI Research Labs (base +30)
- OpenAI (`openai.com/news/rss.xml`)
- DeepMind (`deepmind.google/blog/rss.xml`)
- HuggingFace Blog (`huggingface.co/blog/feed.xml`)

#### Tier 2: Enterprise AI (base +25–+27)
- Microsoft Research (`microsoft.com/en-us/research/blog/feed/`)
- AWS ML Blog (`aws.amazon.com/blogs/machine-learning/feed/`)
- NVIDIA Deep Learning (`blogs.nvidia.com/blog/category/deep-learning/feed/`)

#### Tier 3: Practitioner / Developer Ecosystem (base +20)
- Simon Willison (`simonwillison.net/atom/everything/`)
- Interconnects (`interconnects.ai/feed`)
- Latent Space (`latent.space/feed`)
- One Useful Thing (`oneusefulthing.org/feed`)
- Maarten Grootendorst (`newsletter.maartengrootendorst.com/feed`)
- Sebastian Raschka (`magazine.sebastianraschka.com/feed`)
- Jack Clark / Import AI (`jack-clark.net/feed/`)

#### Tier 4: Open-Source Ecosystem (base +18)
- Hugging Face Transformers Releases (`github.com/huggingface/transformers/releases.atom`)
- vLLM Releases (`github.com/vllm-project/vllm/releases.atom`)
- Ollama Releases (`github.com/ollama/ollama/releases.atom`)
- PyTorch Releases (`github.com/pytorch/pytorch/releases.atom`)

#### Tier 5: Infrastructure / Business Analysis (base +15)
- SemiAnalysis (`semianalysis.com/feed/`)
- Together AI (`together.ai/blog/rss.xml`)
- ServeTheHome (`servethehome.com/feed/`)
- Semiconductor Engineering (`semiengineering.com/feed/`)
- Sequoia Capital (`sequoiacap.com/feed/`)
- CB Insights (`cbinsights.com/research/feed/`)

#### Tier 6: Policy, Security & Journalism (base +10–+12)
- AI Incident Database (`incidentdatabase.ai/rss.xml`)
- EU AI Act Tracker (`artificialintelligenceact.eu/feed/`)
- The Verge AI (`theverge.com/rss/ai-artificial-intelligence/index.xml`)
- MIT Technology Review (`technologyreview.com/topic/artificial-intelligence/feed/`)
- IEEE Spectrum AI (`spectrum.ieee.org/feeds/topic/artificial-intelligence.rss`)
- The Decoder (`the-decoder.com/feed/`)
- Wired AI (`wired.com/feed/tag/ai/latest/rss`)
- VentureBeat AI (`venturebeat.com/category/ai/feed/`)
- TechCrunch AI (`techcrunch.com/category/artificial-intelligence/feed/`)
- 404 Media (`404media.co/rss/`)
- Silicon Angle AI (`siliconangle.com/category/ai/feed/`)
- The Sequence (`thesequence.substack.com/feed`)
- Marktechpost (`marktechpost.com/feed/`)
- AI Accelerator Institute (`aiacceleratorinstitute.com/rss/`)

#### Tier 7: Academic (base +10)
- arXiv CS.LG (`arxiv.org/rss/cs.LG`)
- The Gradient (`thegradient.pub/rss/`)
- BAIR Berkeley (`bair.berkeley.edu/blog/feed.xml`)
- ML Mastery (`machinelearningmastery.com/feed/`)

#### Tier 8: Critical / Balancing Voices (base +5)
- AI Snake Oil (`aisnakeoil.com/feed`)
- Gary Marcus (`garymarcus.substack.com/feed`)
- Algorithmic Bridge (`thealgorithmicbridge.substack.com/feed`)
- Victoria Krakovna (`vkrakovna.wordpress.com/feed/`)

---

## Page 14: Interaction Engine (Mention Replies & Comments)

BluBot is no longer a broadcast-only curator. The **Interaction Engine** bridges the gap between static news and conversational engagement by supporting direct mentions and configurable comment replies.

### Core Architecture
The engine runs post-broadcast in `bot.py` and performs the following:
1. **Mention & Comment Polling**: Scans notifications on Bluesky and Mastodon for reasons like `mention` or `reply`, and queries Threads recent posts and replies.
2. **24-Hour Lookback Window**: Filters all comments and notifications to only process items published or indexed within the last 24 hours.
3. **Selective Engagement**: To prevent bot-spam signaling, `MENTION_REPLY_PROB` (default 0.8) and `COMMENT_REPLY_PROB` (default 0.5) ensure the bot only engages with high-quality interactions.
4. **Resilient Threading**:
   - **Bluesky**: Corrects for `root` vs `parent` refs to maintain perfect thread integrity.
   - **Mastodon**: Uses status-id reply chaining.

### Token & Cost Optimization
To optimize inference cost and minimize latency during interactive reply synthesis, the engine enforces strict token bounds:
- **Disabled Thinking**: By default, the `generate_interactive_reply` API call bypasses the `thinking_config` parameters entirely. Bypassing reasoning models prevents runaway token usage on simple dialog.
- **Strict Token Budget**: Enforces a max output limit of `100` tokens (`max_output_tokens=100`), ensuring that responses are concise, focused, and token-efficient.

### Conversational Persona & Prompts
To prevent robotic-sounding AI replies, the model utilizes `INTERACTIVE_REPLY_INSTRUCTION` prompting rules:
1. **Human-like Authenticity**: Avoid robotic pre-ambles, clichés, and greeting formulas (e.g., do NOT start with "As the Elite AI Sage...", "Indeed,", "Greetings,"). Speak as a peer sharing a quick insight.
2. **High Signal**: Provide a genuine piece of strategic or technical insight. Avoid generic "Thanks for the comment!" templates.
3. **Strict Constraints**: No hashtags. Emojis are blocked unless representing a specific technical concept (e.g., 🚀, 🧠). Under 280 characters limit.

**Example Prompt & Output:**
* *Input*: "User @dev1 mentioned you: 'What is the impact of gemma 4 on edge computing?'. Respond insightfully as the Elite Sage."
* *Response*: "Gemma 4's lightweight variants significantly optimize memory-bound edge environments. Look for major efficiency gains in localized agent pipelines."

### Security & Anti-Spam
- **Interaction Limit**: Hard-capped at 5 interactions per run to prevent "tag-bombing" from exhausting AI tokens.
- **Seen Interactions**: Notification IDs are tracked in `seen_interactions.json` to prevent double-replies.
- **Engagement Jitter**: Implements a 10-30s delay to simulate human narrative thought.

### Configuration
Set these in `config.py` or as environment variables:
- `ENABLE_BSKY_COMMENT_REPLIES`: Enable/disable comment replying on Bluesky (default: `true`).
- `ENABLE_MASTODON_COMMENT_REPLIES`: Enable/disable comment replying on Mastodon (default: `false`).
- `ENABLE_THREADS_COMMENT_REPLIES`: Enable/disable comment replying on Threads (default: `false`).
- `MENTION_REPLY_PROB`: Adjust balance between silence and engagement (default: `0.8`).
- `COMMENT_REPLY_PROB`: Adjust balance for replying to non-mentions (default: `0.5`).
- `AUTO_LIKE_INTERACTIONS`: Enable/Disable bot "Likes" on interacted posts (default: `true`).

### Managing Feeds
- **Standalone Audit**: Run `python scripts/feed_audit.py` to get a full health report of all configured feeds.
- **Status Dashboard**: Check `broken_feeds.json` for live health data and fail counts.
- **Manual Override**: Removing a URL from `broken_feeds.json` forces an immediate recovery attempt on the next run.

---

## 🧶 Page 15: Precision Threading (The Weaver Cap)

To maintain "Elite" signal-to-noise ratios and avoid feed fatigue, BluBot v3.8.5 introduces a localized thread cap.

### Configuration
- **`MAX_THREAD_PARTS=2`** (Default): Enforces a strict 2-post limit per thread. 
- **The Weaver Split Logic**: If AI synthesis produces a long narrative, the logic intelligently splits it into 2 parts. If more content exists, it truncates with `...` and relies on the linked article for full details.

### Character Safety Buffers
We now apply a character "Safety Buffer" to prevent rejection from platform APIs (Mastodon, Threads):
- **Mastodon**: 485 chars (Limit 500 - 15)
- **Bluesky/Threads**: 290 chars (Limit 300 - 10)
This ensures that the pagination markers (e.g., `(1/2)`) never push a post over the platform-specific character limit.

---

## 📅 Page 16: Automated Config Updates & Friday Release Focus

### 1. Dynamic Keyword & Product Updates
To prevent search terms from becoming outdated, BluBot utilizes `scripts/update_config_keywords.py` and a weekly GitHub Actions workflow `weekly_config_update.yml` running every Friday morning at 2:00 AM UTC.
* **Functionality**: The script automatically fetches recent headlines from the feed network and calls Gemini to extract the top 10 momentum products and top 12 high-signal developer event/tech keywords.
* **State Push / Pull Request**: The workflow attempts to commit updates back to `main`. If branch protection is active, it automatically creates a new branch and logs a GitHub Pull Request.

### 2. Friday Release Curation Focus
On Friday mornings, the curation prompt automatically shifts. The bot appends a specialized instruction to focus exclusively on product launches and developer releases from the past week, creating a weekly roundup digest.

---

## 🚀 Page 17: Interactive Telegram Control, Alt Text, and Hashtag Management (v3.13.0)

BluBot v3.13.0 introduces three massive upgrades for manual intervention, accessibility, and platform culture alignment:

### 1. Interactive Telegram Gateway & Approval Queue
You can control the bot directly from Telegram. The integration supports two key workflows:
* **The Approval Queue**: Before publishing, the bot posts the text draft + generated image card directly to your Telegram chat using Inline Buttons (`[✅ Approve]`, `[❌ Reject]`, `[🔄 Regenerate Text]`, `[🎨 Regenerate Image]`).
  - **Wait-and-Poll**: The GitHub Action waits up to `TELEGRAM_TIMEOUT_MINUTES` (default: 5) for your choice.
  - **Auto-Post Fallback**: If you do not respond in time, the bot automatically posts the draft to avoid scheduling delays.
  - **Security Gate**: The bot only processes updates matching `TELEGRAM_USER_ID`.
  - **Interactive Editing**: You can edit the draft inline by replying directly to the draft message with your new text, or sending a `/edit <new text>` command. The bot will validate the text length against safety-buffered limits (Bluesky 290, Mastodon 485, Threads 490) and warn you if it will split into a thread or truncate.
  - **Interactive Curation & Image Regeneration (v3.13.0)**:
    - **`[🔄 Regenerate Text]`**: Prompts the user to supply an optional feedback hint. You can reply with formatting instructions (e.g. "shorter", "make it more technical") or write `/skip` to regenerate using default options. Gemini rewrites the draft inline.
    - **`[🎨 Regenerate Image]`**: Automatically regenerates the isometric card prompt using the latest draft text, requests a fresh image using the configured image provider chain, regenerates the screen-reader alt-text using Gemini Vision, and updates the preview media dynamically.
* **On-Demand Topic Curation**: Send `/topic <your_keyword>` or `/curate <your_keyword>` to your Telegram bot. When the GHA runner starts, it performs a real-time keyword search against all active RSS feeds:
  - **RSS Grounding**: If matching articles are found (e.g. searching "Cursor" matches the SpaceX-Cursor deal), the bot curates and synthesizes directly from the actual news articles (preserving original links/facts) rather than relying on stale parametric knowledge.
  - **Raw Curation Fallback**: If no matching articles are found in your RSS feeds, the bot gracefully falls back to raw synthesis from scratch.

### 2. Screen Reader Multimodal Alt-Text
Accessibility is native. If the bot generates or attaches an image:
* It calls Gemini Vision (`models/gemini-2.5-flash-lite`) with the image bytes and the generation prompt.
* Gemini generates a descriptive, screen-reader-ready alt text under 100 characters.
* Alt text is automatically broadcasted alongside the image to Mastodon and Threads.

### 3. Cultural Hashtag Alignment
Hashtags are now toggleable per platform to fit their social norms:
* **Bluesky** (`ENABLE_HASHTAGS_BSKY=false`): Strips hashtags to keep posts clean.
* **Mastodon** (`ENABLE_HASHTAGS_MASTODON=true`): Keeps hashtags for feed discoverability.
* **Threads** (`ENABLE_HASHTAGS_THREADS=true`): Keeps hashtags intact.
* Standalone hashtags are cleanly deleted, and inline hashtags (e.g. `#AI`) are stripped of their `#` prefix (e.g. `AI`).

---

## 🚀 Page 18: Threads Media Propagation Hardening (v3.13.1)

BluBot v3.13.1 introduces a safety fix for Threads media propagation:
* **Threads Stale Media Prevention**: When a user regenerates or changes the post image via the Telegram approval gateway, the bot now automatically clears the stale crawled `image_url` property in the synthesis model. Since Threads uploads images by pulling from the provided URL, this prevents Threads from publishing the original crawled image after a user has approved a regenerated or edited image.

---

## 🚀 Page 19: Telegram Approval Queue Timeout Calibration (v3.13.2)

BluBot v3.13.2 calibrates the Telegram approval queue timeout:
* **Wall-Clock Time Polling**: The Telegram polling loop now uses real wall-clock time (`time.time()`) rather than iteration counts to track elapsed duration. This ensures that the polling timeout runs exactly for the configured timeframe (e.g. 5 minutes) regardless of network call durations or API request polling latency.

---

## 🚀 Page 20: Monotonic Time Tracking for Telegram Approval Timeout (v3.13.3)

BluBot v3.13.3 introduces monotonic time tracking for the Telegram approval queue timeout:
* **Monotonic Time Polling**: Replaced `time.time()` with `time.monotonic()` to track elapsed timeout duration. This makes the polling loop immune to system clock step changes (e.g. VM/container sleep resumes or NTP sync corrections) and ensures the configured timeout remains accurate under all environments.

---

## 🧬 Page 21: Cross-Source Story Clustering (v3.18.0)

BluBot v3.18.0 introduces a **title normalization and story clustering engine** for cross-source consensus detection.

### How It Works
1. **Headline Normalization**: Article titles are tokenized and normalized by stripping stopwords, punctuation, and version identifiers (e.g. "GPT-4o" → "gpt"). This produces a canonical token set per article.
2. **Similarity Matching**: Articles are compared pairwise using Jaccard similarity on their normalized token sets. Articles with high overlap (and optionally matching version strings) are grouped into clusters.
3. **Domain Corroboration**: Within each cluster, the engine counts distinct publisher domains. If ≥2 unique domains report the same story, the cluster is awarded **Consensus Synergy** (`+15` bonus).
4. **Lead Selection**: The highest-scoring article in each cluster becomes the lead. Supporting source names and direct article links are attached to the lead article for editorial transparency.

### Scoring Debug Metadata
Each clustered article's `_score_debug` dictionary is extended with:
- `cluster_size`: Number of articles in the cluster.
- `cluster_lead`: Source ID of the lead article.
- `supporting_sources`: List of source names from non-lead articles in the cluster.
- `consensus_bonus_reason`: `"domain_corroboration"` if ≥2 domains, `"none"` otherwise.

---

## 📌 Page 22: Topic Watchlists (v3.18.0)

BluBot v3.18.0 adds persistent **topic watchlists** for hands-free priority tracking.

### Telegram Commands
| Command | Description |
| :--- | :--- |
| `/watch <topic>` | Add a topic to the watchlist (max 10 active). Topic must be under 100 characters and cannot contain URLs. |
| `/unwatch <topic>` | Remove a topic from the watchlist by exact match (case-insensitive). |
| `/watches` | Display all active watchlist entries with their creation dates. |

### Watchlist Entry Structure
Each watchlist entry is a structured dictionary stored in `seen_articles.json` under the `watch_topics` key:
```json
{
    "topic": "llama 4",
    "display_name": "Llama 4",
    "created": "2026-08-01T12:00:00+00:00",
    "keywords": ["llama"],
    "last_matched": null
}
```

### Scoring Boost
During curation, each article is matched against all active watchlist entries using **word-boundary regex** to prevent false positives (e.g. "ai" won't match "maintenance"):
- **Exact topic match in title**: `+8` boost
- **Keyword match in title**: `+5` boost
- **Keyword match in summary**: `+3` boost
- Maximum boost across all watches is **capped at `+8`** per article.

### Safety Guards
- Maximum 10 active watches to prevent state inflation.
- Topics must be under 100 characters.
- URL-containing topics are rejected.
- Duplicate topics are rejected with an informative response.

---

## 📊 Page 23: Grounded Executive Briefings via `/brief` (v3.18.0)

BluBot v3.18.0 adds the `/brief <topic>` Telegram command for on-demand **7-day executive briefings**.

### How It Works
1. **Broadened RSS Fetch**: The briefing engine calls `fetch_news()` with `days_lookback=7` (vs. the default `2` for regular curation) and `seen_links=[]` (no deduplication filter) to retrieve the complete 7-day article archive.
2. **Topic Matching**: Articles are filtered against the user's topic string using `article_matches_topic()` (same grounding logic as `/topic`).
3. **Story Clustering**: Matching articles pass through the Consensus Synergy clustering engine, grouping corroborated multi-source stories.
4. **Gemini Synthesis**: Up to 15 matching articles are compiled into a structured prompt asking Gemini to produce an analytical executive briefing with:
   - An executive summary paragraph.
   - 3–5 key developments with direct `[Title](URL)` citations.
   - Explicit consensus highlighting when multiple sources corroborate.
5. **Telegram Delivery**: The briefing is delivered to Telegram using `smart_split()` with the 4096-character Telegram message limit. Unlike regular curation, **no `max_chunks` cap** is applied—briefings are delivered in full regardless of length.

### Dry-Run Behavior
When `is_dry_run=True`, the briefing engine bypasses Gemini API calls entirely and returns a structured mock briefing containing the matched article list.

### Input Validation
- Topic must be under 100 characters.
- URL-containing topics are rejected with an `brief_invalid` response.
- If no articles match the topic in the 7-day window, a "No articles found" message is returned.
