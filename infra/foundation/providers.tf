provider "aws" {
  region              = var.region
  allowed_account_ids = ["699281550756"]

  default_tags {
    tags = {
      Project   = "shipsafe"
      Stack     = "foundation"
      ManagedBy = "terraform"
      Owner     = var.owner
    }
  }
}
