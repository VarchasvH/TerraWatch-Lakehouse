variable aws_region {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "ap-south-1"
}

variable aws_account_id {
  description = "The AWS account ID"
  type        = string
}

variable project_name {
  description = "The project name"
  type        = string
}