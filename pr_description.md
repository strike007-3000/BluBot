# PR Description: Supply Chain Resilience & Dependabot Mitigation (v3.11.2) 🛡️🤖

This PR resolves a critical Dependabot updater failure by aligning package version bounds and configuring version pinning rules.

## 🌟 Key Updates

### 1. Supply Chain Constraints
- Updated `cryptography` in `requirements.in` from a rigid pin (`cryptography==46.0.7`) to a range constraint (`cryptography>=46.0.7,<47`).
- This satisfies the transitive constraint of the `atproto` SDK client library, which strictly restricts `cryptography<47,>=41.0.7`.

### 2. Dependabot Configuration
- Configured `.github/dependabot.yml` to ignore upgrades for `cryptography` to versions `>= 47.0.0`.
- This prevents the Dependabot updater from getting stuck in an unresolvable dependency cycle, while still allowing it to parse and submit PRs for security updates within the `46.x` branch.

### 3. Dependency Compilation
- Recompiled `requirements.txt` using `pip-compile`. It successfully locked `cryptography` to `46.0.7` without conflict and generated all corresponding cryptographic hashes.

### 4. Telemetry Alignment
- Checked and verified live-telemetry status in `STATUS.md`.

## 🧪 Verification & Testing
- ✅ **Test Coverage**: All 36 tests in `src/tests/` passed successfully (including verification of settings and curation).
- ✅ **Upgraded Local Validation**: Verified local package resolution and confirmed compatibility.

---
*Ensuring Continuous Delivery Pipeline Uptime via Dependabot Hardening - Ready for Merge*
