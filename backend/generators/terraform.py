import logging
from typing import Any, Dict, List, Tuple

from generators.base import (
    BaseGenerator,
    ErrorCategory,
    GenerationContext,
    GenerationResult,
    IaCType,
    ValidationError,
)

logger = logging.getLogger(__name__)


class TerraformGenerator(BaseGenerator):
    iac_type = IaCType.TERRAFORM

    def _setup_validators(self) -> None:
        self.validators = [
            self._validate_hcl_syntax,
            self._validate_security,
        ]

    def generate(self, context: GenerationContext) -> GenerationResult:
        import time

        start_time = time.time()

        provider = self._detect_provider(context)
        config = self._parse_config(context, provider)

        files = {}
        files["main.tf"] = self._generate_main(config, provider, context)
        files["variables.tf"] = self._generate_variables(config, provider)
        files["outputs.tf"] = self._generate_outputs(config, provider)
        files["providers.tf"] = self._generate_providers(config, provider)
        files["terraform.tfvars.example"] = self._generate_tfvars_example(
            config, provider
        )

        code = "\n\n".join(
            [f"# {filename}\n{content}" for filename, content in files.items()]
        )

        result = GenerationResult.create(
            iac_type=self.iac_type,
            code=code,
            generation_time=time.time() - start_time,
        )
        result.files = files

        return result

    def validate_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        open_braces = code.count("{")
        close_braces = code.count("}")

        if open_braces != close_braces:
            errors.append(
                ValidationError(
                    category=ErrorCategory.SYNTAX_MISSING_BRACKET,
                    message=f"Unbalanced braces: {open_braces} {{ vs {close_braces} }}",
                )
            )

        if "terraform {" not in code and 'provider "' not in code:
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="Missing terraform or provider block",
                    severity="warning",
                )
            )

        return len([e for e in errors if e.severity == "error"]) == 0, errors

    def validate_semantics(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        sensitive_patterns = ["api_key =", "password =", "secret =", "token ="]
        for pattern in sensitive_patterns:
            if (
                pattern in code.lower()
                and "var."
                not in code[
                    code.lower().find(pattern) : code.lower().find(pattern) + 50
                ]
            ):
                errors.append(
                    ValidationError(
                        category=ErrorCategory.CONFIG_INVALID_VALUE,
                        message=f"Possible hardcoded credential: {pattern}",
                        suggestion="Use variables with sensitive = true",
                        severity="warning",
                    )
                )

        return True, errors

    def _validate_hcl_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            pass

        return True, errors

    def _validate_security(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "public_ip = true" in code.lower() or "public = true" in code.lower():
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_INVALID_VALUE,
                    message="Resource configured with public access",
                    severity="warning",
                    suggestion="Consider using private networking where possible",
                )
            )

        return True, errors

    def _detect_provider(self, context: GenerationContext) -> str:
        request = context.natural_language_request.lower()

        if context.cloud_provider:
            return context.cloud_provider.lower()

        if "arvan" in request:
            return "arvancloud"
        elif "aws" in request or "amazon" in request:
            return "aws"
        elif "gcp" in request or "google" in request:
            return "gcp"
        elif "azure" in request or "microsoft" in request:
            return "azure"

        return "arvancloud"

    def _parse_config(
        self, context: GenerationContext, provider: str
    ) -> Dict[str, Any]:
        config = {
            "region": context.region or "ir-thr-at1",
            "environment": context.environment,
            "resources": {
                "compute": [],
                "network": [],
                "storage": [],
                "database": [],
            },
        }

        request = context.natural_language_request.lower()

        if "vm" in request or "instance" in request or "server" in request:
            config["resources"]["compute"].append(
                {
                    "type": "instance",
                    "count": 1,
                    "flavor": "g1-1-1-0" if provider == "arvancloud" else "t3.micro",
                }
            )

        if "network" in request or "vpc" in request:
            config["resources"]["network"].append(
                {
                    "type": "network",
                    "cidr": "10.0.0.0/16",
                }
            )

        if "database" in request or "postgres" in request or "mysql" in request:
            config["resources"]["database"].append(
                {
                    "type": "postgres" if "postgres" in request else "mysql",
                }
            )

        if "storage" in request or "bucket" in request or "s3" in request:
            config["resources"]["storage"].append(
                {
                    "type": "bucket",
                }
            )

        return config

    def _generate_main(
        self, config: Dict[str, Any], provider: str, context: GenerationContext
    ) -> str:
        if provider == "arvancloud":
            return self._generate_arvancloud_main(config, context)
        elif provider == "aws":
            return self._generate_aws_main(config, context)
        else:
            return self._generate_generic_main(config, provider, context)

    def _generate_arvancloud_main(
        self, config: Dict[str, Any], context: GenerationContext
    ) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

