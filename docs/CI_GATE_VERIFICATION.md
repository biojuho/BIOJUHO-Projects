# CI Quality Gate Verification

This file verifies that the Security & Quality Gate workflow runs correctly on PRs.

## What this PR tests

1. **smoke-test** job — workspace smoke tests with PYTHONUNBUFFERED and 5-min timeout
2. **qa-review** job — Bandit/Ruff analysis with automatic PR comment reporting
3. **security-contracts** job — security gate contract validation
4. **quality-gate** job — final summary gate that blocks merge on failure

## Expected behavior

- All 4 jobs should run and produce a green check
- A QA summary comment should be automatically posted on this PR
- The Quality Gate status check should be required for merge

---

*This file can be deleted after verification.*
