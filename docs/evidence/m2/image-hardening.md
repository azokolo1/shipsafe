# M2 - Container image hardening (measured 2026-10-19, Trivy 0.75.0)

| | Naive (`python:3.12`, single stage) | Hardened (multi-stage, slim, digest-pinned) |
|---|---|---|
| Compressed size | 489 MB | 73.4 MB; 75.1 MB after pip removal (deletion layer cannot reclaim base-layer space) |
| CRITICAL | 17 | 0 |
| HIGH | 357 | 44 (all Debian OS packages, no fix published) |
| HIGH/CRITICAL with a fix available | - | 0 (CI gate passes) |
| Runs as | root (uid 0) | app (uid 10001) |
| Read-only root filesystem | no | yes (verified) |
| Graceful shutdown (`docker stop`) | - | 0.575 s (exec-form CMD, Python is PID 1) |
| pip in runtime image | yes | removed |

## Triage of remaining findings
- All remaining HIGH findings are Debian base OS packages (util-linux, perl-base, ncurses)
  with status `affected`/`fix_deferred` - no patched version exists yet.
- Python dependencies: no HIGH/CRITICAL findings.
- Not reachable in this workload: mount-related util-linux CVEs need CAP_SYS_ADMIN (container
  runs non-root with all capabilities dropped); perl Archive::Tar is never invoked.
- CI policy: fail on CRITICAL and on fixable HIGH; report unfixed findings to GitHub code
  scanning; scheduled rebuilds pick up base-image fixes.
