## Description
This Pull Request elevates **BluBot** to an enterprise-grade technical standard (v3.6.7) by implementing a major **Elite Architecture Overhaul** and industrial-grade **URL Normalization**.

### 🛠️ Key Architectural Changes (v3.6.7)
- **Typed Pipeline Stages**: Refactored the monolithic `main()` into distinct, immutable handler stages (**Curation → Synthesis → Broadcast → Persistence**) using frozen `src/models.py` dataclasses.
- **Centralized Settings Singleton**: Migrated all environment-aware configuration to `src/settings.py` for professional-grade rigidity and validation.
- **Advisory File-Locking**: Integrated a cross-platform `FileLock` (supporting `fcntl` and `msvcrt`) into `src/utils.py` to protect `seen_articles.json` from race conditions.
- **Industrial URL Normalization**: 
    - Implemented `normalize_url` to resolve protocol-relative links (`//`) and strip aggressive tracking parameters (UTM, ref, fbclid, etc.).
    - **P1 Bug Fix**: Restored exact redirect URL resolution in `get_with_safe_redirects` while keeping normalization for the final landing page (preserving session/token integrity).

### 🧪 Quality & Documentation
- **Verified Regression Suite**: All 15 automated tests (Security, Scoring, Redaction, Settings) are passing.
- **Documentation Overhaul**: Synchronized `README.md`, `WIKI_MANUAL.md`, `CONTRIBUTING.md`, and `SECURITY.md` to reflect the new technical blueprint.
- **CI Enforcement**: Integrated the new `Settings` validation into the standard GitHub Actions test suite.

### Verification Results
- **100% Test Pass Rate** (15/15 tests).
- Successful **Full Dry Run** of the staged pipeline using `test_models.py`.

*Built with ❤️ for the AI Community*
