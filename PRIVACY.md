# Privacy Policy for BluBot

**Last Updated: June 14, 2026**

BluBot ("we", "our", or "the Bot") is an automated news curation and broadcasting tool. This Privacy Policy explains how the Bot handles data when you integrate it with third-party platforms, specifically Meta Threads.

## 1. Information We Collect
BluBot is designed to run in a self-hosted or automated environment (such as GitHub Actions). 
* **Personal Data:** We do not collect, store, or harvest any personal data, profiles, or contact details of our users.
* **Credentials & Tokens:** Any access tokens or user IDs (e.g., `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`) required to run the Bot are stored securely as encrypted secrets in your own hosting platform (e.g., GitHub Secrets). The Bot never transmits these credentials to any party other than the official Meta Threads API endpoints.

## 2. How We Use Data
The Bot accesses the Threads API solely to:
* Publish curated news summaries (posts) to your authorized Threads account.
* Fetch recent mentions or replies to your posts (if explicitly enabled) for the sole purpose of responding to interactions.
* Update your Threads profile bio (if explicitly enabled) with automated bot telemetry.

## 3. Data Sharing and Third Parties
* **No Sharing:** We do not sell, trade, or share any data with third-party companies, marketers, or external entities.
* **Meta API:** Your data is processed directly via the Meta Threads API in accordance with the [Meta Developer Policies](https://developers.facebook.com/policy/).

## 4. Data Retention
BluBot operates in a stateless environment. It does not run a persistent database for personal information. The only local state persisted is public metadata (such as seen news article URLs) to prevent duplicate posts, which is stored in your private repository.

## 5. Revoking Access
You can revoke BluBot's access to your Threads account at any time by:
1. Removing the credentials from your hosting environment (GitHub Secrets).
2. Navigating to your Threads account settings (under Website Permissions) and de-authorizing the application.

## 6. Contact & Support
If you have any questions about this Privacy Policy, please open an issue in the public GitHub repository where this bot is hosted.
