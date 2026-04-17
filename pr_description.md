## Description
This Pull Request implements a comprehensive, automated test suite for **BluBot v3.6.5** and synchronizes all project documentation to reflect these new quality standards.

### Key Changes
- **Automated Test Suite**: Added 14 tests in `src/tests/` using `pytest`.
    - `test_utils.py`: SSRF protection and image processing.
    - `test_curator.py`: Scoring engine weights and synergy bonus logic.
    - `test_logger.py`: Secret redaction and JSON formatting.
    - `test_config.py`: Configuration validation.
- **Documentation Sync**: 
    - Updated `README.md` with testing instructions.
    - Added **Page 9** to `docs/WIKI_MANUAL.md` for Quality Control.
    - Updated `CONTRIBUTING.md` and `SECURITY.md`.
- **CI Hardening**: Updated `.github/workflows/test.yml` to enforce the 14-test suite on all PRs.
- **Automated Releases**: Refactored `release.yml` to automatically create tags and GitHub Releases upon PR merge, extracting changelogs from `README.md`.
- **Version Sync**: Bumped [VERSION](file:///d:/Code/BlueSky/VERSION) to `3.6.5`.
- **Legacy Diagnostics**: Refactored `test_models.py` to use shared internal logic while preserving its interactive developer playground features.

### Verification Results
- 100% pass rate on all 14 automated tests.
- Manual verification of scoring breakdown in `test_models.py`.

*Built with ❤️ for the AI Community*
