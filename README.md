# 🦋 BluBot: Daily AI News on Bluesky

Automated AI news curator that fetches daily updates, summarizes them using **Google Gemini**, and posts them to **Bluesky**—all running for free on **GitHub Actions**.

## 🚀 Features
- **Curated Feeds**: Logic to pull from OpenAI, Google DeepMind (hubs), Hugging Face, TechCrunch AI, and arXiv.
- **Smart Summarization**: Uses Gemini 1.5 Flash to generate concise, engaging summaries.
- **Zero Cost**: Runs entirely on GitHub Actions and free-tier APIs.
- **Scheduled**: Posts automatically once a day.

## 🛠️ Setup Instructions

### 1. Get Your Credentials
- **Bluesky App Password**: 
  - Go to Settings > Advanced > App Passwords in your Bluesky profile.
  - Create a new password named `BluBot`.
- **Gemini API Key**: 
  - Get a free API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Configure GitHub Secrets
Navigate to your repository settings on GitHub:
`Settings > Secrets and variables > Actions > New repository secret`

Add the following secrets:
| Name | Description |
|------|-------------|
| `BLUESKY_HANDLE` | Your Bluesky handle (e.g., `user.bsky.social`) |
| `BLUESKY_PASSWORD` | The App Password you generated |
| `GEMINI_API_KEY` | Your Google Gemini API Key |

### 3. Enable Workflow Permissions
Go to `Settings > Actions > General` and ensure **"Read and write permissions"** is selected under "Workflow permissions" (this allows the bot to run correctly).

## 📂 Project Structure
- `bot.py`: The heart of the bot (fetching + summarizing + posting).
- `requirements.txt`: Python dependencies.
- `.github/workflows/daily_post.yml`: The automation schedule.

## 🧪 Local Testing
If you want to test locally:
1. Clone the repo.
2. Create a `.env` file with your credentials.
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python bot.py`

---
*Built with ❤️ by Antigravity*
