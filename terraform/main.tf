provider "aws" {
  region = var.aws_region
}

data "aws_ami" "ubuntu_2204" {
  most_recent = true

  owners = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  uses_allocation_id_override = var.eip_allocation_id != null && var.eip_allocation_id != ""
  uses_existing_eip           = !var.allocate_new_eip
}

resource "aws_security_group" "eigent" {
  name        = "eigent-sg"
  description = "Eigent EC2 security group"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_ingress_cidr]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eigent" {
  name               = "eigent-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.eigent.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "eigent" {
  name = "eigent-ec2-instance-profile"
  role = aws_iam_role.eigent.name
}

resource "aws_instance" "eigent" {
  ami                    = data.aws_ami.ubuntu_2204.id
  instance_type          = var.instance_type
  key_name               = var.ssh_key_name
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.eigent.id]
  iam_instance_profile   = aws_iam_instance_profile.eigent.name

  root_block_device {
    volume_type = "gp3"
    volume_size = 30
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    domain_name = var.domain_name
    repo_url    = var.repo_url
  })

  tags = {
    Name = "eigent"
  }
}

resource "aws_eip" "eigent" {
  count  = local.uses_existing_eip ? 0 : 1
  domain = "vpc"
  tags = {
    Name = "eigent-eip"
  }
}

data "aws_eip" "existing" {
  count = local.uses_existing_eip ? 1 : 0

  id        = local.uses_allocation_id_override ? var.eip_allocation_id : null
  public_ip = local.uses_allocation_id_override ? null : var.existing_eip_public_ip
}

resource "aws_eip_association" "eigent" {
  instance_id   = aws_instance.eigent.id
  allocation_id = local.uses_existing_eip ? data.aws_eip.existing[0].id : aws_eip.eigent[0].id
}

resource "aws_route53_record" "eigent" {
  count   = var.create_route53_record ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 60
  records = [
    coalesce(
      try(aws_eip.eigent[0].public_ip, null),
      try(data.aws_eip.existing[0].public_ip, null)
    )
  ]
}

