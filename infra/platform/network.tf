# ShipSafe platform network (ADR-0004, option A).
# Two AZs. Public subnets hold only the ALB and the NAT gateway; ECS tasks run in
# private subnets with no public IPs. One NAT gateway (cost compromise, see ADR-0004);
# S3 traffic, which carries ECR image layers, uses a free gateway endpoint instead.
# This stack is destroyed at the end of every working session.

locals {
  name = "shipsafe"
  azs  = var.availability_zone_ids

  # 10.40.0.0/24, 10.40.1.0/24 public; 10.40.10.0/24, 10.40.11.0/24 private
  public_subnets  = { for i, az in local.azs : az => cidrsubnet(var.vpc_cidr, 8, i) }
  private_subnets = { for i, az in local.azs : az => cidrsubnet(var.vpc_cidr, 8, 10 + i) }
}

resource "aws_vpc" "main" {
  #checkov:skip=CKV2_AWS_11:Flow logs are added with the rest of the logging in M6; this stack is short-lived and carries no user traffic yet.
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = local.name }
}

# The default security group allows all traffic between its members. Nothing uses
# it, so strip every rule to make accidental use fail closed.
resource "aws_default_security_group" "default" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${local.name}-default-unused" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = local.name }
}

# --- Public subnets: ALB and NAT gateway only -------------------------------

resource "aws_subnet" "public" {
  for_each = local.public_subnets

  vpc_id                  = aws_vpc.main.id
  availability_zone_id    = each.key
  cidr_block              = each.value
  map_public_ip_on_launch = false

  tags = { Name = "${local.name}-public-${each.key}", Tier = "public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${local.name}-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# --- NAT gateway (single, in the first AZ) ----------------------------------

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = { Name = "${local.name}-nat" }

  depends_on = [aws_internet_gateway.main]
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[local.azs[0]].id

  tags = { Name = local.name }

  depends_on = [aws_internet_gateway.main]
}

# --- Private subnets: ECS tasks ---------------------------------------------

resource "aws_subnet" "private" {
  for_each = local.private_subnets

  vpc_id               = aws_vpc.main.id
  availability_zone_id = each.key
  cidr_block           = each.value

  tags = { Name = "${local.name}-private-${each.key}", Tier = "private" }
}

# One route table for both private subnets because there is one NAT gateway.
# With a NAT per AZ, each private subnet would get its own table.
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${local.name}-private" }
}

resource "aws_route" "private_nat" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main.id
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

# --- S3 gateway endpoint (free) ---------------------------------------------
# ECR stores image layers in S3. Routing S3 through this endpoint keeps image
# pulls off the NAT gateway and its $0.05/GB processing charge.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = { Name = "${local.name}-s3" }
}
