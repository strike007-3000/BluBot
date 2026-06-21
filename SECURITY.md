# 🛡️ Security Policy: BluBot Elite

We take the security of the BluBot ecosystem and the privacy of our automated posts seriously. As the "Fortress" for AI news curation, we maintain high standards for dependency management and code integrity.

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 3.13.x  | ✅ Active (Current) |
| 3.12.x  | ✅ Security patches only |
| 3.11.x  | ❌ Deprecated |
| 3.10.x  | ❌ Deprecated |
| < 3.10  | ❌ End of Life |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please use the **GitHub "Private Vulnerability Reporting"** feature:
1.  Navigate to the [Security](https://github.com/strike007-3000/BluBot/security) tab of this repository.
2.  Click on **Vulnerability reporting** in the left sidebar.
3.  Click **Report a vulnerability** to submit your findings privately.

Our team will respond within 48 hours to acknowledge your report and provide a timeline for resolution.

## Current Security Baseline (v3.13.3)

The project is currently hardened against:

- **SSRF Attacks**: Metadata fetching is protected by **DNS Pinning** and **IP Scoping** (RFC 1918 blocking), with automated regression tests in the CI suite (`src/tests/`).
- **Secret Leaks**: `SafeLogger` dynamically redacts API tokens and high-entropy strings from all log outputs. The typed `Settings` singleton ensures no raw environment variables are leaked into business logic layers.
- **Dependency Exploits**: Core packages are locked to safe versions via `pip-tools` with cryptographic hashes in `requirements.txt` (resolving CWE-1100 and supply chain risks). Dependabot is configured with version constraints to prevent unresolvable upgrade loops.
- **Data Corruption**: Atomic state persistence via cross-platform **Advisory File Locking** and `.tmp` swap logic prevents race conditions during concurrent CI and local runs.
- **Decompression Bomb DoS**: Pillow's image loading engine is restricted to a maximum of `10,000,000` pixels (`Image.MAX_IMAGE_PIXELS`) to prevent memory exhaustion attacks when fetching remote media.
- **Telegram Impersonation**: The Telegram approval gateway validates all incoming callback queries and message updates against the configured `TELEGRAM_USER_ID`, silently discarding interactions from unauthorized senders.
- **Zero-Duplicate Threads Logic**: A "Catch & Log" delivery model persists successfully broadcast post identifiers immediately on partial failure, preventing duplicate re-posts on subsequent runner restarts.
- **Resilient RSS Parsing**: Parses raw bytes (`response.content`) with safe attribute lookups (`getattr(entry, 'link', None)`) to survive malformed XML without exposing the pipeline to injection risks.

*Thank you for helping keep the Sage secure!*
