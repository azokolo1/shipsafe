# ADR-0001: Remote Terraform state in S3 with native S3 locking

- Status: Accepted
- Date: 2026-10-11

## Context
Terraform state records every managed resource and can contain sensitive values.
It must be shared between my workstation and CI, protected from concurrent writes,
recoverable after a bad write, and encrypted. Historically the S3 backend needed a
DynamoDB table for locking; HashiCorp has since deprecated DynamoDB-based locking
in favour of native S3 locking (`use_lockfile`, Terraform >= 1.10).

## Decision
- Store state in a dedicated S3 bucket in the ShipSafe workload account (eu-west-2).
- Lock with native S3 lock files (`use_lockfile = true`); no DynamoDB table.
- Encrypt with a customer-managed KMS key (rotation on, explicit key policy).
- Versioning on, with non-current versions expiring after 90 days.
- Public access blocked, TLS-only bucket policy, BucketOwnerEnforced ownership.
- `prevent_destroy` on the bucket.
- Provider guardrail `allowed_account_ids` so Terraform cannot run against another account.
- Bootstrap applied once with local state, then migrated into the bucket it created.

## Alternatives considered
- **DynamoDB locking:** deprecated, and adds a second resource to manage and pay for.
- **HCP Terraform / Terraform Cloud:** good managed option, but adds an external
  dependency and hides the mechanics I want to demonstrate.
- **Local state:** no sharing with CI, no locking, no recovery.

## Consequences
- One fewer AWS resource to secure and pay for.
- Requires Terraform >= 1.10 everywhere (workstation and CI).
- Accepted Checkov exceptions in portfolio mode, documented inline in `state.tf`:
  CKV_AWS_18 (access logging), CKV_AWS_144 (cross-region replication),
  CKV2_AWS_62 (event notifications). The production reference enables access
  logs/S3 data events and replicates state to a second region.

## Verification
- `terraform plan` from two sessions: the second fails with "Error acquiring the state lock".
- `terraform.tfstate.tflock` is visible in the bucket while a lock is held.
- With a wrong `allowed_account_ids`, plan fails with "AWS account ID not allowed".
- After migration, `terraform plan` reports "No changes".
