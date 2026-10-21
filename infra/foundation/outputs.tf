output "zone_id" {
  description = "Route 53 hosted zone ID for the ShipSafe subdomain."
  value       = aws_route53_zone.shipsafe.zone_id
}

output "name_servers" {
  description = "Add these as the NS record for the subdomain in the parent zone."
  value       = aws_route53_zone.shipsafe.name_servers
}

output "certificate_arn" {
  description = "ACM certificate ARN. Usable once its status is ISSUED."
  value       = aws_acm_certificate.shipsafe.arn
}

output "ecr_repository_url" {
  description = "ECR repository URL for the application image."
  value       = aws_ecr_repository.app.repository_url
}
