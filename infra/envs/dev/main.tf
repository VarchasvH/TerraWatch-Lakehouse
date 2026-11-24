terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~>6.0"
    }
  }
}

variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "ap-south-1"
}

provider "aws" {
  region = var.aws_region
}


data "aws_caller_identity" "current" {}

output "caller_arn" {
  value = data.aws_caller_identity.current.arn
}

module "storage" {
  source         = "../../modules/storage"
  project_name   = "terrawatch"
  aws_account_id = data.aws_caller_identity.current.account_id
}