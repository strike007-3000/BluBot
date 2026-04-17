# 📖 BluBot Elite Sage: The Complete Manual

Welcome to the official Wiki for the **Elite Sage** (BluBot v3.6.3). This guide balances the technical inner workings with the "Sage" persona's philosophy.

---

## 🏠 Page 1: The Sage Philosophy

The BluBot is an **Impact-Aware Intelligence** designed to separate the *signal* from the *noise*.

### The Vision
The Sage looks for **Product Shifts** (real code) and **Technical Gems** (research papers, deep engineering blogs). It shares findings as a mentor, not just a news aggregator.

### Platform Synergy
- **Bluesky**: The central technical hub.
- **Mastodon**: The academic and decentralized pulse.
- **Threads**: The broad industry narrative.

---

## 🧠 Page 2: Breakthrough Scoring Engine v3

The "Brain" of the bot ranked by a weighted matrix.

### The Scoring Pipeline
1. **Source Tiering**: Tier 1 (+30), Tier 2 (+15), Hidden Gems (+25).
2. **Signal Boosting (+12)**: Keywords like *SOTA, Agentic, World Model, Open Weights*.
3. **Momentum (+18)**: flagship entities like *GPT-5, Llama 4, Gemini 3*.
4. **Consensus Synergy (+15)**: Applied if a story is found in multiple independent feeds.
5. **Diversity Penalty (-25)**: Prevents single-topic echo chambers.

---

## 🛡️ Page 3: Reliability & The Fortress (v3.6.3)

The Sage is designed to be **unbreakable**.

### The Failover Loop
- **Primary**: Gemini 3.1 Flash Lite.
- **Failovers**: Gemma 4 (31B/26B), Gemma 3 (27B-IT).

### Hardening Features
- **Zero-Clobber Persistence**: Uses a linear rebase-and-push strategy on the `automated/state` branch with `--autostash` to prevent dirty worktree aborts.
- **Zero-Duplicate Threads Strategy**: Wraps final Threads delivery in a "Catch & Log" block. If the response fails, it logs a warning instead of retrying the whole post, preventing accidental duplicate threads.
- **The Fortress**: Unified logging system (`SafeLogger`) that dynamically masks all environment secrets and tokens.

---

## 🎨 Page 4: NVIDIA NIM Image Generation (v3.6)

The Sage uses **Stability AI Stable Diffusion 3 Medium** via NVIDIA's Inference Microservices as the primary image provider.

### The Designer Pipeline
1. **Lead Selection**: Scrape metadata.
2. **Logo Filter**: Automatically identifies and skips generic site logos (e.g., arXiv logo).
3. **NVIDIA Generation**: Calls the SD3 NIM with professional minimalist isometric prompts.
4. **Base64 Processing**: High-fidelity decoding into raw bytes for platform-specific broadcasting.

---

## 🛰️ Page 5: Source Intelligence

Scanning over **30 premium feeds**.
- **Tier 1**: OpenAI, DeepMind, Anthropic, HuggingFace, Mistral.
- **Hidden Gems**: ArXiv (CS.AI/LG), BAIR (Berkeley), SAIL (Stanford), NVIDIA Research.

---

## ⚙️ Page 6: Technical Configuration (v3.6.3)

### Environment Secrets
| Variable | Description |
| :--- | :--- |
| `GEMINI_KEY` | Google AI Studio Key |
| `NVIDIA_KEY` | NVIDIA Build API Key (for SD3) |
| `BSKY_HANDLE` | Your Bluesky handle |
| `BSKY_APP_PASSWORD` | BlueSky App Password |
| `IMAGE_PROVIDER` | `nvidia` (default) or `imagen` |

---

## 🧪 Page 7: Local Testing & Interactive Diagnostics

The Sage provides a robust **Full Pipeline Dry Run** via `test_models.py`.

### Interactive Key Management
You can test the entire bot locally **without social media credentials**. 
1. **Interactive Entry**: If `GEMINI_KEY` or `NVIDIA_KEY` are missing from your `.env`, the script will prompt you to paste them in the console.
2. **Offline Logic**: Config engine injects "Mock" values for `BSKY_HANDLE`, ensuring you only need your AI keys to verify the synthesis.

### Running the Diagnostic
```bash
python test_models.py
```
Select **Option 2 (FULL PIPELINE DRY RUN)** to see a draft review of exactly what will be posted.

---

## 💾 Page 8: Linear State Persistence

To protect your "Seen Articles" history on a restricted repository, the bot uses a dedicated `automated/state` branch.

### The 'Zero-Clobber' Strategy
1. **Concurrency Guard**: Ensures only one bot run updates the state at a time.
2. **Autostash Rebase**: Performs `git pull --rebase --autostash` to merge `seen_articles.json` and `README.md` safely without workspace conflicts.

---
*Built with ❤️ for the AI Community*
