# 🚀 PR v3.13.2: Telegram Approval Queue Timeout Calibration

This PR fixes a polling timeout drift issue in the Telegram approval gateway where network call latencies and long polling cause the actual wall-clock elapsed time to exceed the configured timeout (e.g. waiting 7.5 minutes instead of 5 minutes).

## Proposed Upgrades

### 🔄 1. Wall-Clock Timeout Tracking
- Uses `time.time()` to measure exact wall-clock elapsed time instead of relying on loop iteration counts (`elapsed += poll_interval`).
- Ensures the bot auto-posts exactly when the configured duration expires, preventing execution from being delayed.

---

## 🛠️ Compliance with `AGENTS.md` Rules

### 1. What was Deleted or Simplified
- Removed the manual iteration-counting variable (`elapsed`) and its increments from the polling loop, simplifying timeout tracking by relying directly on standard library wall-clock calls.

### 2. Why the Simpler Version is Safe
- It uses standard epoch timestamp comparison, which is robust, resilient to network jitter, and has zero dependency changes.

### 3. Verification & Tests Run
- Verified that all unit tests continue to pass (48/48 tests successful).
- Ran a local simulated loop check to confirm exact exit time matching.
