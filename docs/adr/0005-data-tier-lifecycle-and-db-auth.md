# ADR-0005: Data tier lifecycle and database authentication

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

M4 adds an asynchronous job flow: the API records a job and enqueues its ID on SQS; a worker service processes it and records the outcome in PostgreSQL. The platform stack is destroyed after every session (ADR-0004), and the monthly budget alert is $40.

Prices for eu-west-2, retrieved from the AWS Pricing API on 2026-10-22 (USD, excluding VAT):

| Item | Price |
|---|---|
| RDS `db.t4g.micro` PostgreSQL, Single-AZ | $0.018 per hour |
| RDS gp3 storage | $0.133 per GB-month |
| Secrets Manager | $0.40 per secret per month |
| SQS standard requests | $0.40 per million (first million per month free) |

## Decision 1: RDS is ephemeral

RDS (`db.t4g.micro`, 20 GB gp3, Single-AZ, PostgreSQL 17) lives in `infra/platform` and is created and destroyed with it.

| Option considered | Cost | Why not chosen |
|---|---|---|
| **Ephemeral (chosen)** | ~$0.022/hour while up, $0 between sessions | — |
| Always on | ~$16/month | 40% of the budget for an idle database; would also make the VPC persistent |
| Stopped between sessions | ~$2.70/month storage | Needs a persistent VPC, and AWS restarts a stopped instance after 7 days |
| Snapshot on destroy, restore on apply | pennies of snapshot storage | Slower than create, and fiddly Terraform, to keep data a demo does not need |
| Aurora Serverless v2 (scales to zero) | storage only when paused | Costs more than `t4g.micro` while active; needs a persistent VPC. Compared in M10 |

Consequences: data does not survive a session, and every session rebuilds the schema from migrations on an empty database, so broken migrations surface immediately. Sessions get longer by the RDS create and delete time (measured in M4C).

## Decision 2: no application password

- RDS manages the master password in Secrets Manager (`manage_master_user_password`). Only a **one-off migration task** receives it, injected by ECS from the secret.
- The application connects as `shipsafe_app`, a role with `SELECT, INSERT, UPDATE` on `jobs` only (no `DELETE`, no DDL), using **IAM database authentication**: a token signed from the ECS task role, valid 15 minutes, generated for each new connection. No application password exists anywhere.
- TLS is verified (`sslmode=verify-full`) against the Amazon RDS CA bundle for eu-west-2, shipped in the image.

## Decision 3: delivery semantics

- The database is the source of truth; the SQS message carries only the job ID.
- **At-least-once:** the worker deletes a message only after the outcome is recorded. A job already `done` is never run again, so redelivery is harmless.
- The worker takes **one message at a time**, so the visibility timeout covers exactly one job. The visibility timeout (set in M4B) must exceed the longest job (`MAX_SLEEP_SECONDS` = 60).
- A message that keeps failing is moved to a **dead-letter queue** after 3 receives.

## Decision 4: readiness does not check the database

`/readyz` stays shallow. ECS replaces tasks that fail the ALB health check, so a readiness check on a **shared** dependency would turn a database outage into a restart storm across every task, without fixing anything. Database failures surface as errors on `/jobs` requests and in logs and metrics (M6).

## What production would do differently

Multi-AZ, deletion protection, automated backups of 7+ days with point-in-time recovery, a final snapshot on delete, Performance Insights, and a parameter group reviewed for connection limits. All are deliberately off here, for cost and teardown speed.
