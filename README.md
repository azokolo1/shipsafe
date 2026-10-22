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

## M3: Network, edge and ECS

- **Three Terraform stacks with different lifetimes:** `bootstrap` (state, identity, budget), `foundation` (delegated DNS zone, ACM certificate, ECR; about $0.51/month), and `platform` (VPC, NAT, ALB, ECS), which is **destroyed after every working session** to stay inside a $40/month budget. See [ADR-0004](docs/adr/0004-egress-and-environment-lifecycle.md) and the [session runbook](docs/runbooks/platform-session.md).
- **HTTPS** on `shipsafe.regopsintelligence.com`: subdomain delegated across AWS accounts, DNS-validated ACM certificate, ALB with TLS 1.3/1.2 and an HTTP-to-HTTPS redirect.
- **ECS Fargate** service: 2 tasks across 2 AZs in private subnets with no public IPs, read-only root filesystem, all Linux capabilities dropped, non-root user, image deployed **by digest**, least-privilege execution role.
- **Measured under continuous traffic:** a rolling deploy served 890/890 requests successfully, with old and new versions side by side for 35.6 s; after one of two tasks was stopped, 118/118 requests succeeded until the replacement registered. See [M3 evidence](docs/evidence/m3/).

The URL only answers while a working session is running; the platform is torn down afterwards.
