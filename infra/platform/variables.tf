variable "region" {
  description = "AWS region for ShipSafe resources."
  type        = string
  default     = "eu-west-2"
}

variable "owner" {
  description = "Value for the Owner tag."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the ShipSafe VPC. /24 subnets are carved from it."
  type        = string
  default     = "10.40.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && tonumber(split("/", var.vpc_cidr)[1]) <= 20
    error_message = "vpc_cidr must be a valid IPv4 CIDR of /20 or larger."
  }
}

# Zone IDs (euw2-az1...), not names (eu-west-2a...): names are shuffled per account,
# IDs are the same physical AZ everywhere. Pinned so the subnet layout never changes
# just because AWS adds an AZ.
variable "availability_zone_ids" {
  description = "Exactly two AZ IDs to spread the platform across."
  type        = list(string)
  default     = ["euw2-az1", "euw2-az2"]

  validation {
    condition     = length(var.availability_zone_ids) == 2
    error_message = "Exactly two AZ IDs are expected (one NAT gateway, two-AZ ALB and service)."
  }
}
