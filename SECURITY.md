# 🛡️ Security Policy: BluBot Elite

We take the security of the BluBot ecosystem and the privacy of our automated posts seriously. As the "Fortress" for AI news curation, we maintain high standards for dependency management and code integrity.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.2.x   | ✅ Active (v3.2)   |
| 3.1.x   | ❌ Deprecated       |
| < 3.0   | ❌ End of Life      |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please use the **GitHub "Private Vulnerability Reporting"** feature:
1.  Navigate to the [Security](https://github.com/strike007-3000/BluBot/security) tab of this repository.
2.  Click on **Vulnerability reporting** in the left sidebar.
3.  Click **Report a vulnerability** to submit your findings privately.

Our team will respond within 48 hours to acknowledge your report and provide a timeline for resolution.

## Current Security Baseline (v3.6.7)
The project is currently hardened against:
- **SSRF Attacks**: metadata fetching is protected by DNS pinning and IP scoping (RFC 1918 blocking), with **automated regression tests** in the CI suite.
- **Secret Leaks**: `SafeLogger` dynamically redacts API tokens and high-entropy strings from logs. Typed `Settings` ensure no raw environment variables are leaked into business logic.
- **Dependency Exploits**: Core packages are locked to safe versions (resolving CWE-1100, etc.).
- **Data Corruption**: Atomic state persistence via cross-platform **Advisory File Locking** (`fcntl`/`msvcrt`) and `.tmp` swap logic.

*Thank you for helping keep the Sage secure!*
