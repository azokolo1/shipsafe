provider "aws" {
  region = var.region

  # Guardrail: Terraform refuses to touch any other account
  allowed_account_ids = ["699281550756"]

  default_tags {
    tags = {
      Project     = "shipsafe"
      Environment = "shared"
      Owner       = var.owner
      ManagedBy   = "terraform"
      Repository  = var.github_repo
      CostCentre  = "portfolio"
    }
  }
}
