output "bucket_names" {
  value = { for layer, b in aws_s3_bucket.this : layer => b.bucket }
}

output "bucket_arns" {
  value = { for layer, b in aws_s3_bucket.this : layer => b.arn }
}