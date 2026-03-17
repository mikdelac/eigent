variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.large"
}

variable "subnet_id" {
  description = "Subnet ID to launch the instance into."
  type        = string
  default     = "subnet-04e29b72b27dab7a9"
}

variable "domain_name" {
  description = "Public FQDN for Eigent (used for TLS cert issuance)."
  type        = string
  default     = "ai1.steamocloud.com"
}

variable "ssh_key_name" {
  description = "Name of an existing EC2 key pair to enable SSH."
  type        = string
  default     = "key_database"
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed to SSH into the instance. Strongly recommended to restrict to your public IP."
  type        = string
  default     = "0.0.0.0/0"
}

variable "create_route53_record" {
  description = "Whether to create a Route53 A record for domain_name pointing to the instance EIP."
  type        = bool
  default     = false
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID. Required when create_route53_record=true."
  type        = string
  default     = null
}

variable "existing_eip_public_ip" {
  description = "Existing Elastic IP public IPv4 to associate to the instance by default."
  type        = string
  default     = "100.24.222.53"
}

variable "allocate_new_eip" {
  description = "If true, Terraform will allocate a new Elastic IP instead of using existing_eip_public_ip."
  type        = bool
  default     = false
}

variable "eip_allocation_id" {
  description = "Optional explicit EIP allocation ID override. If set, it takes precedence over existing_eip_public_ip."
  type        = string
  default     = null
}

variable "repo_url" {
  description = "Eigent git repository URL to clone on the instance."
  type        = string
  default     = "https://github.com/eigent-ai/eigent.git"
}