# Network
resource "arvancloud_iaas_network" "main" {{
  name        = "${{var.project_name}}-network"
  region      = var.region
  description = "Main network for ${{var.project_name}}"
}}

# Subnet
resource "arvancloud_iaas_subnet" "main" {{
  name       = "${{var.project_name}}-subnet"
  region     = var.region
  network_id = arvancloud_iaas_network.main.id
  cidr       = var.subnet_cidr
  gateway_ip = cidrhost(var.subnet_cidr, 1)
  
  dns_servers = ["8.8.8.8", "8.8.4.4"]
  
  enable_dhcp = true
}}

# Security Group
resource "arvancloud_iaas_security_group" "main" {{
  name        = "${{var.project_name}}-sg"
  region      = var.region
  description = "Security group for ${{var.project_name}}"
}}

resource "arvancloud_iaas_security_group_rule" "ssh" {{
  region            = var.region
  security_group_id = arvancloud_iaas_security_group.main.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.allowed_ssh_cidr
}}

resource "arvancloud_iaas_security_group_rule" "http" {{
  region            = var.region
  security_group_id = arvancloud_iaas_security_group.main.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
}}

resource "arvancloud_iaas_security_group_rule" "https" {{
  region            = var.region
  security_group_id = arvancloud_iaas_security_group.main.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
}}

# SSH Key
resource "arvancloud_iaas_sshkey" "main" {{
  name       = "${{var.project_name}}-key"
  region     = var.region
  public_key = var.ssh_public_key
}}

# Compute Instance
resource "arvancloud_iaas_abrak" "main" {{
  count = var.instance_count

  name      = "${{var.project_name}}-${{count.index + 1}}"
  region    = var.region
  flavor_id = var.flavor_id
  image_id  = var.image_id
  
  network_id = arvancloud_iaas_network.main.id
  
  security_groups = [arvancloud_iaas_security_group.main.id]
  
  key_name = arvancloud_iaas_sshkey.main.name
  
  disk_size = var.disk_size
  
  tags = var.tags
}}

# Floating IP
resource "arvancloud_iaas_floatingip" "main" {{
  count = var.instance_count

  region      = var.region
  description = "Floating IP for ${{var.project_name}}-${{count.index + 1}}"
}}

resource "arvancloud_iaas_floatingip_attach" "main" {{
  count = var.instance_count

  region        = var.region
  floatingip_id = arvancloud_iaas_floatingip.main[count.index].id
  abrak_id      = arvancloud_iaas_abrak.main[count.index].id
}}
"""

    def _generate_aws_main(
        self, config: Dict[str, Any], context: GenerationContext
    ) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

# VPC
resource "aws_vpc" "main" {{
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {{
    Name = "${{var.project_name}}-vpc"
  }})
}}

# Internet Gateway
resource "aws_internet_gateway" "main" {{
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {{
    Name = "${{var.project_name}}-igw"
  }})
}}

# Subnet
resource "aws_subnet" "public" {{
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone = var.availability_zones[count.index]

  map_public_ip_on_launch = true

  tags = merge(var.tags, {{
    Name = "${{var.project_name}}-public-${{count.index + 1}}"
  }})
}}

# Route Table
resource "aws_route_table" "public" {{
  vpc_id = aws_vpc.main.id

  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }}

  tags = merge(var.tags, {{
    Name = "${{var.project_name}}-public-rt"
  }})
}}

resource "aws_route_table_association" "public" {{
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}}

# Security Group
resource "aws_security_group" "main" {{
  name_prefix = "${{var.project_name}}-"
  vpc_id      = aws_vpc.main.id

  ingress {{
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }}

  ingress {{
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  ingress {{
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  tags = merge(var.tags, {{
    Name = "${{var.project_name}}-sg"
  }})
}}

# EC2 Instance
resource "aws_instance" "main" {{
  count = var.instance_count

  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id     = aws_subnet.public[count.index % length(aws_subnet.public)].id

  vpc_security_group_ids = [aws_security_group.main.id]
  key_name               = var.key_name

  root_block_device {{
    volume_size = var.disk_size
    volume_type = "gp3"
  }}

  tags = merge(var.tags, {{
    Name = "${{var.project_name}}-${{count.index + 1}}"
  }})
}}
"""

    def _generate_generic_main(
        self, config: Dict[str, Any], provider: str, context: GenerationContext
    ) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}
