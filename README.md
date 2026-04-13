# 👨‍🔧 BluBot: Daily AI News Curator

Automated AI news curator that fetches updates twice daily, synthesizes them using **Google Gemini 3.1 Flash Lite**, and posts them to **Bluesky**, **Mastodon**, and **Threads**—all running for free on **GitHub Actions**.

## 🚀 Features

- **Multi-Platform Support**: Automatically posts to Bluesky, Mastodon, and Threads.
- **Curated AI Feeds**: Pulls from 25+ high-signal sources including OpenAI, DeepMind, Anthropic, Hugging Face, EE Times, Ahead of AI, SemiAnalysis, 404 Media, and arXiv.
- **Smart Deduplication**: Tracks processed articles to ensure no repeats (persisted via `seen_articles.json`).
- **48-Hour Coverage**: Scans the last 48 hours of news to ensure even slow news days have high-quality content.
- **Rich Link Previews (Bluesky)**: Automatically generates beautiful link cards with thumbnails and descriptions using Open Graph metadata.
- **Robust Quality Control**:
  - **Metadata Scraping**: Uses `BeautifulSoup` to safely extract article previews.
  - **Validation**: Filters out gibberish, repetitive patterns, and low-quality output.
  - **Rescue Logic**: Automatic "Best Candidate" and "Length Rescue" attempt to fix almost-perfect summaries.
- **Scheduled & Free**: Runs twice daily (9:00 AM and 3:00 PM local) using GitHub Actions.

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

## 📂 Project Structure

- `bot.py`: Main logic (RSS fetching, Gemini synthesis, platform posting).
- `seen_articles.json`: Persistent state file that stores IDs of previously posted news.
- `requirements.txt`: Python dependencies.
- `.github/workflows/daily_post.yml`: GitHub Actions schedule and environment setup.
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

---
*Built with ❤️ for the AI Community*
