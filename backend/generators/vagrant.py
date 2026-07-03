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


VAGRANT_BOXES = {
    "ubuntu": "ubuntu/jammy64",
    "debian": "debian/bookworm64",
    "centos": "centos/stream9",
    "rocky": "rockylinux/9",
    "alpine": "generic/alpine318",
    "fedora": "fedora/39-cloud-base",
}


class VagrantGenerator(BaseGenerator):
    iac_type = IaCType.VAGRANT

    def _setup_validators(self) -> None:
        self.validators = [
            self._validate_ruby_syntax,
        ]

    def generate(self, context: GenerationContext) -> GenerationResult:
        import time

        start_time = time.time()
        config = self._parse_config(context)
        vagrantfile = self._generate_vagrantfile(config, context)

        result = GenerationResult.create(
            iac_type=self.iac_type,
            code=vagrantfile,
            generation_time=time.time() - start_time,
        )

        result.files = {
            "Vagrantfile": vagrantfile,
        }

        if config.get("provisioning", {}).get("shell"):
            result.files["provision.sh"] = self._generate_provision_script(config)

        return result

    def validate_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "Vagrant.configure" not in code:
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="Missing Vagrant.configure block",
                )
            )

        do_count = code.count(" do")
        end_count = code.count("end")

        if do_count != end_count:
            errors.append(
                ValidationError(
                    category=ErrorCategory.SYNTAX_MISSING_BRACKET,
                    message=f"Unbalanced do/end blocks: {do_count} do vs {end_count} end",
                )
            )

        return len(errors) == 0, errors

    def validate_semantics(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "config.vm.box" not in code:
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="No VM box defined",
                    suggestion="Add config.vm.box = 'ubuntu/jammy64'",
                )
            )

        return len(errors) == 0, errors

    def _validate_ruby_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if code.count('"') % 2 != 0:
            errors.append(
                ValidationError(
                    category=ErrorCategory.SYNTAX_MISSING_BRACKET,
                    message="Unbalanced double quotes",
                    severity="warning",
                )
            )

        if code.count("'") % 2 != 0:
            errors.append(
                ValidationError(
                    category=ErrorCategory.SYNTAX_MISSING_BRACKET,
                    message="Unbalanced single quotes",
                    severity="warning",
                )
            )

        return True, errors

    def _parse_config(self, context: GenerationContext) -> Dict[str, Any]:
        config = {
            "box": "ubuntu/jammy64",
            "hostname": "dev-vm",
            "memory": 2048,
            "cpus": 2,
            "machines": [],
            "network": {
                "private_ip": "192.168.56.10",
                "forwarded_ports": [],
            },
            "synced_folders": [
                {"host": ".", "guest": "/vagrant"},
            ],
            "provisioning": {
                "shell": True,
                "ansible": False,
                "docker": False,
            },
            "provider": "virtualbox",
        }

        request = context.natural_language_request.lower()

        for os_name, box in VAGRANT_BOXES.items():
            if os_name in request:
                config["box"] = box
                break

        if "cluster" in request or "multi" in request:
            config["machines"] = [
                {"name": "node1", "ip": "192.168.56.11"},
                {"name": "node2", "ip": "192.168.56.12"},
                {"name": "node3", "ip": "192.168.56.13"},
            ]

        if "docker" in request:
            config["provisioning"]["docker"] = True

        if "kubernetes" in request or "k8s" in request:
            config["provisioning"]["kubernetes"] = True
            config["memory"] = 4096
            config["cpus"] = 2

        if "high memory" in request or "large" in request:
            config["memory"] = 8192
            config["cpus"] = 4

        return config

    def _generate_vagrantfile(
        self, config: Dict[str, Any], context: GenerationContext
    ) -> str:
        if config["machines"]:
            return self._generate_multi_machine(config, context)
        else:
            return self._generate_single_machine(config, context)

    def _generate_single_machine(
        self, config: Dict[str, Any], context: GenerationContext
    ) -> str:
        return f'''# -*- mode: ruby -*-
# vi: set ft=ruby :

# Auto-generated by Kube-Tofu
# {context.natural_language_request}

Vagrant.configure("2") do |config|
  # Base box
  config.vm.box = "{config["box"]}"
  config.vm.hostname = "{config["hostname"]}"

  # Network configuration
  config.vm.network "private_network", ip: "{config["network"]["private_ip"]}"
  
  # Port forwarding
  config.vm.network "forwarded_port", guest: 80, host: 8080
  config.vm.network "forwarded_port", guest: 443, host: 8443
  config.vm.network "forwarded_port", guest: 8000, host: 8000

  # Shared folders
  config.vm.synced_folder ".", "/vagrant", type: "virtualbox"

  # Provider configuration
  config.vm.provider "{config["provider"]}" do |v|
    v.name = "{config["hostname"]}"
    v.memory = {config["memory"]}
    v.cpus = {config["cpus"]}
    
    # Enable nested virtualization (for Docker/K8s)
    v.customize ["modifyvm", :id, "--nested-hw-virt", "on"]
  end

  # Provisioning
  config.vm.provision "shell", inline: <<-SHELL
    set -e
    
    echo "=== Updating system ==="
    apt-get update
    apt-get upgrade -y
    
    echo "=== Installing common tools ==="
    apt-get install -y \\
      curl \\
      wget \\
      git \\
      vim \\
      htop \\
      jq \\
      tree
    
{self._generate_docker_provision() if config["provisioning"].get("docker") else ""}
{self._generate_kubernetes_provision() if config["provisioning"].get("kubernetes") else ""}
    
    echo "=== Provisioning complete ==="
  SHELL
  
  # Post-up message
  config.vm.post_up_message = <<-MESSAGE

  ╔═══════════════════════════════════════════════════════════════╗
  ║              Development Environment Ready!                    ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║                                                               ║
  ║  SSH:      vagrant ssh                                        ║
  ║  IP:       {config["network"]["private_ip"]}                                       ║
  ║                                                               ║
  ║  Ports:                                                       ║
  ║    HTTP:   http://localhost:8080                              ║
  ║    HTTPS:  https://localhost:8443                             ║
  ║    API:    http://localhost:8000                              ║
  ║                                                               ║
  ╚═══════════════════════════════════════════════════════════════╝

  MESSAGE
end
'''

    def _generate_multi_machine(
        self, config: Dict[str, Any], context: GenerationContext
    ) -> str:
        machines_config = ""
        for machine in config["machines"]:
            machines_config += f'''
  config.vm.define "{machine["name"]}" do |node|
    node.vm.hostname = "{machine["name"]}"
    node.vm.network "private_network", ip: "{machine["ip"]}"
    
    node.vm.provider "{config["provider"]}" do |v|
      v.name = "{machine["name"]}"
      v.memory = {config["memory"]}
      v.cpus = {config["cpus"]}
    end
  end
'''

        return f'''# -*- mode: ruby -*-
# vi: set ft=ruby :

# Auto-generated by Kube-Tofu
# {context.natural_language_request}

# Multi-machine cluster configuration

NODES = {len(config["machines"])}

Vagrant.configure("2") do |config|
  # Base box for all machines
  config.vm.box = "{config["box"]}"
  
  # Common provisioning
  config.vm.provision "shell", inline: <<-SHELL
    apt-get update
    apt-get install -y curl wget git vim htop
  SHELL
{machines_config}
  # Post-up message
  config.vm.post_up_message = <<-MESSAGE

  ╔═══════════════════════════════════════════════════════════════╗
  ║              Multi-Machine Cluster Ready!                      ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║                                                               ║
  ║  Machines:                                                    ║
{chr(10).join([f"  ║    {m['name']}: {m['ip']}" + " " * (48 - len(m["name"]) - len(m["ip"])) + "║" for m in config["machines"]])}
  ║                                                               ║
  ║  Commands:                                                    ║
  ║    vagrant ssh node1                                          ║
  ║    vagrant status                                             ║
  ║                                                               ║
  ╚═══════════════════════════════════════════════════════════════╝

  MESSAGE
end
'''

    def _generate_docker_provision(self) -> str:
        return """
    echo "=== Installing Docker ==="
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker vagrant
    
    # Install Docker Compose
    apt-get install -y docker-compose-plugin
"""

    def _generate_kubernetes_provision(self) -> str:
        return """
    echo "=== Installing Kubernetes tools ==="
    
    # Install kubectl
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
    
    # Install kind (Kubernetes in Docker)
    curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
    install -o root -g root -m 0755 kind /usr/local/bin/kind
    rm kind
    
    # Install Helm
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
"""

    def _generate_provision_script(self, config: Dict[str, Any]) -> str:
        return """#!/bin/bash
# Auto-generated by Kube-Tofu

set -e

echo "=== Starting provisioning ==="

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install common tools
sudo apt-get install -y \\
    curl \\
    wget \\
    git \\
    vim \\
    htop \\
    jq \\
    tree \\
    build-essential

echo "=== Provisioning complete ==="
"""
