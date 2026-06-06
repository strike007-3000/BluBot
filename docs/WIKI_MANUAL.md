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

### The Curation & Scoring Pipeline

1. **Source Tiering**:
   - **Tier 1 (Labs)**: `+30` score boost.
   - **Tier 2 (Newsletters & Analysts)**: `+15` score boost.
   - **Hidden Gems (Tier 3 - Research)**: `+15` score boost (defined as `BASE_HIDDEN_GEM`).
2. **Signal Boosting**: `+12` boost if title or summary contains high-signal keywords (e.g. *SOTA, agentic, world model, open weights*, etc.).
3. **Momentum Product Boosting**: `+18` boost if title contains momentum products (e.g. *gpt-5, llama 4, gemini 3, gemma 4*, etc.).
4. **Consensus Synergy Pass**: `+15` synergy bonus added if the article appears across multiple independent RSS feeds.
5. **Diversity Penalty**: Subtracts `-12` (defined as `-25` in configuration constants but active as `-12` in runtime code) if the article's classified topic is already in `recent_topics` list, preventing repetition.
6. **Time Decay**: Subtracts `-0.5` score for each hour since the article's publication to keep the feed fresh.

---

## 🛡️ Page 3: Reliability & The Fortress (v3.9.0)

The Sage is designed to be **unbreakable**.

### Hardening Features
- **3-Tier State Resilience (v3.8.0)**: BluBot implements a redundant persistence model. If the primary `seen_articles.json` is corrupted or missing, it automatically falls back to a local `.bak` rotation and finally a remote **GitHub Gist**.
- **Structured Logging (v3.6.5)**: The `SafeLogger` uses Python's `logging` module with a custom `JsonFormatter` and `RedactionFilter`. It automatically masks high-entropy strings (JWTs, API tokens) using entropy and keyword matching to prevent leakages in CI.
- **Visual Integrity Defense (v3.7.6)**: Implements **Universal RGB Conversion** in the image engine (`compress_image`) to handle grayscale (ArXiv) and specialized modes (such as CMYK), converting them to RGB before compression to avoid solid black/white artifact regressions.
- **SSRF Prevention Logic**: The metadata scraper (`get_link_metadata`) uses **DNS Pinning** to lock down the hostname to pre-resolved IPs and **IP Validation** to ensure no private/internal network addresses are called (mitigating Server-Side Request Forgery).
- **Zero-Duplicate Threads Logic ("Catch & Log")**: Prevents duplicate postings during transient API failures or runner timeouts. If a stage fails after publishing partial thread contents, the exception is caught, logged, and state is immediately persisted with successfully broadcast post identifiers. This ensures that a subsequent run does not publish the same content again.
- **Decompression Bomb Protection**: Restricts Pillow's image loading engine (`Image.MAX_IMAGE_PIXELS`) to a maximum of `10,000,000` pixels to shield the app from memory exhaustion attacks when retrieving large media files.
- **Resilient RSS Parsing**: Rather than relying on string-based feed parser scraping, the engine reads raw bytes via `response.content` and performs graceful lookups on optional attributes (`getattr(entry, 'link', None)`) to tolerate malformed XML schemas.

---

## 🎨 Page 4: NVIDIA NIM Image Generation

The Sage uses **Stability AI Stable Diffusion 3 Medium** via NVIDIA's Inference Microservices as the primary image provider.

### The Designer & Image Pipeline

