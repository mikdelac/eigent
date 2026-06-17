# Eigent EC2 (us-east-1) Terraform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create Terraform that provisions the lowest-tier practical EC2 in `us-east-1` and bootstraps a hosted, HTTPS-ready Eigent deployment at `ai.steamocloud.com`.

**Architecture:** Single EC2 instance runs the Eigent backend (`server/` via Docker Compose) and serves the built frontend through Nginx. Nginx reverse-proxies `/api` to the backend on `localhost:3001`. Let’s Encrypt certs are issued via HTTP-01 using the domain `ai.steamocloud.com`.

**Tech Stack:** Terraform, AWS EC2 + EIP, Security Groups, (optional) Route53 record, cloud-init user data, Docker + Compose, Node.js (>=18 <23), Nginx, Certbot (Let’s Encrypt).

---

### Task 1: Create Terraform skeleton (providers, versions, variables, outputs)

**Files:**
- Create: `infra/terraform/main.tf`
- Create: `infra/terraform/versions.tf`
- Create: `infra/terraform/variables.tf`
- Create: `infra/terraform/outputs.tf`
- Create: `infra/terraform/README.md`

**Step 1: Add provider + versions constraints**

- Use AWS provider.
- Pin Terraform required version to a modern stable baseline.

**Step 2: Add variables**

- `aws_region` default `us-east-1`
- `instance_type` default `t3.micro`
- `domain_name` default `ai.steamocloud.com`
- `ssh_key_name` (required)
- `ssh_ingress_cidr` (required; default can be `0.0.0.0/0` but plan should recommend restricting)
- `create_route53_record` (bool)
- `route53_zone_id` (nullable string; required if `create_route53_record=true`)

**Step 3: Add outputs**

- EC2 public IP (EIP)
- Instance ID
- Nginx URL (`https://${var.domain_name}`)

**Verification**

Run:
- `terraform -chdir=infra/terraform fmt -recursive`
- `terraform -chdir=infra/terraform validate`

Expected: both succeed.

---

### Task 2: EC2 resources (security group, IAM role, instance, EIP)

**Files:**
- Modify: `infra/terraform/main.tf`

**Step 1: Security group**

Inbound:
- 22/tcp from `var.ssh_ingress_cidr`
- 80/tcp from `0.0.0.0/0`
- 443/tcp from `0.0.0.0/0`

Outbound:
- all

**Step 2: IAM role + instance profile**

Minimum permissions for bootstrap logging/ops:
- SSM core (optional but recommended) OR none if SSH-only

Plan decision: include SSM managed policy so you can recover without opening SSH to the world.

**Step 3: EC2 instance**

- AMI: Amazon Linux 2023 (via SSM parameter lookup)
- Root volume: gp3, 30GB
- Attach security group
- Attach instance profile
- Provide `user_data` (Task 4)

**Step 4: Elastic IP**

- Allocate and associate to instance

**Verification**

Run:
- `terraform -chdir=infra/terraform plan`

Expected: shows instance + EIP + security group.

---

### Task 3: DNS (optional Route53 A record)

**Files:**
- Modify: `infra/terraform/main.tf`
- Modify: `infra/terraform/variables.tf`
- Modify: `infra/terraform/outputs.tf`

**Step 1: Conditional Route53 record**

If `var.create_route53_record=true`, create:
- Route53 `A` record `ai.steamocloud.com` → EIP

**Verification**

Run:
- `terraform -chdir=infra/terraform plan`

Expected: record created only when enabled.

---

### Task 4: Bootstrap script (cloud-init) to install and run Eigent + Nginx + TLS

**Files:**
- Create: `infra/terraform/user_data.sh.tftpl`

**Step 1: Install base packages**

- `git`
- `docker` + enable/start
- Docker compose plugin
- `nginx`
- `certbot` + nginx plugin (or standalone)

**Step 2: Install Node.js**

- Install Node 18/20/22 in a reproducible way on Amazon Linux 2023 (use NodeSource repo)

**Step 3: Deploy Eigent**

- Clone `https://github.com/eigent-ai/eigent.git` to `/opt/eigent`
- `cd /opt/eigent/server`
- `cp .env.example .env`
- `docker compose up --build -d`

**Step 4: Build frontend for hosted mode**

- `cd /opt/eigent`
- Create an env file for build pointing to local API:
  - `VITE_BASE_URL=/api`
  - `VITE_USE_LOCAL_PROXY=true`
  - `VITE_PROXY_URL=http://localhost:3001`
- `npm ci`
- `npm run build`

**Step 5: Configure Nginx**

- Serve `/opt/eigent/dist` (or the actual build output directory)
- Reverse-proxy `/api/` to `http://127.0.0.1:3001/`
- Include WebSocket headers if needed

**Step 6: Issue TLS cert**

- Ensure DNS resolves to EIP before cert attempt
- Obtain Let’s Encrypt cert for `${domain_name}`
- Set up renewal timer

**Robustness**

- Write logs to `/var/log/user-data.log`
- Use `set -euo pipefail`
- Add simple retries for package installs and cert issuance

**Verification**

After `terraform apply`, verify:
- `https://ai.steamocloud.com` returns the frontend
- `https://ai.steamocloud.com/api/docs` returns Swagger UI

---

### Task 5: Usage docs for your team

**Files:**
- Create: `infra/terraform/README.md`

Include:
- prerequisites (AWS credentials, Terraform, domain DNS)
- variables required
- `terraform init/plan/apply` commands
- how to SSH or SSM
- where to view logs:
  - `docker ps`
  - `docker logs eigent_api`
  - Nginx logs

