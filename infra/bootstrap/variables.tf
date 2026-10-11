variable "region" {
  description = "AWS region for the bootstrap resources"
  type        = string
  default     = "eu-west-2"
}

variable "owner" {
  description = "Owner tag value"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format"
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget in USD"
  type        = number
  default     = 40
}

variable "budget_email" {
  description = "Email address for budget alerts"
  type        = string
  sensitive   = true
}
