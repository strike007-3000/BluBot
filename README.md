# 🤖 BluBot: Daily AI News Curator

Automated AI news curator that fetches daily updates, synthesizes them using **Google Gemini 3.1 Flash Lite**, and posts them to **Bluesky** and **Mastodon**—all running for free on **GitHub Actions**.

## 🚀 Features

- **Multi-Platform Support**: Automatically posts to both Bluesky and Mastodon.
- **Curated AI Feeds**: Pulls from high-quality sources including OpenAI, Hugging Face, TechCrunch AI, MIT Technology Review, and arXiv (cs.AI).
- **Intelligent Summarization**: Uses **Gemini 3.1 Flash Lite (Preview)** with sophisticated system instructions to generate engaging, optimistic, and technical summaries.
- **Robust Quality Control**:
  - **Validation**: Filters out gibberish, repetitive patterns, and low-quality output.
  - **Rescue Logic**: Automatic "Best Candidate" and "Length Rescue" attempt to fix almost-perfect summaries (e.g., adding missing hashtags or expanding short posts).
- **Scheduled & Free**: Runs daily at 9:00 AM UTC using GitHub Actions (zero hosting costs).

## 🛠️ Setup Instructions

### 1. Platform Credentials

#### Bluesky
- Go to `Settings > Advanced > App Passwords`.
- Create a new password named `BluBot`.

#### Mastodon (Optional)
- Go to `Preferences > Development > New Application`.
- Select `write:statuses` scope and save to get your **Access Token**.

#### Google Gemini
- Get a free API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Configure GitHub Secrets

If you are forking this repository, you **must** configure these secrets for the bot to run:

Navigate to: `Settings > Secrets and variables > Actions > New repository secret`

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `BSKY_HANDLE` | **Yes** | Your Bluesky handle (e.g., `user.bsky.social`) |
| `BSKY_APP_PASSWORD` | **Yes** | Your Bluesky **App Password** (NOT your main account password) |
| `GEMINI_KEY` | **Yes** | Your Google Gemini API Key |
| `MASTODON_ACCESS_TOKEN` | No | Your Mastodon Access Token (if using Mastodon) |
| `MASTODON_BASE_URL` | No | Your Mastodon Instance URL (e.g., `https://mastodon.social`) |

### 3. Enable Workflow Permissions
Go to `Settings > Actions > General` and ensure **"Read and write permissions"** is selected under "Workflow permissions".

## 📂 Project Structure

- `bot.py`: Main logic (RSS fetching, Gemini synthesis, platform posting).
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