```
              [Scrape Article URL]
                       │
                       ▼
          [Check og:image in Metadata]
           /                        \
      (Found)                     (Not Found)
         ▼                            ▼
  [Normalize URL]            [Call NVIDIA SD3 NIM]
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
3. **NVIDIA NIM SD3 Generation (Fallback)**: If no original image is found, the system requests a minimalist isometric tech graphic prompt using `models/gemini-3.1-flash-lite-preview`, then invokes the SD3 NIM microservice to generate the base64-encoded JPEG image.
4. **RGB Conversion**: Standardizes image mode representations by converting CMYK or Grayscale source images to standard RGB, preventing rendering distortions.
5. **Iterative Quality Compression**: Fits the binary payload under the strict 900KB platform upload cap. The optimizer iteratively scales JPEG quality down (from 85% to 30%, in steps of 10%) and writes to an in-memory buffer (`io.BytesIO()`) until the constraints are met.

---

## 🛰️ Page 5: Source Intelligence

Scanning over **30 premium feeds**.
- **Tier 1**: OpenAI, DeepMind, Anthropic, HuggingFace, Mistral.
- **Hidden Gems**: ArXiv (CS.AI/LG), BAIR (Berkeley), SAIL (Stanford), NVIDIA Research.

---

## ⚙️ Page 6: Technical Configuration (v3.10.1)

### Environment Secrets
| Variable | Description |
| :--- | :--- |
| `GEMINI_KEY` | Google AI Studio Key (also used for Active Model Discovery) |
| `NVIDIA_KEY` | NVIDIA Build API Key (for SD3) |
| `THINKING_BUDGET` | (Optional) Thinking budget for Gemini 2.0/2.5 models (default: 1024) |
| `GEMINI_MODEL` | (Optional) Primary model used for interactive replies (default: `models/gemini-2.5-flash-lite`) |
| `BSKY_HANDLE` | Your Bluesky handle |
| `BSKY_APP_PASSWORD` | BlueSky App Password |
| `GIST_ID` | Private GitHub Gist ID |
| `GIST_TOKEN` | GitHub Token with `gist` scope |
| `IMAGE_PROVIDER` | `nvidia` (default) or `imagen` |
| `ENABLE_BSKY_COMMENT_REPLIES` | (Optional) Enable/disable replying to comments on Bluesky (default: `true`) |
| `ENABLE_MASTODON_COMMENT_REPLIES` | (Optional) Enable/disable replying to comments on Mastodon (default: `false`) |
| `ENABLE_THREADS_COMMENT_REPLIES` | (Optional) Enable/disable replying to comments on Threads (default: `false`) |

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

### Hardening & Event-Loop Optimization
- **Non-Blocking I/O**: File persistence (`load_seen_articles`/`save_seen_articles`, `load_seen_interactions`/`save_seen_interactions`, `load_session_string`/`save_session_string`), social media profile bio updates, status dashboard telemetry, and feed vanguard state tracking are completely offloaded to background worker threads via `asyncio.to_thread`. This guarantees that the core async event loop is never blocked during high-concurrency periods.
- **Decompression Bomb Protection**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to shield the application from decompression-bomb denial-of-service (DoS) exploits when parsing media URLs.
- **Resilient RSS Parsing**: Incorporates raw byte parsing via `response.content` and robust fallback handling for malformed XML schemas. It uses safe lookups (`getattr(entry, 'link', None)`) and skips invalid entries to prevent single-feed crashes from dropping whole RSS sources.

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

- [Page 8: 3-Tier State Resilience](#-page-8-3-tier-state-resilience)
- [Page 3: Reliability & The Fortress](#-page-3-reliability--the-fortress)
- [Page 4: NVIDIA NIM Image Generation](#-page-4-nvidia-nim-image-generation)
- [Page 14: Interaction Engine (Mention Replies & Comments)](#page-14-interaction-engine-mention-replies--comments)
- [Page 15: Precision Threading (The Weaver Cap)](#-page-15-precision-threading-the-weaver-cap)

- [Page 8: 3-Tier State Resilience (v3.8.0)](#-page-8-3-tier-state-resilience-v380)
- [Page 3: Reliability & The Fortress (v3.9.0)](#-page-3-reliability--the-fortress-v390)
- [Page 4: NVIDIA NIM Image Generation (v3.6)](#-page-4-nvidia-nim-image-generation-v36)
- [Page 14: Interaction Engine (Mention Replies & Comments) (v3.11.0)](#page-14-interaction-engine-mention-replies--comments-v3110)
- [Page 15: Precision Threading (The Weaver Cap)](#-page-15-precision-threading-the-weaver-cap)

- [Page 8: 3-Tier State Resilience (v3.8.0)](#-page-8-3-tier-state-resilience-v380)
- [Page 3: Reliability & The Fortress (v3.9.0)](#-page-3-reliability--the-fortress-v390)
- [Page 4: NVIDIA NIM Image Generation (v3.6)](#-page-4-nvidia-nim-image-generation-v36)
- [Page 14: Interaction Engine (Mention Replies & Comments) (v3.11.0)](#page-14-interaction-engine-mention-replies--comments-v3110)
- [Page 15: Precision Threading (The Weaver Cap)](#-page-15-precision-threading-the-weaver-cap)

- [Page 8: 3-Tier State Resilience (v3.8.0)](#-page-8-3-tier-state-resilience-v380)
- [Page 3: Reliability & The Fortress (v3.9.0)](#-page-3-reliability--the-fortress-v390)
- [Page 4: NVIDIA NIM Image Generation (v3.6)](#-page-4-nvidia-nim-image-generation-v36)
- [Page 14: Interaction Engine (Mention Replies & Comments) (v3.11.0)](#page-14-interaction-engine-mention-replies--comments-v3110)
- [Page 15: Precision Threading (The Weaver Cap)](#-page-15-precision-threading-the-weaver-cap)

- [Page 8: 3-Tier State Resilience (v3.8.0)](#-page-8-3-tier-state-resilience-v380)
- [Page 3: Reliability & The Fortress (v3.9.0)](#-page-3-reliability--the-fortress-v390)
- [Page 4: NVIDIA NIM Image Generation (v3.6)](#-page-4-nvidia-nim-image-generation-v36)
- [Page 14: Interaction Engine (Mention Replies & Comments) (v3.11.0)](#page-14-interaction-engine-mention-replies--comments-v3110)
- [Page 15: Precision Threading (The Weaver Cap)](#-page-15-precision-threading-the-weaver-cap)

- [Page 8: 3-Tier State Resilience (v3.8.0)](#-page-8-3-tier-state-resilience-v380)
- [Page 3: Reliability & The Fortress (v3.9.0)](#-page-3-reliability--the-fortress-v390)
- [Page 4: NVIDIA NIM Image Generation (v3.6)](#-page-4-nvidia-nim-image-generation-v36)
- [Page 14: Interaction Engine (Mention Replies & Comments) (v3.11.0)](#page-14-interaction-engine-mention-replies--comments-v3110)
- [Page 15: Precision Threading (The Weaver Cap)](#-page-15-precision-threading-the-weaver-cap)

- [3-Tier State Resilience](#3-tier-state-resilience)
- [Security & Supply Chain](#security--supply-chain)
- [Page 12: Media Pipeline & NVIDIA NIM](#page-12-media-pipeline--nvidia-nim)
- [Page 14: Interaction Engine (Mention Replies)](#page-14-interaction-engine-mention-replies)
- [Page 15: Precision Threading (The Weaver Cap)](#page-15-precision-threading-the-weaver-cap)

To ensure the Sage never "forgets" even in ephemeral runner environments, we use a tiered persistence model.

### The Recovery Sequence
1. **Primary Local**: Fast loading from `seen_articles.json` with advisory `FileLock`.
2. **Local Backup**: On every run, the previous state is saved to `.bak`. If the primary is corrupted, the bot auto-restores from this file.
3. **Remote Gist (The Cloud Memory)**: Syncs state with a private GitHub Gist. This allows the bot to maintain "Seen Articles" across different CI/CD runners without incurring Git merge conflicts.

---
## 🧪 Page 9: Automated Quality Control

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

## 📡 Page 13: Feed Vanguard Automation (v3.8.2)

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

### Curation Feed Network (32 Validated Feeds)

#### Tier 1: AI Lab Blogs
- Google Blog (`blog.google/rss/`)
- Apple Newsroom (`apple.com/newsroom/rss-feed.rss`)
- Verge AI (`theverge.com/ai-artificial-intelligence/rss/index.xml`)
- OpenAI (`openai.com/news/rss.xml`)
- Hugging Face (`huggingface.co/blog/feed.xml`)
- DeepMind (`deepmind.google/blog/rss.xml`)
- NVIDIA Deep Learning (`blogs.nvidia.com/blog/category/deep-learning/feed/`)
- Microsoft Research (`microsoft.com/en-us/research/blog/feed/`)

#### Tier 2: Elite Newsletters & Analysts
- Interconnects (`interconnects.ai/feed`)
- Sebastian Raschka (`magazine.sebastianraschka.com/feed`)
- Latent Space (`latent.space/feed`)
- Import AI / Jack Clark (`jack-clark.net/feed/`)
- One Useful Thing / Ethan Mollick (`oneusefulthing.org/feed`)
- Maarten Grootendorst (`newsletter.maartengrootendorst.com/feed`)
- AlphaSignal AI (`alphasignalai.beehiiv.com/feed`)
- TheSequence (`thesequence.substack.com/feed`)
- TLDR AI (`tldr.tech/ai/rss`)

#### Tier 3: Research & Academic (Hidden Gems)
- ArXiv cs.LG (`arxiv.org/rss/cs.LG`)
- The Gradient (`thegradient.pub/rss/`)
- Victoria Krakovna (`vkrakovna.wordpress.com/feed/`)
- BAIR Berkeley (`bair.berkeley.edu/blog/feed.xml`)
- Machine Learning Mastery (`machinelearningmastery.com/feed/`)

#### Tier 4: Industry & Journalism
- MIT Technology Review (`technologyreview.com/topic/artificial-intelligence/feed/`)
- IEEE Spectrum AI (`spectrum.ieee.org/feeds/topic/artificial-intelligence.rss`)
- The Decoder (`the-decoder.com/feed/`)
- 404 Media (`404media.co/rss/`)
- Wired AI (`wired.com/feed/tag/ai/latest/rss`)
- SiliconANGLE AI (`siliconangle.com/category/ai/feed/`)
- AI Accelerator Institute (`aiacceleratorinstitute.com/rss/`)
- Marktechpost (`marktechpost.com/feed/`)
- TechCrunch AI (`techcrunch.com/category/artificial-intelligence/feed/`)
- VentureBeat AI (`venturebeat.com/category/ai/feed/`)

---

## Page 14: Interaction Engine (Mention Replies & Comments) (v3.10.1)

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

