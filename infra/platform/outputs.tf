output "vpc_id" {
  description = "ShipSafe VPC ID."
  value       = aws_vpc.main.id
}

output "availability_zone_ids" {
  description = "AZ IDs the platform spans."
  value       = local.azs
}

output "public_subnet_ids" {
  description = "Public subnet IDs (ALB, NAT gateway)."
  value       = [for s in aws_subnet.public : s.id]
}

output "private_subnet_ids" {
  description = "Private subnet IDs (ECS tasks)."
  value       = [for s in aws_subnet.private : s.id]
}

output "nat_public_ip" {
  description = "Public IP that private-subnet traffic leaves through."
  value       = aws_eip.nat.public_ip
}

output "app_url" {
  description = "Public HTTPS URL of the service."
  value       = "https://${var.domain_name}"
}

output "alb_dns_name" {
  description = "ALB DNS name (the Route 53 alias points here)."
  value       = aws_lb.main.dns_name
}

output "image" {
  description = "Exact image the service runs (repository@digest)."
  value       = "${data.aws_ecr_repository.app.repository_url}@${data.aws_ecr_image.app.image_digest}"
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.api.name
}

output "log_group_name" {
  description = "CloudWatch log group for the API."
  value       = aws_cloudwatch_log_group.api.name
}
