# M3B: platform network, apply / verify / destroy (2026-10-22)

Stack: `infra/platform` (network only at this stage). Applied from `main` after PR #14, verified, then destroyed in the same session.

## Timings

| Step | Result |
|---|---|
| `terraform apply` | 18 resources, 1m47s (NAT gateway 1m38s of that) |
| `terraform destroy` | 18 resources, 1m44s wall clock including the confirmation prompt (NAT gateway 1m05s) |
| NAT gateway lifetime | about 17 minutes (04:48 to 05:05), billed as one hour: about $0.055 |

## Verification

| Check | Result |
|---|---|
| Subnets | 2 public (10.40.0.0/24, 10.40.1.0/24), 2 private (10.40.10.0/24, 10.40.11.0/24) across `euw2-az1` and `euw2-az2`; `MapPublicIpOnLaunch` false on all four |
| Public route table | `0.0.0.0/0` to the internet gateway |
| Private route table | `0.0.0.0/0` to the NAT gateway; S3 prefix list `pl-7ca54015` to the gateway endpoint |
| NAT gateway | `available` in the public subnet in `euw2-az1` |
| Default security group | no ingress and no egress rules |
| After destroy | no VPC, NAT gateway or Elastic IP tagged `Project=shipsafe` |

## Findings

1. **AZ IDs are not AZ names.** In this account `euw2-az1` is `eu-west-2c` and `euw2-az2` is `eu-west-2a`. Choosing "the first two AZ names" would have selected different physical zones (2a and 2b). The stack pins zone IDs, which Checkov (CKV_AWS_394) prompted.
2. **The S3 gateway endpoint uses AWS's default full-access policy** (`Action "*"`, `Principal "*"`, `Resource "*"`). Checkov did not flag it. Restricting it to the regional ECR layer bucket and the project's own buckets is on the M10 hardening list.
3. **The NAT gateway reports `availability_mode = "zonal"`.** The provider exposes a regional NAT gateway mode, which may address the single-NAT AZ risk in ADR-0004. Not yet verified for behaviour or cost; listed for M10.

What this step does not prove: that traffic flows. Nothing ran in the private subnets until M3C.
