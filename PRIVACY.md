# Privacy Policy for BluBot

**Last Updated: June 21, 2026**

BluBot ("we", "our", or "the Bot") is an automated news curation and broadcasting tool. This Privacy Policy explains how the Bot handles data when you integrate it with third-party platforms, specifically Bluesky, Mastodon, Meta Threads, and Telegram.

## 1. Information We Collect

BluBot is designed to run in a self-hosted or automated environment (such as GitHub Actions).

* **Personal Data:** We do not collect, store, or harvest any personal data, profiles, or contact details of end users.
* **Credentials & Tokens:** Any access tokens, handles, or user IDs required to run the Bot (e.g., `BSKY_APP_PASSWORD`, `MASTODON_ACCESS_TOKEN`, `THREADS_ACCESS_TOKEN`, `TELEGRAM_BOT_TOKEN`) are stored securely as encrypted secrets in your own hosting platform (e.g., GitHub Secrets). The Bot never transmits these credentials to any party other than the official, respective platform API endpoints.
* **Interaction Metadata:** If the Interaction Engine is enabled, the Bot reads notification and reply metadata (post IDs, author handles, and post text) from Bluesky, Mastodon, and Threads APIs solely to generate replies. Processed notification IDs are stored locally in `seen_interactions.json` (in your private repository) to prevent double-replies; no personal text is persisted.
* **Telegram Messages:** If the Telegram gateway is enabled, the Bot reads the most recent messages in your private Telegram bot conversation (up to the last 50 updates) to check for `/topic` or `/curate` commands and to receive approval decisions. All message processing is scoped to the single authorized `TELEGRAM_USER_ID`. Note: `/topic <keyword>` commands and text-regeneration feedback you send are forwarded to the Google Gemini API as part of the synthesis or editing prompt. No Telegram message content is stored locally or transmitted to any other party.

## 2. How We Use Data

The Bot accesses platform APIs solely to:

* Publish curated AI news summaries (posts) to your authorized Bluesky, Mastodon, and Threads accounts.
* Fetch recent mentions or replies to your posts (if explicitly enabled) for the sole purpose of generating contextual responses.
* Update your social media profile bios (if explicitly enabled) with automated bot telemetry (active day count and current topic).
* Send draft previews to your Telegram chat for manual approval and receive approval/rejection/edit decisions before publishing.

## 3. Data Sharing and Third Parties

* **No Sharing:** We do not sell, trade, or share any data with third-party companies, marketers, or external entities.
* **Platform APIs:** Your data is processed directly via each platform's official API:
  - Bluesky AT Protocol in accordance with Bluesky's [Terms of Service](https://bsky.social/about/support/tos).
  - Mastodon API in accordance with your instance's terms of service.
  - Meta Threads API in accordance with [Meta Developer Policies](https://developers.facebook.com/policy/).
  - Telegram Bot API in accordance with Telegram's [Privacy Policy](https://telegram.org/privacy).
* **Google Gemini / NVIDIA NIM:** The following content is sent to the Google Gemini API as part of normal operation:
  - Curated news article titles and summaries (for synthesis).
  - Generated image prompts (for alt-text generation via Gemini Vision).
  - `/topic` keywords and text-regeneration feedback from Telegram (when those features are used).
  - When the Interaction Engine is enabled (`ENABLE_INTERACTIONS=true`, default), social mention and reply text — including the author's handle and post content — is sent to Gemini to generate a contextual reply.
  
  Image generation prompts are additionally sent to the NVIDIA NIM API (when `IMAGE_PROVIDER=nvidia`, the default). Refer to [Google's Privacy Policy](https://policies.google.com/privacy) and [NVIDIA's Privacy Policy](https://www.nvidia.com/en-us/about-nvidia/privacy-policy/) for details on how they handle API request data.

## 4. Data Retention

BluBot operates in a near-stateless environment. It does not run a persistent database for personal information. The only local state persisted is:

* **`seen_articles.json`**: Public news article URLs (to prevent duplicate posts) and editorial metadata (last dialect, topic history). Capped at the last 500 links and 20 recent topics.
* **`seen_interactions.json`**: Social media post/notification IDs of processed interactions, to prevent double-replies. No personal text is stored.
* **`bluesky_session.txt`**: A Bluesky session token for session resumption, stored in your private repository.
* **`broken_feeds.json`**: Health status of RSS feeds (URLs and failure counts). No personal data.

All state files reside exclusively in your private repository or GitHub Gist and are never transmitted to the bot author.

## 5. Revoking Access

You can revoke BluBot's access to any platform at any time by:

1. Removing the relevant credentials from your hosting environment (GitHub Secrets or `.env` file).
2. Revoking the application's OAuth token / App Password directly in the platform's account settings (e.g., Bluesky App Passwords, Mastodon Apps, Threads Website Permissions, Telegram BotFather `/revoke`).

## 6. Contact & Support

If you have any questions about this Privacy Policy, please open an issue in the public GitHub repository where this bot is hosted.
