# Partial configuration: bucket, key and KMS key come from backend.hcl (gitignored).
terraform {
  backend "s3" {}
}
