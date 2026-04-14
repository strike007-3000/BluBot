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

## Current Security Baseline (v3.2)
The project is currently hardened against:
- **Dependency Exploits**: All core packages are locked to safe versions (resolving CWE-122, CWE-444, etc.).
- **Secret Leaks**: `SafeLogger` dynamically redacts API tokens and handles from logs.
- **Data Corruption**: Atomic state persistence via `.tmp` swap logic.

*Thank you for helping keep the Sage secure!*
