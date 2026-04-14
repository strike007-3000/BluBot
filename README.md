# 👨‍🔧 BluBot: Daily AI News Curator

Automated AI news curator that fetches updates twice daily, synthesizes them using **Google Gemini 3.1 Flash Lite**, and posts them to **Bluesky**, **Mastodon**, and **Threads**—all running for free on **GitHub Actions**.

## 📊 System Status
| Component | Status | Last Run | Mode |
|:---|:---|:---|:---|
| **Broadcaster** | Operational | 2026-04-13 | 🚀 Async Engine |
| **Signal Strength** | Elite (Parallel) | -- | -- |

## 🚀 Key Features

- **Fast Async Engine**: Re-engineered with `asyncio` and `httpx` to fetch 25+ RSS feeds concurrently. Processing time reduced by **90%**.
- **Concurrent Broadcasting**: Posts to Bluesky, Mastodon, and Threads simultaneously for maximum efficiency.
- **Smart Image Compression**: Built-in **Pillow-powered optimizer** that automatically resizes thumbnails to stay under platform limits (fixing the "blob too big" errors).
- **Curated AI Feeds**: Pulls from 25+ high-signal sources including OpenAI, DeepMind, Anthropic, Hugging Face, EE Times, Ahead of AI, SemiAnalysis, 404 Media, and arXiv.
- **Signal-to-Noise Engine**: Uses heuristic-based scoring (Source Tiers + Product Keywords) to prioritize groundbreaking AI news.
- **Freshness Engine**: Automatically rotates through sub-topics (LLMs, Robotics, Compute, etc.) to ensure content stays diverse and non-repetitive.
- **Dual-Mode Persona System**: Switches between **The Curator** (Morning news) and **The Senior Analyst/Mentor** (Afternoon wisdom). The bot adapts its tone and focus based on the time of day.
- **4-State Intelligence Matrix**: Dynamically adjusts content strategy based on news volume. If news is slow, the bot automatically transitions to **Strategist Mode** using a pool of **15+ Secondary Topics**, ensuring 100% active cycles.
- **Temporal Intelligence**: Adapts tone and framing based on the day of the week (e.g., "Monday Strategy" vs. "Friday Recap").
- **Hidden Gem Injection**: Ensures at least one high-signal research paper (from `arXiv` or Engineering blogs) is surfaced in every post.
- **Rich Link Previews & Facets (Bluesky)**: Generates beautiful link cards AND ensures all **hashtags and URLs are clickable** by automatically calculating UTF-8 byte-slice facets.
- **Stealth Metadata Scraper**: Upgraded for high-resilience extraction using browser-mimicry headers and intelligent redirection handling (fixing 403 Forbidden issues on sites like OpenAI).
- **The Fortress: Advanced Security**:
  - **Dynamic Log Masking**: `SafeLogger` now automatically scans for and redacts any value found in environment variables (Keys, Tokens, Passwords) to prevent accidental credential leaks.
  - **Prompt Injection Defense**: (Planned) Architecture ready for sanitization filters.
- **Sage Intelligence v2 (Robustness)**:
  - **Byte-Safe Truncation**: Specialized logic to truncate long summaries on byte boundaries, preventing API crashes from split multi-byte characters (emojis).
  - **Async Parse Offloading**: Computationally expensive operations like `feedparser` and `BeautifulSoup` are offloaded to worker threads, ensuring the 0ms-freeze async engine.
  - **O(1) Deduplication**: In-memory `seen_set` lookups ensure instant duplicate check across hundreds of historical links.
- **Refined Signal Stream**: Optimized list of 25+ top-tier AI feeds, with unstable sources automatically pruned for 100% scheduled reliability.
- **Atomic Persistence Engine**:
  - **Fault-Tolerant State**: State is saved incrementally/independently per platform. If Threads fails, your Bluesky/Mastodon success is still persisted—no more duplicate posts on retry.
  - **Session Management**: Reuses authenticated sessions across platforms to minimize redundant login handshakes.
- **Robust Resilience Engine**: Standardized `@retry_with_backoff` decorator with **Exponential Backoff and Jitter**. The bot intelligently recovers from transient API errors, rate limits (429), and network hiccups.
- **Optimized Scheduling**: Runs twice daily on weekdays (9:00 AM and 3:00 PM local) and once daily on weekends (9:00 AM) via GitHub Actions.

