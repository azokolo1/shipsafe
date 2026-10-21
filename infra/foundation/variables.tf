variable "region" {
  description = "AWS region for ShipSafe resources."
  type        = string
  default     = "eu-west-2"
}

variable "owner" {
  description = "Value for the Owner tag."
  type        = string
}

variable "domain_name" {
  description = "Subdomain delegated to this account. The parent zone lives in another AWS account."
  type        = string
  default     = "shipsafe.regopsintelligence.com"
}

variable "ecr_repository_name" {
  description = "ECR repository for the application image."
  type        = string
  default     = "shipsafe"
}

variable "ecr_keep_images" {
  description = "How many of the most recent images ECR keeps."
  type        = number
  default     = 10
}
