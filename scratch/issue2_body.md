### Description
GitHub Actions logs are reporting that Node.js 20 is deprecated and forcing a run on Node.js 24.

### Actions Affected
- `actions/cache/restore@v4`
- `actions/cache/save@v4`
- `actions/checkout@v4`
- `actions/setup-python@v5`

### Proposed Fix
Update workflows to ensure latest action versions are used and review the `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` environment flag. Also consider pinning to `@v5` where applicable for checkout/python.
