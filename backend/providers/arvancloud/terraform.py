from typing import Any, Dict, List


class ArvanCloudTerraformGenerator:
    PROVIDER_TEMPLATE = """terraform {
  required_version = ">= 1.0"
  
  required_providers {
    arvancloud = {
      source  = "arvancloud/iaas"
      version = ">= 0.6.0"
    }
  }
}

provider "arvancloud" {
  api_key = var.arvan_api_key
  region  = var.arvan_region
}
"""

    VARIABLES_TEMPLATE = """# ArvanCloud Variables
variable "arvan_api_key" {
  type        = string
  description = "ArvanCloud API Key"
  sensitive   = true
}

variable "arvan_region" {
  type        = string
  description = "ArvanCloud region"
  default     = "{region}"
}
"""

    def __init__(self):
        self.resource_generators = {
            "server": self._generate_server,
            "network": self._generate_network,
            "subnet": self._generate_subnet,
            "security_group": self._generate_security_group,
            "floating_ip": self._generate_floating_ip,
            "volume": self._generate_volume,
            "ssh_key": self._generate_ssh_key,
        }

    def generate(
        self,
        resources: List[Dict[str, Any]],
        region: str = "ir-thr-at1",
    ) -> str:
        sections = [
            self.PROVIDER_TEMPLATE,
            self.VARIABLES_TEMPLATE.format(region=region),
        ]

        grouped = {}
        for resource in resources:
            rtype = resource.get("type", "unknown")
            if rtype not in grouped:
                grouped[rtype] = []
            grouped[rtype].append(resource)

        order = [
            "ssh_key",
            "network",
            "subnet",
            "security_group",
            "volume",
            "server",
            "floating_ip",
        ]

        for rtype in order:
            if rtype in grouped:
                generator = self.resource_generators.get(rtype)
                if generator:
                    for i, resource in enumerate(grouped[rtype]):
                        sections.append(generator(resource, i))

        sections.append(self._generate_outputs(resources))
        return "\n".join(sections)

    def _generate_server(self, resource: Dict[str, Any], index: int) -> str:
        name = resource.get("name", f"server-{index}")
        safe_name = self._safe_name(name)
        flavor = resource.get("flavor_id", "g2-2-2-0")
        image = resource.get("image_id", "ubuntu-22.04")
        count = resource.get("count", 1)

        network_ref = resource.get("network_ref", "arvancloud_iaas_network.main.id")

        config = f'''
# Server: {name}
resource "arvancloud_iaas_abrak" "{safe_name}" {{
  {"count     = " + str(count) if count > 1 else ""}
  name      = "{name}{"${count.index + 1}" if count > 1 else ""}"
  region    = var.arvan_region
  flavor_id = "{flavor}"
  image_id  = "{image}"
  
  network_interface {{
    network_id = {network_ref}
  }}
'''

        if resource.get("ssh_key_ref"):
            config += f"""
  key_name = {resource.get("ssh_key_ref")}
"""

        if resource.get("security_group_refs"):
            sg_refs = resource.get("security_group_refs", [])
            config += f"""
  security_groups = [{", ".join(sg_refs)}]
"""

        tags = resource.get("tags", [])
        if tags:
            tags_str = ", ".join(f'"{t}"' for t in tags)
            config += f"""
  tags = [{tags_str}]
"""

        config += """
  lifecycle {
    create_before_destroy = true
  }
}
"""
        return config

    def _generate_network(self, resource: Dict[str, Any], index: int) -> str:
        name = resource.get("name", f"network-{index}")
        safe_name = self._safe_name(name)
        description = resource.get("description", "")

        return f'''
# Network: {name}
resource "arvancloud_iaas_network" "{safe_name}" {{
  name        = "{name}"
  region      = var.arvan_region
  description = "{description}"
}}
'''

    def _generate_subnet(self, resource: Dict[str, Any], index: int) -> str:
        name = resource.get("name", f"subnet-{index}")
        safe_name = self._safe_name(name)
        cidr = resource.get("cidr", "10.0.0.0/24")
        gateway = resource.get("gateway_ip", "10.0.0.1")
        enable_dhcp = resource.get("enable_dhcp", True)
        dns = resource.get("dns_nameservers", ["8.8.8.8", "8.8.4.4"])
        network_ref = resource.get("network_ref", "arvancloud_iaas_network.main.id")

        dns_str = ", ".join(f'"{d}"' for d in dns)

        return f'''
# Subnet: {name}
resource "arvancloud_iaas_subnet" "{safe_name}" {{
  name            = "{name}"
  network_id      = {network_ref}
  cidr            = "{cidr}"
  gateway_ip      = "{gateway}"
  enable_dhcp     = {str(enable_dhcp).lower()}
  dns_nameservers = [{dns_str}]
  
  depends_on = [arvancloud_iaas_network.{self._safe_name(resource.get("network_name", "main"))}]
}}
'''

    def _generate_security_group(self, resource: Dict[str, Any], index: int) -> str:
        name = resource.get("name", f"sg-{index}")
        safe_name = self._safe_name(name)
        description = resource.get("description", "")
        rules = resource.get("rules", [])

        config = f'''
# Security Group: {name}
resource "arvancloud_iaas_security_group" "{safe_name}" {{
  name        = "{name}"
  region      = var.arvan_region
  description = "{description}"
}}
'''

        for i, rule in enumerate(rules):
            direction = rule.get("direction", "ingress")
            protocol = rule.get("protocol", "tcp")
            port_min = rule.get("port_range_min", rule.get("port", 22))
            port_max = rule.get("port_range_max", port_min)
            remote_ip = rule.get("remote_ip_prefix", "0.0.0.0/0")

            config += f'''
resource "arvancloud_iaas_security_group_rule" "{safe_name}_rule_{i}" {{
  security_group_id = arvancloud_iaas_security_group.{safe_name}.id
  direction         = "{direction}"
  protocol          = "{protocol}"
  port_range_min    = {port_min}
  port_range_max    = {port_max}
  remote_ip_prefix  = "{remote_ip}"
}}
'''

        return config

    def _generate_floating_ip(self, resource: Dict[str, Any], index: int) -> str:
        name = resource.get("name", f"fip-{index}")
        safe_name = self._safe_name(name)
        description = resource.get("description", "")
        server_ref = resource.get("server_ref")

        config = f'''
# Floating IP: {name}
resource "arvancloud_iaas_floating_ip" "{safe_name}" {{
  region      = var.arvan_region
  description = "{description}"
}}
'''

        if server_ref:
            config += f'''
resource "arvancloud_iaas_floating_ip_attach" "{safe_name}_attach" {{
  floating_ip_id = arvancloud_iaas_floating_ip.{safe_name}.id
  server_id      = {server_ref}
}}
'''

        return config

    def _generate_volume(self, resource: Dict[str, Any], index: int) -> str:
        name = resource.get("name", f"volume-{index}")
        safe_name = self._safe_name(name)
        size = resource.get("size", 10)
        description = resource.get("description", "")
        server_ref = resource.get("server_ref")

        config = f'''
# Volume: {name}
resource "arvancloud_iaas_volume" "{safe_name}" {{
  name        = "{name}"
  region      = var.arvan_region
  size        = {size}
  description = "{description}"
}}
'''

        if server_ref:
            config += f'''
resource "arvancloud_iaas_volume_attachment" "{safe_name}_attach" {{
  volume_id = arvancloud_iaas_volume.{safe_name}.id
  server_id = {server_ref}
}}
'''

        return config

    def _generate_ssh_key(self, resource: Dict[str, Any], index: int) -> str:
        name = resource.get("name", f"sshkey-{index}")
        safe_name = self._safe_name(name)
        public_key = resource.get("public_key", "")

        key_ref = f'"{public_key}"' if public_key else "var.ssh_public_key"

        return f'''
# SSH Key: {name}
resource "arvancloud_iaas_sshkey" "{safe_name}" {{
  name       = "{name}"
  region     = var.arvan_region
  public_key = {key_ref}
}}
'''

    def _generate_outputs(self, resources: List[Dict[str, Any]]) -> str:
        outputs = ["", "# Outputs"]

        servers = [r for r in resources if r.get("type") == "server"]
        if servers:
            outputs.append("""
output "server_ids" {
  description = "IDs of created servers"
  value       = [for s in arvancloud_iaas_abrak : s.id]
}

output "server_ips" {
  description = "Private IPs of created servers"
  value       = [for s in arvancloud_iaas_abrak : s.addresses]
}
""")

        fips = [r for r in resources if r.get("type") == "floating_ip"]
        if fips:
            outputs.append("""
output "floating_ips" {
  description = "Floating IP addresses"
  value       = [for f in arvancloud_iaas_floating_ip : f.floating_ip_address]
}
""")

        return "\n".join(outputs)

    def _safe_name(self, name: str) -> str:
        safe = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        if safe and safe[0].isdigit():
            safe = "r_" + safe
        return safe or "resource"

    def generate_from_description(
        self,
        description: str,
        region: str = "ir-thr-at1",
    ) -> str:
        resources = []
        desc_lower = description.lower()

        resources.append(
            {
                "type": "network",
                "name": "main",
                "description": "Main network",
            }
        )

        resources.append(
            {
                "type": "subnet",
                "name": "main",
                "network_name": "main",
                "network_ref": "arvancloud_iaas_network.main.id",
                "cidr": "10.0.0.0/24",
            }
        )

        if any(w in desc_lower for w in ["web", "nginx", "apache", "http"]):
            resources.append(
                {
                    "type": "security_group",
                    "name": "web",
                    "description": "Web server security group",
                    "rules": [
                        {"direction": "ingress", "protocol": "tcp", "port": 22},
                        {"direction": "ingress", "protocol": "tcp", "port": 80},
                        {"direction": "ingress", "protocol": "tcp", "port": 443},
                    ],
                }
            )

            resources.append(
                {
                    "type": "server",
                    "name": "web",
                    "flavor_id": "g2-2-2-0",
                    "image_id": "ubuntu-22.04",
                    "network_ref": "arvancloud_iaas_network.main.id",
                    "security_group_refs": ["arvancloud_iaas_security_group.web.id"],
                    "tags": ["web", "nginx"],
                }
            )

            resources.append(
                {
                    "type": "floating_ip",
                    "name": "web",
                    "server_ref": "arvancloud_iaas_abrak.web.id",
                }
            )

        if any(w in desc_lower for w in ["database", "postgres", "mysql", "db"]):
            resources.append(
                {
                    "type": "security_group",
                    "name": "database",
                    "description": "Database security group",
                    "rules": [
                        {
                            "direction": "ingress",
                            "protocol": "tcp",
                            "port": 22,
                            "remote_ip_prefix": "10.0.0.0/24",
                        },
                        {
                            "direction": "ingress",
                            "protocol": "tcp",
                            "port": 5432,
                            "remote_ip_prefix": "10.0.0.0/24",
                        },
                    ],
                }
            )

            resources.append(
                {
                    "type": "server",
                    "name": "database",
                    "flavor_id": "g2-4-8-0",
                    "image_id": "ubuntu-22.04",
                    "network_ref": "arvancloud_iaas_network.main.id",
                    "security_group_refs": [
                        "arvancloud_iaas_security_group.database.id"
                    ],
                    "tags": ["database", "postgresql"],
                }
            )

            resources.append(
                {
                    "type": "volume",
                    "name": "db-data",
                    "size": 100,
                    "server_ref": "arvancloud_iaas_abrak.database.id",
                }
            )

        if any(w in desc_lower for w in ["kubernetes", "k8s", "cluster"]):
            resources.append(
                {
                    "type": "security_group",
                    "name": "k8s",
                    "description": "Kubernetes security group",
                    "rules": [
                        {"direction": "ingress", "protocol": "tcp", "port": 22},
                        {"direction": "ingress", "protocol": "tcp", "port": 6443},
                        {
                            "direction": "ingress",
                            "protocol": "tcp",
                            "port_range_min": 30000,
                            "port_range_max": 32767,
                        },
                    ],
                }
            )

            resources.append(
                {
                    "type": "server",
                    "name": "k8s-master",
                    "flavor_id": "g2-4-8-0",
                    "image_id": "ubuntu-22.04",
                    "network_ref": "arvancloud_iaas_network.main.id",
                    "security_group_refs": ["arvancloud_iaas_security_group.k8s.id"],
                    "tags": ["kubernetes", "master"],
                }
            )

            resources.append(
                {
                    "type": "server",
                    "name": "k8s-worker",
                    "count": 3,
                    "flavor_id": "g2-4-4-0",
                    "image_id": "ubuntu-22.04",
                    "network_ref": "arvancloud_iaas_network.main.id",
                    "security_group_refs": ["arvancloud_iaas_security_group.k8s.id"],
                    "tags": ["kubernetes", "worker"],
                }
            )

            resources.append(
                {
                    "type": "floating_ip",
                    "name": "k8s-api",
                    "server_ref": "arvancloud_iaas_abrak.k8s-master.id",
                }
            )

        return self.generate(resources, region)
