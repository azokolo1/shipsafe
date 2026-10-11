data "aws_caller_identity" "current" {}

# Explicit key policy: delegates key access to IAM in this account only.
# Including the account root principal prevents the key becoming unmanageable.
data "aws_iam_policy_document" "tfstate_kms" {
  statement {
    sid       = "EnableIAMPermissionsForThisAccount"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
}

resource "aws_kms_key" "tfstate" {
  description             = "ShipSafe Terraform state encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.tfstate_kms.json
}

resource "aws_kms_alias" "tfstate" {
  name          = "alias/shipsafe-tfstate"
  target_key_id = aws_kms_key.tfstate.key_id
}

resource "aws_s3_bucket" "tfstate" {
  #checkov:skip=CKV_AWS_18:Portfolio mode - API activity covered by CloudTrail; prod reference enables access logs or S3 data events
  #checkov:skip=CKV_AWS_144:Portfolio mode - versioning provides recovery; prod reference replicates to eu-west-1 for DR
  #checkov:skip=CKV2_AWS_62:No consumer for state-object events; notifications would add no value
  bucket = "shipsafe-tfstate-${data.aws_caller_identity.current.account_id}-${var.region}"

  # Losing this bucket would orphan every environment's state
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_ownership_controls" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning lets us recover from a corrupted or bad state write
resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.tfstate.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Deny any request that is not over TLS
data "aws_iam_policy_document" "tfstate_tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.tfstate.arn,
      "${aws_s3_bucket.tfstate.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  policy = data.aws_iam_policy_document.tfstate_tls_only.json
}
