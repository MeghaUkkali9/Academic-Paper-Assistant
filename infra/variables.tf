variable "aws_region" {
  description = "AWS region for the deployment"
  type        = string
  default     = "ap-southeast-2"
}

variable "instance_type" {
  description = "EC2 instance type running the docker-compose stack"
  type        = string
  default     = "t3.large"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GB"
  type        = number
  default     = 40
}

variable "my_ip_cidr" {
  description = "CIDR allowed to reach SSH and the admin-only ports (OpenSearch, Dashboards, Airflow)"
  type        = string
  default     = "157.50.173.197/32"
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.20.1.0/24"
}
