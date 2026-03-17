# Eigent on EC2 (Terraform)

This folder provisions a single EC2 instance in **us-east-1** and bootstraps Eigent so it is reachable at `https://ai.steamocloud.com`.

## Prerequisites

- Terraform >= 1.5
- AWS credentials configured (env vars, shared credentials file, or SSO)
- An existing EC2 Key Pair name (for `ssh_key_name`)
- DNS for `ai.steamocloud.com` must point to the instance’s Elastic IP before Let’s Encrypt issuance succeeds

## Usage

Default EC2 key pair is `key-07c284642ddefed9e`. Override with `-var 'ssh_key_name=OTHER_KEY'` if needed.

```bash
cd terraform
terraform init
terraform plan -var 'ssh_ingress_cidr=YOUR_PUBLIC_IP/32'
terraform apply -var 'ssh_ingress_cidr=YOUR_PUBLIC_IP/32'
```

To override the key pair:

```bash
terraform apply -var 'ssh_key_name=key-07c284642ddefed9e' -var 'ssh_ingress_cidr=YOUR_PUBLIC_IP/32'
```

## Route53 (optional)

If you want Terraform to manage the Route53 A record:

- Set `create_route53_record=true`
- Set `route53_zone_id=Z123...`

## Using an existing Elastic IP (optional)

By default, this Terraform uses the existing Elastic IP in `existing_eip_public_ip` (defaults to `100.24.222.53`).

To force Terraform to allocate a new Elastic IP instead, set:

- `allocate_new_eip=true`

If you want to explicitly select an existing Elastic IP by allocation id (overrides `existing_eip_public_ip`), set:

- `eip_allocation_id=eipalloc-...`

## Verification

After apply:

- `https://ai.steamocloud.com/` should load the frontend
- `https://ai.steamocloud.com/api/docs` should load Swagger UI (backend)

