import logging
import re
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

SERVICE_TEMPLATES = {
    "postgres": {
        "image": "postgres:16-alpine",
        "environment": {
            "POSTGRES_DB": "${DB_NAME:-app}",
            "POSTGRES_USER": "${DB_USER:-app}",
            "POSTGRES_PASSWORD": "${DB_PASSWORD}",
        },
        "volumes": ["postgres_data:/var/lib/postgresql/data"],
        "healthcheck": {
            "test": ["CMD-SHELL", "pg_isready -U ${DB_USER:-app}"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "redis": {
        "image": "redis:7-alpine",
        "command": "redis-server --appendonly yes",
        "volumes": ["redis_data:/data"],
        "healthcheck": {
            "test": ["CMD", "redis-cli", "ping"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "mongodb": {
        "image": "mongo:7",
        "environment": {
            "MONGO_INITDB_ROOT_USERNAME": "${MONGO_USER:-admin}",
            "MONGO_INITDB_ROOT_PASSWORD": "${MONGO_PASSWORD}",
        },
        "volumes": ["mongo_data:/data/db"],
        "healthcheck": {
            "test": ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "mysql": {
        "image": "mysql:8",
        "environment": {
            "MYSQL_DATABASE": "${DB_NAME:-app}",
            "MYSQL_USER": "${DB_USER:-app}",
            "MYSQL_PASSWORD": "${DB_PASSWORD}",
            "MYSQL_ROOT_PASSWORD": "${DB_ROOT_PASSWORD}",
        },
        "volumes": ["mysql_data:/var/lib/mysql"],
        "healthcheck": {
            "test": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
    },
    "rabbitmq": {
        "image": "rabbitmq:3-management-alpine",
        "environment": {
            "RABBITMQ_DEFAULT_USER": "${RABBITMQ_USER:-guest}",
            "RABBITMQ_DEFAULT_PASS": "${RABBITMQ_PASSWORD:-guest}",
        },
        "ports": ["5672:5672", "15672:15672"],
        "volumes": ["rabbitmq_data:/var/lib/rabbitmq"],
        "healthcheck": {
            "test": ["CMD", "rabbitmq-diagnostics", "-q", "ping"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 5,
        },
    },
    "kafka": {
        "image": "confluentinc/cp-kafka:7.5.0",
        "environment": {
            "KAFKA_BROKER_ID": "1",
            "KAFKA_ZOOKEEPER_CONNECT": "zookeeper:2181",
            "KAFKA_ADVERTISED_LISTENERS": "PLAINTEXT://kafka:9092",
            "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
        },
        "depends_on": ["zookeeper"],
    },
    "zookeeper": {
        "image": "confluentinc/cp-zookeeper:7.5.0",
        "environment": {
            "ZOOKEEPER_CLIENT_PORT": "2181",
            "ZOOKEEPER_TICK_TIME": "2000",
        },
        "volumes": ["zookeeper_data:/var/lib/zookeeper/data"],
    },
    "elasticsearch": {
        "image": "docker.elastic.co/elasticsearch/elasticsearch:8.11.0",
        "environment": {
            "discovery.type": "single-node",
            "ES_JAVA_OPTS": "-Xms512m -Xmx512m",
            "xpack.security.enabled": "false",
        },
        "volumes": ["elasticsearch_data:/usr/share/elasticsearch/data"],
        "healthcheck": {
            "test": [
                "CMD-SHELL",
                "curl -f http://localhost:9200/_cluster/health || exit 1",
            ],
            "interval": "30s",
            "timeout": "10s",
            "retries": 5,
        },
    },
    "nginx": {
        "image": "nginx:alpine",
        "ports": ["80:80", "443:443"],
        "volumes": [
            "./nginx.conf:/etc/nginx/nginx.conf:ro",
            "./ssl:/etc/nginx/ssl:ro",
        ],
    },
    "traefik": {
        "image": "traefik:v3.0",
        "command": [
            "--api.insecure=true",
            "--providers.docker=true",
            "--entrypoints.web.address=:80",
            "--entrypoints.websecure.address=:443",
        ],
        "ports": ["80:80", "443:443", "8080:8080"],
        "volumes": [
            "/var/run/docker.sock:/var/run/docker.sock:ro",
        ],
    },
}


class DockerComposeGenerator(BaseGenerator):
    iac_type = IaCType.DOCKER_COMPOSE

    def _setup_validators(self) -> None:
        self.validators = [
            self._validate_dependencies,
            self._validate_networks,
        ]

    def generate(self, context: GenerationContext) -> GenerationResult:
        import time

        start_time = time.time()
        services = self._parse_services(context)
        compose = self._build_compose_structure(services, context)

        compose_yaml = yaml.dump(
            compose,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

        header = f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}
# 
# Usage:
#   docker compose up -d
#   docker compose logs -f
#   docker compose down

"""
        compose_yaml = header + compose_yaml

        result = GenerationResult.create(
            iac_type=self.iac_type,
            code=compose_yaml,
            generation_time=time.time() - start_time,
        )

        result.files = {
            "docker-compose.yml": compose_yaml,
            ".env.example": self._generate_env_example(compose),
        }

        return result

    def validate_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        try:
            compose = yaml.safe_load(code)

            if not isinstance(compose, dict):
                errors.append(
                    ValidationError(
                        category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                        message="Docker Compose must be a YAML mapping",
                    )
                )
                return False, errors

        except yaml.YAMLError as e:
            errors.append(
                ValidationError(
                    category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                    message=f"Invalid YAML syntax: {e}",
                    line=getattr(e, "problem_mark", None) and e.problem_mark.line,
                )
            )
            return False, errors

        return True, errors

    def validate_semantics(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        try:
            compose = yaml.safe_load(code)
        except yaml.YAMLError:
            return False, [
                ValidationError(
                    category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                    message="Cannot parse YAML for semantic validation",
                )
            ]

        version = compose.get("version")
        if version and version < "3":
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_DEPRECATED,
                    message=f"Compose version {version} is deprecated",
                    suggestion="Use version '3.8' or remove version field (Compose V2)",
                )
            )

        services = compose.get("services", {})
        if not services:
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="No services defined in docker-compose",
                )
            )
            return False, errors

        for name, service in services.items():
            if not isinstance(service, dict):
                errors.append(
                    ValidationError(
                        category=ErrorCategory.SEMANTIC_TYPE_MISMATCH,
                        message=f"Service '{name}' must be a mapping",
                    )
                )
                continue

            if "image" not in service and "build" not in service:
                errors.append(
                    ValidationError(
                        category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                        message=f"Service '{name}' must have either 'image' or 'build'",
                    )
                )

            depends_on = service.get("depends_on", [])
            if isinstance(depends_on, list):
                for dep in depends_on:
                    if dep not in services:
                        errors.append(
                            ValidationError(
                                category=ErrorCategory.SEMANTIC_UNDEFINED_REFERENCE,
                                message=f"Service '{name}' depends on undefined service '{dep}'",
                            )
                        )
            elif isinstance(depends_on, dict):
                for dep in depends_on.keys():
                    if dep not in services:
                        errors.append(
                            ValidationError(
                                category=ErrorCategory.SEMANTIC_UNDEFINED_REFERENCE,
                                message=f"Service '{name}' depends on undefined service '{dep}'",
                            )
                        )

        defined_volumes = set(compose.get("volumes", {}).keys())
        for name, service in services.items():
            for volume in service.get("volumes", []):
                if isinstance(volume, str) and ":" in volume:
                    vol_name = volume.split(":")[0]
                    if not vol_name.startswith("./") and not vol_name.startswith("/"):
                        if vol_name not in defined_volumes:
                            errors.append(
                                ValidationError(
                                    category=ErrorCategory.SEMANTIC_UNDEFINED_REFERENCE,
                                    message=f"Volume '{vol_name}' used in '{name}' but not defined",
                                    suggestion=f"Add '{vol_name}:' to the 'volumes' section",
                                )
                            )

        defined_networks = set(compose.get("networks", {}).keys())
        defined_networks.add("default")

        for name, service in services.items():
            for network in service.get("networks", []):
                if isinstance(network, str) and network not in defined_networks:
                    errors.append(
                        ValidationError(
                            category=ErrorCategory.SEMANTIC_UNDEFINED_REFERENCE,
                            message=f"Network '{network}' used in '{name}' but not defined",
                        )
                    )

        return len([e for e in errors if e.severity == "error"]) == 0, errors

    def _validate_dependencies(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        try:
            compose = yaml.safe_load(code)
            services = compose.get("services", {})

            graph = {}
            for name, service in services.items():
                deps = service.get("depends_on", [])
                if isinstance(deps, dict):
                    deps = list(deps.keys())
                graph[name] = deps

            def has_cycle(node, visited, rec_stack):
                visited.add(node)
                rec_stack.add(node)

                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        if has_cycle(neighbor, visited, rec_stack):
                            return True
                    elif neighbor in rec_stack:
                        return True

                rec_stack.remove(node)
                return False

            visited = set()
            for node in graph:
                if node not in visited:
                    if has_cycle(node, visited, set()):
                        errors.append(
                            ValidationError(
                                category=ErrorCategory.SEMANTIC_CIRCULAR_DEPENDENCY,
                                message="Circular dependency detected in services",
                                severity="error",
                            )
                        )
                        break

        except Exception as e:
            logger.warning(f"Dependency validation failed: {e}")

        return len(errors) == 0, errors

    def _validate_networks(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        try:
            compose = yaml.safe_load(code)
            networks = compose.get("networks", {})

            for name, config in networks.items():
                if config and isinstance(config, dict):
                    if config.get("external"):
                        errors.append(
                            ValidationError(
                                category=ErrorCategory.CONFIG_INVALID_VALUE,
                                message=f"Network '{name}' is external - ensure it exists",
                                severity="warning",
                            )
                        )

        except Exception as e:
            logger.warning(f"Network validation failed: {e}")

        return True, errors

    def _parse_services(self, context: GenerationContext) -> List[Dict[str, Any]]:
        services = []

        for service in context.services:
            service_lower = service.lower()

            for template_name, template in SERVICE_TEMPLATES.items():
                if template_name in service_lower:
                    services.append(
                        {
                            "name": template_name,
                            "template": template_name,
                            "config": template.copy(),
                        }
                    )
                    break
            else:
                services.append(
                    {
                        "name": service_lower.replace(" ", "_"),
                        "template": None,
                        "config": {},
                    }
                )

        request = context.natural_language_request.lower()

        if "postgres" in request and not any(s["name"] == "postgres" for s in services):
            services.append(
                {
                    "name": "postgres",
                    "template": "postgres",
                    "config": SERVICE_TEMPLATES["postgres"].copy(),
                }
            )

        if "redis" in request and not any(s["name"] == "redis" for s in services):
            services.append(
                {
                    "name": "redis",
                    "template": "redis",
                    "config": SERVICE_TEMPLATES["redis"].copy(),
                }
            )

        if "mongo" in request and not any(s["name"] == "mongodb" for s in services):
            services.append(
                {
                    "name": "mongodb",
                    "template": "mongodb",
                    "config": SERVICE_TEMPLATES["mongodb"].copy(),
                }
            )

        if "rabbit" in request and not any(s["name"] == "rabbitmq" for s in services):
            services.append(
                {
                    "name": "rabbitmq",
                    "template": "rabbitmq",
                    "config": SERVICE_TEMPLATES["rabbitmq"].copy(),
                }
            )

        if "kafka" in request and not any(s["name"] == "kafka" for s in services):
            services.append(
                {
                    "name": "zookeeper",
                    "template": "zookeeper",
                    "config": SERVICE_TEMPLATES["zookeeper"].copy(),
                }
            )
            services.append(
                {
                    "name": "kafka",
                    "template": "kafka",
                    "config": SERVICE_TEMPLATES["kafka"].copy(),
                }
            )

        return services

    def _build_compose_structure(
        self, services: List[Dict[str, Any]], context: GenerationContext
    ) -> Dict[str, Any]:
        compose = {
            "services": {},
            "volumes": {},
            "networks": {
                "default": {
                    "name": f"{context.environment}-network",
                },
            },
        }

        has_app = any(
            s["name"] in ("app", "api", "backend", "frontend") for s in services
        )
        if not has_app:
            compose["services"]["app"] = {
                "build": {
                    "context": ".",
                    "dockerfile": "Dockerfile",
                },
                "ports": ["8080:8080"],
                "environment": {
                    "NODE_ENV": context.environment,
                },
                "healthcheck": {
                    "test": ["CMD", "curl", "-f", "http://localhost:8080/health"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                },
                "restart": "unless-stopped",
            }

            deps = [
                s["name"]
                for s in services
                if s["name"] in ("postgres", "redis", "mongodb", "mysql")
            ]
            if deps:
                compose["services"]["app"]["depends_on"] = {
                    dep: {"condition": "service_healthy"} for dep in deps
                }

        for service in services:
            name = service["name"]
            config = service["config"]

            if not config:
                config = {
                    "build": {"context": f"./{name}"},
                    "restart": "unless-stopped",
                }

            compose["services"][name] = config

            for vol in config.get("volumes", []):
                if isinstance(vol, str) and ":" in vol:
                    vol_name = vol.split(":")[0]
                    if not vol_name.startswith("./") and not vol_name.startswith("/"):
                        compose["volumes"][vol_name] = None

        return compose

    def _generate_env_example(self, compose: Dict[str, Any]) -> str:
        env_vars = set()

        for name, service in compose.get("services", {}).items():
            env = service.get("environment", {})
            if isinstance(env, dict):
                for key, value in env.items():
                    if isinstance(value, str) and "${" in value:
                        matches = re.findall(r"\$\{([^}:]+)", value)
                        env_vars.update(matches)
            elif isinstance(env, list):
                for item in env:
                    if "=" in item:
                        key = item.split("=")[0]
                        env_vars.add(key)

        lines = [
            "# Environment variables for Docker Compose",
            "# Copy this file to .env and fill in the values",
            "",
        ]

        for var in sorted(env_vars):
            if "PASSWORD" in var or "SECRET" in var:
                lines.append(f"{var}=changeme  # CHANGE THIS!")
            else:
                lines.append(f"{var}=")

        return "\n".join(lines)
