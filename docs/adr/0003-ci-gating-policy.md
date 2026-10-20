# ADR-0003: CI gating policy for `main`

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

ShipSafe is developed by one person, but it should demonstrate the controls a team would rely on. Without enforcement, any gate can be skipped by pushing straight to `main`, merging while checks are red, or using `--no-verify` locally.

## Decision

1. A `protect-main` repository ruleset on the default branch: PR required, squash merge only, linear history, no deletion, no force push, **no bypass actors**.
2. One required check, `ci-ok`, pinned to the GitHub Actions app (`integration_id` 15368), in strict mode (the branch must be up to date with `main`).
3. Required approvals set to **0**. This is a solo-maintainer compromise; a team setting would require at least 1 approval, with last-push approval.
4. Image gate: fail on CRITICAL, or HIGH with a fix available; upload all findings as SARIF.
5. Secret gate: scan only the PR's commits on pull requests, and full history on `main`.
6. Supply chain: actions allow-list, SHA pinning required, read-only default token, checksum-verified tools, digest-pinned images, weekly Dependabot.

## Consequences

- Every change to `main`, including the maintainer's own, goes through CI. This was verified by gate tests 0 and A.
- Unfixed OS CVEs stay visible as alerts but don't block delivery; they need periodic review.
- A new job must be added to `ci-ok`'s `needs`, or it won't gate anything.
- Strict mode means a PR must be updated after every merge to `main` (`gh pr update-branch`).

## Alternatives considered

- **CRITICAL-only image gate:** rejected. Gate test D (5 HIGH, 0 CRITICAL, all fixable) would have passed.
- **Requiring every job individually in the ruleset:** rejected. Renaming a job would silently break protection.
- **gitleaks `--all` on PRs:** rejected after gate test D, where a leak on another branch failed an unrelated PR. GitHub secret scanning covers all branches instead.
- **Admin bypass for emergencies:** rejected. There is no production traffic, and a bypass makes the evidence meaningless.

## Evidence

[`docs/evidence/m2/gate-tests.md`](../evidence/m2/gate-tests.md)