# Provider: {provider}

# TODO: Add {provider}-specific resources here

locals {{
  project_name = var.project_name
  environment  = var.environment
  
  common_tags = {{
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Kube-Tofu"
  }}
}}
"""

    def _generate_variables(self, config: Dict[str, Any], provider: str) -> str:
        if provider == "arvancloud":
            return """# Variables for ArvanCloud

variable "arvan_api_key" {
  type        = string
  description = "ArvanCloud API Key"
  sensitive   = true
}

variable "region" {
  type        = string
  description = "ArvanCloud region"
  default     = "ir-thr-at1"
}

variable "project_name" {
  type        = string
  description = "Project name for resource naming"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, prod)"
  default     = "dev"
}

variable "subnet_cidr" {
  type        = string
  description = "CIDR block for subnet"
  default     = "10.0.1.0/24"
}

variable "instance_count" {
  type        = number
  description = "Number of instances to create"
  default     = 1
}

variable "flavor_id" {
  type        = string
  description = "Instance flavor ID"
  default     = "g1-1-1-0"
}

variable "image_id" {
  type        = string
  description = "OS image ID"
}

variable "disk_size" {
  type        = number
  description = "Root disk size in GB"
  default     = 25
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key for instance access"
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR allowed for SSH access"
  default     = "0.0.0.0/0"
}

variable "tags" {
  type        = list(string)
  description = "Tags to apply to resources"
  default     = []
}
"""
        else:
            return """# Variables

variable "project_name" {
  type        = string
  description = "Project name for resource naming"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, prod)"
  default     = "dev"
}

variable "region" {
  type        = string
  description = "Cloud provider region"
}

variable "instance_count" {
  type        = number
  description = "Number of instances"
  default     = 1
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
"""

    def _generate_outputs(self, config: Dict[str, Any], provider: str) -> str:
        if provider == "arvancloud":
            return """# Outputs

output "instance_ids" {
  description = "IDs of created instances"
  value       = arvancloud_iaas_abrak.main[*].id
}

output "instance_ips" {
  description = "Private IPs of instances"
  value       = arvancloud_iaas_abrak.main[*].addresses
}

output "floating_ips" {
  description = "Public floating IPs"
  value       = arvancloud_iaas_floatingip.main[*].floating_ip_address
}

output "network_id" {
  description = "Network ID"
  value       = arvancloud_iaas_network.main.id
}

output "security_group_id" {
  description = "Security group ID"
  value       = arvancloud_iaas_security_group.main.id
}
"""
        else:
            return """# Outputs

output "instance_ids" {
  description = "IDs of created instances"
  value       = []  # Add provider-specific outputs
}
"""

    def _generate_providers(self, config: Dict[str, Any], provider: str) -> str:
        if provider == "arvancloud":
            return """# Terraform configuration

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    arvancloud = {
      source  = "arvancloud/iaas"
      version = ">= 0.6.0"
    }
  }
}

provider "arvancloud" {
  api_key = var.arvan_api_key
  region  = var.region
}
"""
        elif provider == "aws":
            return """# Terraform configuration

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}
"""
        else:
            return f"""# Terraform configuration

terraform {{
  required_version = ">= 1.6.0"
}}

# Configure {provider} provider here
"""

    def _generate_tfvars_example(self, config: Dict[str, Any], provider: str) -> str:
        if provider == "arvancloud":
            return """# Example terraform.tfvars
# Copy to terraform.tfvars and fill in values

arvan_api_key    = ""  # Your ArvanCloud API key
region           = "ir-thr-at1"
project_name     = "my-project"
environment      = "dev"

instance_count   = 1
flavor_id        = "g1-1-1-0"  # 1 vCPU, 1GB RAM
image_id         = ""  # Ubuntu 22.04 image ID
disk_size        = 25

ssh_public_key   = "ssh-rsa AAAA..."
allowed_ssh_cidr = "YOUR_IP/32"

tags = ["project:my-project", "env:dev"]
"""
        else:
            return """# Example terraform.tfvars
# Copy to terraform.tfvars and fill in values

project_name = "my-project"
environment  = "dev"
region       = ""

instance_count = 1

tags = {
  Project     = "my-project"
  Environment = "dev"
}
"""
