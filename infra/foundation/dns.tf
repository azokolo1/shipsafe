# Delegated subdomain. The parent zone (regopsintelligence.com) is in another AWS
# account and holds one NS record pointing at this zone's name servers.
# Recreating this zone would assign new name servers and break that delegation,
# which is why it lives in the persistent stack and cannot be destroyed by accident.
resource "aws_route53_zone" "shipsafe" {
  #checkov:skip=CKV2_AWS_38:DNSSEC needs a us-east-1 KMS key plus a DS record in the parent zone (other account). Deferred to M10.
  #checkov:skip=CKV2_AWS_39:Query logging needs a us-east-1 log group. Public demo zone; revisit in M6 observability.
  name    = var.domain_name
  comment = "ShipSafe portfolio project, delegated from regopsintelligence.com"

  lifecycle {
    prevent_destroy = true
  }
}