## 🛠️ Setup Instructions

### ⚙️1. Platform Credentials

#### Bluesky
- Go to `Settings > Advanced > App Passwords`.
- Create a new password named `BluBot`.

#### Mastodon (Optional)
- Go to `Preferences > Development > New Application`.
- Select `write:statuses` scope and save to get your **Access Token**.

#### Threads (Optional)
1.  **Create a Meta App**: Go to [Meta for Developers](https://developers.facebook.com/) and create a new app with the **Threads** use case.
2.  **Configure Scopes**: Under **Use Cases > Threads API > Customize**, ensure both `threads_basic` and `threads_content_publish` are enabled.
3.  **Add Redirect URI**: In the Threads App settings, add `https://localhost/` to the **Valid OAuth Redirect URIs**.
4.  **Handle Sandbox/Development**: If your app is not yet live/reviewed:
    - Go to **App Roles > Roles** and add your own account as a **Threads Tester**.
    - Accept the invite in your Threads App (**Settings > Account > Website Permissions > Invites**).
5.  **Generate Token**: Use the included `setup_threads.py` script. It will ask for your **Threads App ID** and **Threads App Secret** (found in your app's Basic settings).
6.  **GitHub Secrets**: The script will provide your **Long-Lived Access Token** and **Threads User ID**. Add these to your GitHub repo secrets.

#### Google Gemini
- Get a free API key from [Google AI Studio](https://aistudio.google.com/).

### 🤫2. Configure GitHub Secrets

If you are forking this repository, you **must** configure these secrets for the bot to run:

Navigate to: `Settings > Secrets and variables > Actions > New repository secret`

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `BSKY_HANDLE` | **Yes** | Your Bluesky handle (e.g., `user.bsky.social`) |
| `BSKY_APP_PASSWORD` | **Yes** | Your Bluesky **App Password** (NOT your main account password) |
| `GEMINI_KEY` | **Yes** | Your Google Gemini API Key |
| `MASTODON_ACCESS_TOKEN` | No | Your Mastodon Access Token (if using Mastodon) |
| `MASTODON_BASE_URL` | No | Your Mastodon Instance URL (e.g., `https://mastodon.social`) |
| `THREADS_ACCESS_TOKEN` | No | Your Threads Long-Lived Access Token |
| `THREADS_USER_ID` | No | Your Threads User ID |

### 🪄3. Enable Workflow Permissions
Go to `Settings > Actions > General` and ensure **"Read and write permissions"** is selected under "Workflow permissions".


## Model Failover (Free Tier)

To improve reliability on the free tier, the bot uses automatic model failover for text generation.

Failover priority:
1. `gemini-3.1-flash-lite` (primary)
2. `gemma-3-27b` (high-availability fallback)
3. `gemini-2.5-flash-lite` (secondary fallback)

Failover is triggered when transient provider/API saturation errors occur (for example `503 UNAVAILABLE`, and `429` where that retry path is enabled). The bot retries with the next model in priority order.

If all configured models fail, the bot degrades to the mentor-insight generation path (when enabled) so scheduled runs can still complete instead of crashing.

Runtime logs include the attempted model and selected fallback transitions to simplify troubleshooting in GitHub Actions.

## 📂 Project Structure

- `bot.py`: The entry point (Orchestrator) that coordinates the daily news cycle.
- **`src/`**: The core package containing modular layers:
  - `config.py`: Centralized configuration (RSS feeds, tiers, topic map).
  - `utils.py`: Resilience Engine (@retry_with_backoff), Metadata scraping, and Image compression.
  - `curator.py`: News discovery, relevance scoring, and Gemini synthesis.
  - `broadcaster.py`: Social media posting logic for all platforms.
- `seen_articles.json`: Persistent state file storing the memory of previously posted articles.
- `requirements.txt`: Python dependencies (including `httpx` and `Pillow`).
- `.github/workflows/daily_post.yml`: GitHub Actions schedule and CI/CD environment.
- `debug_bot.py`: Helper script for local testing without triggers.

## 🧪 Local Testing

1. Clone the repository.
2. Create a `.env` file with the secrets listed above.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## 🗒️ Updates & History

- **2026-04-14**: Introduced free-tier model failover with ordered fallback models for transient provider saturation resilience.

---
*Built with ❤️ for the AI Community*
