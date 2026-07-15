terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.11"
    }
  }

  backend "s3" {
    bucket         = "academic-paper-assistant-tfstate-718203020368"
    key            = "academic-paper-assistant/terraform.tfstate"
    region         = "ap-southeast-2"
    dynamodb_table = "academic-paper-assistant-tflock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
