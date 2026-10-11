output "state_bucket" {
  description = "Name of the Terraform state bucket"
  value       = aws_s3_bucket.tfstate.bucket
}

output "state_kms_key_arn" {
  description = "ARN of the KMS key encrypting state"
  value       = aws_kms_key.tfstate.arn
}
