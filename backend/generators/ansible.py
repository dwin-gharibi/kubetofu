import logging
from typing import Any, Dict, List, Tuple

import yaml

from generators.base import (
    BaseGenerator,
    ErrorCategory,
    GenerationContext,
    GenerationResult,
    IaCType,
    ValidationError,
)

logger = logging.getLogger(__name__)


class AnsibleGenerator(BaseGenerator):
    iac_type = IaCType.ANSIBLE

    def _setup_validators(self) -> None:
        self.validators = [
            self._validate_playbook_structure,
        ]

    def generate(self, context: GenerationContext) -> GenerationResult:
        import time

        start_time = time.time()

        config = self._parse_config(context)

        files = {}
        files["playbook.yml"] = self._generate_playbook(config, context)
        files["inventory/hosts.yml"] = self._generate_inventory(config)
        files["group_vars/all.yml"] = self._generate_group_vars(config)
        files["requirements.yml"] = self._generate_requirements(config)

        if config.get("roles"):
            for role in config["roles"]:
                role_name = role["name"]
                files[f"roles/{role_name}/tasks/main.yml"] = self._generate_role_tasks(
                    role
                )
                files[f"roles/{role_name}/handlers/main.yml"] = (
                    self._generate_role_handlers(role)
                )
                files[f"roles/{role_name}/defaults/main.yml"] = (
                    self._generate_role_defaults(role)
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

        try:
            for doc in yaml.safe_load_all(code):
                if doc is not None and not isinstance(doc, (dict, list)):
                    errors.append(
                        ValidationError(
                            category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                            message="Invalid YAML structure",
                        )
                    )
        except yaml.YAMLError as e:
            errors.append(
                ValidationError(
                    category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                    message=f"YAML syntax error: {e}",
                )
            )

        return len(errors) == 0, errors

    def validate_semantics(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "- hosts:" not in code and "- name:" not in code:
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="Playbook missing hosts or name definition",
                )
            )

        return len(errors) == 0, errors

    def _validate_playbook_structure(
        self, code: str
    ) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "become: true" in code or "become: yes" in code:
            if "become_user:" not in code:
                errors.append(
                    ValidationError(
                        category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                        message="Using become without become_user",
                        severity="info",
                        suggestion="Consider specifying become_user for clarity",
                    )
                )

        return True, errors

    def _parse_config(self, context: GenerationContext) -> Dict[str, Any]:
        config = {
            "hosts": "all",
            "become": True,
            "roles": [],
            "packages": [],
            "services": [],
        }

        request = context.natural_language_request.lower()

        if "docker" in request:
            config["roles"].append(
                {
                    "name": "docker",
                    "packages": ["docker.io", "docker-compose-plugin"],
                    "services": ["docker"],
                }
            )

        if "nginx" in request:
            config["roles"].append(
                {
                    "name": "nginx",
                    "packages": ["nginx"],
                    "services": ["nginx"],
                }
            )

        if "postgres" in request:
            config["roles"].append(
                {
                    "name": "postgresql",
                    "packages": ["postgresql", "postgresql-contrib"],
                    "services": ["postgresql"],
                }
            )

        if "redis" in request:
            config["roles"].append(
                {
                    "name": "redis",
                    "packages": ["redis-server"],
                    "services": ["redis-server"],
                }
            )

        if "python" in request:
            config["roles"].append(
                {
                    "name": "python",
                    "packages": ["python3", "python3-pip", "python3-venv"],
                    "services": [],
                }
            )

        if "node" in request or "nodejs" in request:
            config["roles"].append(
                {
                    "name": "nodejs",
                    "packages": ["nodejs", "npm"],
                    "services": [],
                }
            )

        if not config["roles"]:
            config["roles"].append(
                {
                    "name": "common",
                    "packages": ["curl", "wget", "git", "vim", "htop"],
                    "services": [],
                }
            )

        return config

    def _generate_playbook(
        self, config: Dict[str, Any], context: GenerationContext
    ) -> str:
        playbook = [
            {
                "name": f"Configure servers - {context.natural_language_request[:50]}",
                "hosts": config["hosts"],
                "become": config["become"],
                "gather_facts": True,
                "vars_files": ["group_vars/all.yml"],
                "pre_tasks": [
                    {
                        "name": "Update apt cache",
                        "apt": {
                            "update_cache": True,
                            "cache_valid_time": 3600,
                        },
                        "when": "ansible_os_family == 'Debian'",
                    }
                ],
                "roles": [role["name"] for role in config["roles"]],
                "post_tasks": [
                    {
                        "name": "Verify services are running",
                        "service_facts": None,
                    },
                    {
                        "name": "Display completion message",
                        "debug": {
                            "msg": "Configuration complete!",
                        },
                    },
                ],
            }
        ]

        header = f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}
