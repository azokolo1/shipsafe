output "state_bucket" {
  description = "Name of the Terraform state bucket"
  value       = aws_s3_bucket.tfstate.bucket
}

output "state_kms_key_arn" {
  description = "ARN of the KMS key encrypting state"
  value       = aws_kms_key.tfstate.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}

output "gha_plan_role_arn" {
  description = "Role GitHub Actions assumes for terraform plan"
  value       = aws_iam_role.gha_plan.arn
}
