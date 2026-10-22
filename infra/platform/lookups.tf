# Persistent resources owned by infra/foundation, looked up by name rather than
# read from its state file: the stacks stay decoupled, and a missing dependency
# fails the plan with a clear error instead of at apply time.

data "aws_caller_identity" "current" {}

data "aws_route53_zone" "shipsafe" {
  name         = var.domain_name
  private_zone = false
}

data "aws_acm_certificate" "shipsafe" {
  domain      = var.domain_name
  statuses    = ["ISSUED"]
  most_recent = true
}

data "aws_ecr_repository" "app" {
  name = var.ecr_repository_name
}

# Fails the plan if the tag was never pushed. Its digest is what ECS deploys, so a
# task can never run a different image than the one that was scanned and reviewed.
data "aws_ecr_image" "app" {
  repository_name = data.aws_ecr_repository.app.name
  image_tag       = var.image_tag
}
