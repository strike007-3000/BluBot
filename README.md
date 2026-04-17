# 👨‍🔧 BluBot: Elite AI News Curator

Automated AI news curator that fetches updates twice daily, synthesizes them using **Sage Intelligence (Multi-Model Failover)**, and broadcasts insightfully to **Bluesky**, **Mastodon**, and **Threads**—all running entirely for free on **GitHub Actions**.

## 📊 System Status
| Component | Status | Last Run | Mode |
|:---|:---|:---|:---|
| **Broadcaster** | Operational | 2026-04-17 | 🔍 Afternoon Deep Dive (General) |
| **Signal Strength** | Elite (Parallel) | -- | -- |

## 🚀 Key Features

- **Sage Intelligence v3 (Self-Healing AI)**: 
    - **Multi-Model Failover**: Automatically rotates through prioritized models (**`Gemini 3.1 Flash Lite`**, **`Gemma 4 31B/26B`**, **`Gemma 3 27B-IT`**) if the primary provider is saturated or fails validation.
    - **Self-Healing Loop**: Automatically corrects common AI output issues (e.g., missing hashtags) and **strips accidental markdown formatting** (bolding/italics) to ensure 100% clean posts.
    - **Self-Discovery Diagnostics**: If a model fails to validate, the bot automatically **logs every available model ID** for your key.
    - **Graceful Degradation**: If news volume is low or summarization fails, the bot intelligently degrades to "Mentor Fallback" mode.
- **🖼️ Self-Healing Image Generation (v3.6)**: 
    - **NVIDIA NIM Integration**: Uses **Stability AI Stable Diffusion 3 Medium** via NVIDIA's Inference Microservices as the primary image provider, bypassing the 100-run "Imagen restricted" blockers.
    - **Smart Image Compression**: Built-in **Pillow-powered optimizer** that automatically resizes thumbnails to platform-specific limits (fixing "blob too big" errors).
- **Fast Async Parallel Engine**: Re-engineered with `asyncio` and a shared `httpx.AsyncClient` context for 90% faster processing.
- **Fortress Hardening (v3.6.5)**: 
    - **Structured JSON Logging**: Re-engineered `SafeLogger` to output machine-readable JSON with entropy-aware secret redaction (identifies keys by string-complexity).
    - **SSRF Prevention Architecture**: Hardened the metadata scraper with **DNS Pinning** and **IP validation** to block all internal/private network requests.
    - **Zero-Duplicate Threads Logic**: Implemented "Catch & Log" delivery validation to prevent duplicate posts during transient API failures.
- **Breakthrough Scoring Engine v3 (Elite Signal Processing)**: 
    - **Impact-Aware Intelligence**: Prioritizes breakthrough news (Agents, SOTA) and boosts articles mentioning flagship 2026 models.
    - **Consensus Synergy Pass**: Automatically boosts "Consensus Events" reported by multiple independent feeds.

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
| `GEMINI_KEY` | **Yes** | Your Google Gemini API Key |
| `NVIDIA_KEY` | **Yes** | Your NVIDIA API Key (for SD3) |
| `IMAGE_PROVIDER` | No | Default: `nvidia`. Set to `imagen` to switch back. |
| `MASTODON_ACCESS_TOKEN` | No | Your Mastodon Access Token |
| `MASTODON_BASE_URL` | No | Your Mastodon Instance URL |
| `THREADS_ACCESS_TOKEN` | No | Your Threads Long-Lived Access Token |
| `THREADS_USER_ID` | No | Your Threads User ID |

## 📂 Project Structure

- `bot.py`: Main Orchestrator.
- `src/`: Modular logic layers (Config, Logger, Curator, Utils, Broadcaster).
- `test_models.py`: **Interactive Diagnostic Suite** (Unified RSS & AI validation).

## 🗒️ Updates & History

- **v3.6.5 (Current)**: **Security Hardening & Structural Logging**.
    - **Structured JSON Logs**: Implemented standardized `logging` with automated masking for high-entropy secrets and auth tokens.
    - **SSRF Hardening**: Integrated DNS pinning and IP scoping for `get_link_metadata` to prevent internal service discovery.
- **v3.6.4**: **Threads & Documentation Sync**.
    - **Failure Propagation**: Hardened Threads publishing to correctly signal delivery failures to the orchestrator.
- **v3.6.3**: **Threads Stability Patch**.
    - **Zero-Duplicate Strategy**: Implemented initial Threads delivery validation.
- **v3.6.0**: **NVIDIA NIM Image Integration**.
    - Bypassed Imagen 4 restrictions by moving to NVIDIA SD3.
    - Added interactive console input for keys in `test_models.py`.
- **v3.5.12**: **Persistence & Retry Hardening**.
    - Implemented `--autostash` for state updates and branch bootstrapping logic.
    - Narrowed retry behavior to skip terminal 403/400 errors.

---

## 🤝 Community & Security
- **Wiki**: Find the full technical blueprint in the [Elite Sage Manual](docs/WIKI_MANUAL.md).

*Built with ❤️ for the AI Community*
