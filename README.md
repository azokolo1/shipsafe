# ShipSafe

A production-style AWS ECS Fargate delivery platform: secure CI/CD with GitHub OIDC, automatic failure detection and rollback, progressive delivery, SLO-based observability and cost controls. Built in public, milestone by milestone.

> Portfolio project, not a commercial production workload.

![ShipSafe production-reference architecture](docs/architecture/shipsafe-prod-reference.png)

## Status

- [x] Architecture design
- [ ] M1: Secure foundations (remote state, budgets, OIDC)

## M2: Application, container and CI gates

- FastAPI API and SQS-style worker: 11 tests, structured JSON logs, graceful SIGTERM shutdown.
- Hardened image: 489 MB to 75.1 MB, CRITICAL findings 17 to 0, non-root (UID 10001), read-only root filesystem. See [image hardening](docs/evidence/m2/image-hardening.md).
- `main` is protected by a ruleset with no bypass. One required check (`ci-ok`) aggregates lint, tests, IaC checks, secret scanning and a Trivy image gate. See [CI/CD](docs/ci-cd.md) and [ADR-0003](docs/adr/0003-ci-gating-policy.md).
- Five gate tests (direct push, failing test, fake secret, vulnerable dependency, missing CI) were all blocked. See [evidence](docs/evidence/m2/gate-tests.md).
