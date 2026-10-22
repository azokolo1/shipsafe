# M3C: ALB and ECS Fargate service, first session (2026-10-22)

Stack: `infra/platform` (network + ALB + ECS). Applied from `main` after the M3C PR merged, verified, then destroyed in the same session. Billed as one hour (about $0.13).

## Timings

| Step | Result |
|---|---|
| `terraform apply` | 37 resources, 4m02s. ALB 2m28s and NAT gateway 1m42s in parallel; ECS service 1m24s to steady state |
| `terraform destroy` | 37 resources, 4m25s. ECS service 3m22s (drain and graceful stop); internet gateway 2m55s (see finding 2) |

## Verification

| Check | Result |
|---|---|
| `GET /healthz`, `/readyz`, `/version` over HTTPS | `ok`, `ready`, version `98f94bb` |
| `http://` | `301 Moved Permanently` from the ALB |
| TLS | TLSv1.3, `TLS_AES_128_GCM_SHA256`, X25519; certificate `CN=shipsafe.regopsintelligence.com`, issuer Amazon RSA 2048 M04 |
| Target group | 2 healthy targets, private IPs, one per AZ (`eu-west-2c` = `euw2-az1`, `eu-west-2a` = `euw2-az2`) |
| Tasks | 2 RUNNING and HEALTHY (container health check), both on `sha256:61db8ec7…` |
| Logs | structured JSON in `/ecs/shipsafe/api` with version and request ID |
| IAM | least-privilege execution role (one repository, one log group) and the `aws:SourceArn` trust condition both worked |
| After destroy | no VPC, NAT gateway, Elastic IP, load balancer, active cluster or log group left |

## Self-healing test, and what it does and does not prove

One task was stopped with `aws ecs stop-task` at 18:26:13 (local time). ECS service events:

| Time | Event |
|---|---|
| 18:26:26.9 | target deregistered, connection draining started |
| 18:26:27.8 | replacement task started |
| 18:26:45.9 | replacement registered in the target group |
| ~18:26:59 | service stable (`aws ecs wait services-stable` returned after 46.6 s) |

A loop of 120 requests returned 120 × `200`, **but it was started after the stop**, so it does not show whether any request failed while the task was lost. That measurement was repeated in M3D with a timestamped loop running throughout.

## Findings

1. **Unknown root path.** Opening the URL in a browser returned `{"detail":"Not Found"}`: there was no `GET /` route. Added in M3D.
2. **Missing ALB to IGW dependency.** Terraform began deleting the internet gateway while the internet-facing ALB still held public IPs, so the detach retried for 2m55s and finished 2 seconds after the ALB was deleted. Fixed in M3D with `depends_on = [aws_internet_gateway.main]` on the ALB.
