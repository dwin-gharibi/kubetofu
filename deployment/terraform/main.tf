# Kube-Tofu Infrastructure Deployment
# Deploy Kube-Tofu platform on ArvanCloud

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    arvancloud = {
      source  = "arvancloud/iaas"
      version = ">= 0.6.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "arvancloud" {
  api_key = var.arvan_api_key
  region  = var.arvan_region
}

variable "arvan_api_key" {
  type        = string
  description = "ArvanCloud API Key"
  sensitive   = true
}

variable "arvan_region" {
  type        = string
  description = "ArvanCloud region"
  default     = "ir-thr-at1"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, prod)"
  default     = "dev"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key for server access"
}

locals {
  project_name = "kubetofu"
  common_tags  = ["kubetofu", var.environment]
}

resource "arvancloud_iaas_network" "main" {
  name        = "${local.project_name}-network"
  region      = var.arvan_region
  description = "Kube-Tofu main network"
}

resource "arvancloud_iaas_subnet" "main" {
  name            = "${local.project_name}-subnet"
  network_id      = arvancloud_iaas_network.main.id
  cidr            = "10.0.0.0/24"
  gateway_ip      = "10.0.0.1"
  enable_dhcp     = true
  dns_nameservers = ["8.8.8.8", "8.8.4.4"]
}

resource "arvancloud_iaas_security_group" "web" {
  name        = "${local.project_name}-web-sg"
  region      = var.arvan_region
  description = "Web traffic security group"
}

resource "arvancloud_iaas_security_group_rule" "web_http" {
  security_group_id = arvancloud_iaas_security_group.web.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
}

resource "arvancloud_iaas_security_group_rule" "web_https" {
  security_group_id = arvancloud_iaas_security_group.web.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
}

resource "arvancloud_iaas_security_group" "app" {
  name        = "${local.project_name}-app-sg"
  region      = var.arvan_region
  description = "Application security group"
}

resource "arvancloud_iaas_security_group_rule" "app_ssh" {
  security_group_id = arvancloud_iaas_security_group.app.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
}

resource "arvancloud_iaas_security_group" "db" {
  name        = "${local.project_name}-db-sg"
  region      = var.arvan_region
  description = "Database security group"
}

resource "arvancloud_iaas_security_group_rule" "db_postgres" {
  security_group_id = arvancloud_iaas_security_group.db.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 5432
  port_range_max    = 5432
  remote_ip_prefix  = "10.0.0.0/24"
}

resource "arvancloud_iaas_sshkey" "main" {
  name       = "${local.project_name}-key"
  region     = var.arvan_region
  public_key = var.ssh_public_key
}

resource "arvancloud_iaas_abrak" "app" {
  name      = "${local.project_name}-app"
  region    = var.arvan_region
  flavor_id = var.environment == "prod" ? "g2-4-8-0" : "g2-2-4-0"
  image_id  = "ubuntu-22.04"
  key_name  = arvancloud_iaas_sshkey.main.name

  network_interface {
    network_id = arvancloud_iaas_network.main.id
  }

  security_groups = [
    arvancloud_iaas_security_group.web.id,
    arvancloud_iaas_security_group.app.id,
  ]

  tags = concat(local.common_tags, ["app", "docker"])

  lifecycle {
    create_before_destroy = true
  }
}

resource "arvancloud_iaas_abrak" "db" {
  name      = "${local.project_name}-db"
  region    = var.arvan_region
  flavor_id = var.environment == "prod" ? "g2-4-8-0" : "g2-2-4-0"
  image_id  = "ubuntu-22.04"
  key_name  = arvancloud_iaas_sshkey.main.name

  network_interface {
    network_id = arvancloud_iaas_network.main.id
  }

  security_groups = [
    arvancloud_iaas_security_group.db.id,
    arvancloud_iaas_security_group.app.id,
  ]

  tags = concat(local.common_tags, ["database", "postgresql"])
}

resource "arvancloud_iaas_volume" "db_data" {
  name        = "${local.project_name}-db-data"
  region      = var.arvan_region
  size        = var.environment == "prod" ? 100 : 20
  description = "PostgreSQL data volume"
}

resource "arvancloud_iaas_volume_attachment" "db_data" {
  volume_id = arvancloud_iaas_volume.db_data.id
  server_id = arvancloud_iaas_abrak.db.id
}

resource "arvancloud_iaas_floating_ip" "app" {
  region      = var.arvan_region
  description = "Kube-Tofu application public IP"
}

resource "arvancloud_iaas_floating_ip_attach" "app" {
  floating_ip_id = arvancloud_iaas_floating_ip.app.id
  server_id      = arvancloud_iaas_abrak.app.id
}

output "app_public_ip" {
  description = "Application server public IP"
  value       = arvancloud_iaas_floating_ip.app.floating_ip_address
}

output "app_private_ip" {
  description = "Application server private IP"
  value       = arvancloud_iaas_abrak.app.addresses
}

output "db_private_ip" {
  description = "Database server private IP"
  value       = arvancloud_iaas_abrak.db.addresses
}

output "connection_info" {
  description = "Connection information"
  value = {
    ssh_command = "ssh -i ~/.ssh/id_rsa ubuntu@${arvancloud_iaas_floating_ip.app.floating_ip_address}"
    web_url     = "http://${arvancloud_iaas_floating_ip.app.floating_ip_address}"
  }
}
