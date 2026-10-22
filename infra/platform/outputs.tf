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
