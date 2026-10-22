# M3A: persistent foundation (2026-10-22)

Stack: `infra/foundation`. Applied from `main` after PR #13. Cost: about $0.51/month (hosted zone $0.50; ECR storage under $0.01; ACM and basic scanning free).

## Accounts involved

| Role | Account |
|---|---|
| Domain registration (`regopsintelligence.com`), auto-renew and transfer lock on | 577483322388 |
| Parent hosted zone, holding the `shipsafe` NS record | 337909737271 |
| Delegated zone, certificate, ECR, ShipSafe workload | 699281550756 |

## What was created

| Resource | Result |
|---|---|
| Route 53 zone `shipsafe.regopsintelligence.com` | `Z08983978BEYHX7WWGTE`, name servers `ns-1015.awsdns-62.net`, `ns-1216.awsdns-24.org`, `ns-15.awsdns-01.com`, `ns-1691.awsdns-19.co.uk` |
| ACM certificate | DNS-validated, status `ISSUED` at 04:01:30 |
| ECR repository `shipsafe` | immutable tags, scan on push, lifecycle (untagged after 1 day, keep last 10) |
| First image | tag `98f94bb`, `sha256:61db8ec7f12b8a56a7377c80d96f34cfcadc01857d0a3e3d16709efaf1558b79`, OCI image manifest, 75,104,103 bytes in ECR |

The parent domain was not changed apart from the one NS record: MX still resolves to `smtp.google.com`.

## Problems found and fixed

### 1. Self-referencing delegation

The first `shipsafe` NS record in the parent zone listed the parent's own name servers. Asking the parent server directly showed it immediately:

```
dig NS shipsafe.regopsintelligence.com @ns-189.awsdns-23.com +norec +noall +authority
```

The certificate stayed `PENDING_VALIDATION` and public resolution returned nothing. After the record was corrected to the four delegated servers, Google (8.8.8.8) and Cloudflare (1.1.1.1) both resolved the validation CNAME, and ACM issued the certificate about 15 minutes later on its own retry. Nothing was recreated.

### 2. BuildKit attestation turned the push into an image index

`docker build` added a provenance attestation by default, so the push created an image index (tagged) plus two untagged children: the image and the attestation. ECR scan-on-push had nothing to scan under the tag, and the real image was untagged, which put it at risk from the "expire untagged after 1 day" lifecycle rule. Fixed by deleting all three and rebuilding with `--provenance=false --sbom=false`. The image digest was unchanged (`sha256:61db8ec7…`): same content, without the wrapper. Signed provenance is planned for M5.

### 3. Two scanners, two answers

| Scanner | Scope | Result |
|---|---|---|
| ECR basic scanning, image `98f94bb` | OS packages | 0 CRITICAL, 3 HIGH, 9 MEDIUM, 3 LOW |
| Trivy 0.75.0, code scanning on `main` at the end of M2 (same base image digest) | OS and Python packages | 8 distinct HIGH CVEs (44 alerts), 0 CRITICAL, none fixable |

Different databases and severity sources. Both are recorded as measured; neither is treated as the single truth.
