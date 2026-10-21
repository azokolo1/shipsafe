# Public TLS certificate for the subdomain only (no wildcard: issue what we use).
# Free, and kept here so platform applies don't wait for DNS validation.
# No aws_acm_certificate_validation waiter: ACM keeps retrying validation on its
# own, so this stack applies before the parent-zone NS record exists.
resource "aws_acm_certificate" "shipsafe" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "certificate_validation" {
  for_each = {
    for dvo in aws_acm_certificate.shipsafe.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = aws_route53_zone.shipsafe.zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 300
  records         = [each.value.record]
  allow_overwrite = true
}
