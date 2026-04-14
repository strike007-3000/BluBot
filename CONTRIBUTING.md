# 🤝 Contributing to BluBot Elite

Welcome, Technical Sage. We are thrilled that you want to help broaden the perspective of the BluBot ecosystem. To maintain the **Elite Signal Strength** and the **Persona Integrity** of the bot, we follow a strict set of architectural and community guidelines.

## 🧠 The Sage Philosophy
BluBot is not just a bot; it's an **Impact-Aware Intelligence**. Our goal is to synthesize complex technical breakthroughs into human-centric insights. Every contribution should serve the vision of "Signal over Noise."

## 🧱 Architectural Guardrails
1.  **Asynchronous First**: All network operations must use `asyncio` and `httpx`. No blocking calls in the main pipeline.
2.  **The Fortress (Security)**: All logging must pass through `src/logger.py:SafeLogger` to ensure secret masking. Always use atomic writes for persistence.
3.  **Modular Logic**: Platform logic belongs in `src/broadcaster.py`, and curation logic belongs in `src/curator.py`. Keep `bot.py` lean as an orchestrator.

## ⚖️ "Signal Verification" for AI-Assisted Code
We welcome the use of AI coding assistants (like Gemini, Claude, or GPT), but with a **hard requirement for manual verification**:
- **Audit All Dependencies**: AI assistants may occasionally "hallucinate" package names or suggest insecure/deprecated versions. You MUST manually verify that every `import` and `requirement` is current and safe.
- **Dependency Locking**: Never add a package to `requirements.txt` without pinning it to a safe version.
- **Logic Sanity Checks**: Ensure AI-generated regex or parsing logic is ReDoS-safe and handles malformed data gracefully.

## 🚀 The PR Workflow
1.  **Fork & Branch**: Create a descriptive branch (e.g., `feature/atproto-facets` or `fix/bibtex-parsing`).
2.  **Test Before You Post**: Run `python test_models.py` and verify all diagnostic scores pass.
3.  **The "Merge" Requirement**: Your PR must pass the **CI Verification (`test`)** and **CodeQL Analysis** before it will be considered for a merge.
4.  **Documentation**: If you change the persona or scoring engine, update [WIKI_MANUAL.md](docs/WIKI_MANUAL.md) to reflect the shift.

*By contributing, you agree that your work will be licensed under the MIT License of this repository.*
