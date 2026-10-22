# ADR-0004: Network egress and environment lifecycle

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

From M3, ShipSafe runs billable infrastructure: ALB, NAT, Fargate. The monthly budget alert is $40. ECS tasks need outbound access to ECR (image pulls) and CloudWatch Logs. ShipSafe is a portfolio project, not a commercial workload, so it does not need to be online all the time.

On-demand prices for eu-west-2, retrieved from the AWS Pricing API on 2026-10-21 (USD, excluding VAT):

| Item | Price |
|---|---|
| Fargate vCPU | $0.04656 per vCPU-hour |
| Fargate memory | $0.00511 per GB-hour |
| NAT gateway | $0.05 per hour + $0.05 per GB processed |
| Application Load Balancer | $0.02646 per hour (or partial hour) + $0.0084 per LCU-hour |
| Interface VPC endpoint | $0.011 per endpoint per AZ per hour |
| Public IPv4 address | $0.005 per hour |

## Options compared (2 tasks × 0.25 vCPU / 0.5 GB, ALB in 2 AZs)

| Option | Design | ≈ $/hour | 24/7 month | 48 h month |
|---|---|---|---|---|
| A | Private subnets, 1 NAT gateway, S3 gateway endpoint | 0.128 | ~$94 | ~$6.20 |
| B | Private subnets, no internet route, interface endpoints (ECR API, ECR DKR, Logs) | 0.139 | ~$102 | ~$6.70 |
| C | Public subnets, public IPs on tasks, security group admits the ALB only | 0.083 | ~$61 | ~$4.00 |

## Decision

1. **Option A.** Tasks run in private subnets with no public IPs. Egress goes through **one** NAT gateway; S3 traffic (ECR image layers) goes through a free gateway endpoint.
2. **Three stacks with different lifetimes:**
   - `infra/bootstrap`: state, identity, budget. Permanent.
   - `infra/foundation`: Route 53 subdomain zone, ACM certificate, ECR repository. Permanent, about $0.55/month.
   - `infra/platform`: VPC, NAT, ALB, ECS. **Destroyed at the end of every working session.**
3. **DNS:** `shipsafe.regopsintelligence.com` is a hosted zone in the ShipSafe account, delegated by one NS record in the parent zone (another account). The parent domain's name servers, mail and other records are not touched.

## Consequences

- No running configuration fits the $40 budget 24/7, so the destroy discipline is required, not optional.
- ALB and NAT bill per started hour: repeated apply/destroy cycles within an hour each cost a full hour.
- **Single NAT:** if its AZ fails, tasks in the other AZ lose outbound access (new image pulls, log delivery). Production would run one NAT per AZ (about +$0.055/hour).
- Platform resources must be destroy-friendly: no ALB deletion protection, short log retention, and nothing in the platform stack that the next apply depends on.
- The domain registration renews yearly in account 577483322388, so it does not count against the ShipSafe budget in 699281550756.
- ShipSafe DNS depends on one `shipsafe` NS record in the parent zone, which lives in the RegOps account (337909737271). If that record is deleted, the hostname stops resolving and the certificate cannot renew. The parent zone's comment records the dependency; an M6 check will alert on broken delegation.

## Alternatives considered

- **Option B:** strongest posture (no internet path). Rejected for now because every new AWS dependency needs its own endpoint (about +$0.022/hour each), which adds friction while the service is still taking shape. It will be measured against A in M10.
- **Option C:** cheapest, but tasks with public IPs depend on one security group for isolation. The saving is about $2/month at expected usage.
- **A NAT per AZ:** the production pattern. Rejected on cost for a demo with no users.
- **A dedicated domain:** cleaner separation from the RegOps brand. Not chosen; the subdomain costs nothing extra.
