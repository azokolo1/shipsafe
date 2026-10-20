# M2 gate tests (2026-10-20)

Each test tried to land a bad change on `main` after the `protect-main` ruleset and the Actions lockdown were in place.

| Test | Attempt | Caught by | Outcome |
|---|---|---|---|
| 0 (PR #3) | Merge a PR that had no CI run | Ruleset: required check `ci-ok` missing | `the base branch policy prohibits the merge` |
| A | `git push origin main` (empty commit) | Ruleset | `GH013: Changes must be made through a pull request` / `Required status check "ci-ok" is expected` |
| B (PR #6) | `/healthz` returns `degraded` | `app / lint + test` failed; `image` skipped; `ci-ok` failed | Merge refused |
| C (PR #7) | Random fake AWS key ID (`AKIA` + 16 chars, no account) | pre-commit gitleaks (`aws-access-token`); CI `secrets / gitleaks`. Push protection did **not** block it | Merge refused |
| D (PR #8) | `cryptography==3.3.1` | `image`: Trivy reported 5 HIGH, 0 CRITICAL, all fixable (incl. CVE-2020-36242, fixed in 3.3.2) | Merge refused |

All demo PRs were closed unmerged and their branches deleted.

## Findings and fixes (PR #9)

1. **Cross-branch secret false positive.** In test D, `secrets / gitleaks` also failed: it scanned 11 commits, including commit `1039215` from test C's branch. `fetch-depth: 0` plus gitleaks' default `--all` scanned every branch. Fix: PRs scan `base..head` only; `main` scans full history.
2. **Dependabot proposed Python 3.15** (PR #4); `requires-python` is `<3.13`. Fix: ignore minor and major tag updates for `python`; digest updates continue.
3. **certifi critical alert** (GHSA-6q48-6c7w-9gw2). `uv tree --no-dev` shows certifi is dev-only (via `httpx`), so it is not in the image and Trivy correctly did not report it. Patched anyway: `2026.10.18 -> 2026.10.19`.

## Image hardening

See [`image-hardening.md`](image-hardening.md). Code scanning at the end of M2: 44 open Trivy alerts, 8 distinct CVEs, all without a fix (screenshots `code-scanning-trivy-p1.png` and `-p2.png`).
