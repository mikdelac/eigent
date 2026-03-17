output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.eigent.id
}

output "elastic_ip" {
  description = "Elastic IP address associated with the instance."
  value = coalesce(
    try(aws_eip.eigent[0].public_ip, null),
    try(data.aws_eip.existing[0].public_ip, null)
  )
}

output "url" {
  description = "Hosted URL for Eigent."
  value       = "https://${var.domain_name}"
}