#
# Run with: ansible-playbook -i inventory/hosts.yml playbook.yml
---
"""
        return header + yaml.dump(playbook, default_flow_style=False, sort_keys=False)

    def _generate_inventory(self, config: Dict[str, Any]) -> str:
        inventory = {
            "all": {
                "hosts": {
                    "server1": {
                        "ansible_host": "192.168.1.10",
                    },
                },
                "children": {
                    "webservers": {
                        "hosts": {
                            "server1": None,
                        },
                    },
                    "dbservers": {
                        "hosts": {},
                    },
                },
                "vars": {
                    "ansible_user": "ubuntu",
                    "ansible_python_interpreter": "/usr/bin/python3",
                },
            },
        }

        header = """# Inventory file
# Update with your actual hosts
---
"""
        return header + yaml.dump(inventory, default_flow_style=False, sort_keys=False)

    def _generate_group_vars(self, config: Dict[str, Any]) -> str:
        variables = {
            "# Common variables": None,
            "app_name": "myapp",
            "app_env": "production",
            "": None,
            "# System configuration": None,
            "timezone": "UTC",
            "locale": "en_US.UTF-8",
            " ": None,
            "# Security": None,
            "ssh_port": 22,
            "firewall_enabled": True,
            "  ": None,
            "# Application settings": None,
            "app_port": 8080,
            "app_workers": 4,
        }

        header = """# Group variables for all hosts
---
"""
        lines = [header]
        for key, value in variables.items():
            if key.startswith("#"):
                lines.append(f"\n{key}")
            elif value is None:
                continue
            else:
                lines.append(f"{key}: {value}")

        return "\n".join(lines)

    def _generate_requirements(self, config: Dict[str, Any]) -> str:
        requirements = {
            "roles": [
                {"name": "geerlingguy.docker", "version": "6.1.0"},
                {"name": "geerlingguy.pip"},
            ],
            "collections": [
                {"name": "community.general"},
                {"name": "ansible.posix"},
            ],
        }

        header = """# Ansible Galaxy requirements
# Install with: ansible-galaxy install -r requirements.yml
---
"""
        return header + yaml.dump(
            requirements, default_flow_style=False, sort_keys=False
        )

    def _generate_role_tasks(self, role: Dict[str, Any]) -> str:
        tasks = []

        if role.get("packages"):
            tasks.append(
                {
                    "name": f"Install {role['name']} packages",
                    "apt": {
                        "name": role["packages"],
                        "state": "present",
                    },
                    "when": "ansible_os_family == 'Debian'",
                }
            )

        for service in role.get("services", []):
            tasks.append(
                {
                    "name": f"Ensure {service} is running",
                    "service": {
                        "name": service,
                        "state": "started",
                        "enabled": True,
                    },
                }
            )

        header = f"""# Tasks for {role["name"]} role
---
"""
        return header + yaml.dump(tasks, default_flow_style=False, sort_keys=False)

    def _generate_role_handlers(self, role: Dict[str, Any]) -> str:
        handlers = []

        for service in role.get("services", []):
            handlers.append(
                {
                    "name": f"Restart {service}",
                    "service": {
                        "name": service,
                        "state": "restarted",
                    },
                }
            )
            handlers.append(
                {
                    "name": f"Reload {service}",
                    "service": {
                        "name": service,
                        "state": "reloaded",
                    },
                }
            )

        header = f"""# Handlers for {role["name"]} role
---
"""
        return (
            header + yaml.dump(handlers, default_flow_style=False, sort_keys=False)
            if handlers
            else header + "[]"
        )

    def _generate_role_defaults(self, role: Dict[str, Any]) -> str:
        defaults = {
            f"{role['name']}_enabled": True,
        }

        header = f"""# Default variables for {role["name"]} role
---
"""
        return header + yaml.dump(defaults, default_flow_style=False, sort_keys=False)
