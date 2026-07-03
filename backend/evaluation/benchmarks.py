import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import random


class IaCType(Enum):
    TERRAFORM = "terraform"
    KUBERNETES = "kubernetes"
    DOCKERFILE = "dockerfile"
    DOCKER_COMPOSE = "docker_compose"
    HELM = "helm"
    ANSIBLE = "ansible"
    VAGRANT = "vagrant"


class DifficultyLevel(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class BenchmarkScenario:
    id: str
    name: str
    description: str
    natural_language_request: str
    expected_iac_types: List[IaCType]
    difficulty: DifficultyLevel
    required_resources: List[str]
    validation_criteria: Dict[str, Any]
    reference_solution: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "request": self.natural_language_request,
            "iac_types": [t.value for t in self.expected_iac_types],
            "difficulty": self.difficulty.value,
            "required_resources": self.required_resources,
            "validation_criteria": self.validation_criteria,
            "tags": self.tags,
        }


@dataclass
class BenchmarkResult:
    scenario_id: str
    success: bool
    iterations: int
    time_taken_ms: float
    syntax_valid: bool
    semantic_valid: bool
    deployable: bool
    quality_scores: Dict[str, float]
    errors: List[str] = field(default_factory=list)
    generated_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def first_attempt_success(self) -> bool:
        return self.success and self.iterations == 1


class BenchmarkRunner:
    def __init__(
        self,
        generator_fn: Optional[Callable[[str], str]] = None,
        validator_fn: Optional[Callable[[str, IaCType], Dict]] = None,
        max_iterations: int = 10,
    ):
        self.generator_fn = generator_fn
        self.validator_fn = validator_fn
        self.max_iterations = max_iterations
        self.results: List[BenchmarkResult] = []

    def run_scenario(
        self,
        scenario: BenchmarkScenario,
        generator_fn: Optional[Callable] = None,
    ) -> BenchmarkResult:
        gen_fn = generator_fn or self.generator_fn
        if not gen_fn:
            raise ValueError("No generator function provided")

        start_time = time.time()
        errors = []
        iterations = 0
        syntax_valid = False
        semantic_valid = False
        deployable = False
        generated_code = None
        quality_scores = {}

        feedback = None
        for i in range(self.max_iterations):
            iterations = i + 1
            try:
                if feedback:
                    prompt = f"{scenario.natural_language_request}\n\nPrevious errors to fix:\n{feedback}"
                else:
                    prompt = scenario.natural_language_request

                generated_code = gen_fn(prompt)

                validation = self._validate(
                    generated_code,
                    scenario.expected_iac_types[0]
                    if scenario.expected_iac_types
                    else IaCType.TERRAFORM,
                )

                syntax_valid = validation.get("syntax_valid", False)
                semantic_valid = validation.get("semantic_valid", False)
                deployable = validation.get("deployable", False)

                if validation.get("errors"):
                    feedback = "\n".join(validation["errors"])
                    errors.extend(validation["errors"])
                else:
                    feedback = None

                if deployable:
                    break

            except Exception as e:
                errors.append(str(e))
                feedback = str(e)

        time_taken = (time.time() - start_time) * 1000

        quality_scores = self._calculate_quality_scores(
            generated_code, scenario, syntax_valid, semantic_valid, deployable
        )

        result = BenchmarkResult(
            scenario_id=scenario.id,
            success=deployable,
            iterations=iterations,
            time_taken_ms=time_taken,
            syntax_valid=syntax_valid,
            semantic_valid=semantic_valid,
            deployable=deployable,
            quality_scores=quality_scores,
            errors=errors[:10],
            generated_code=generated_code,
            metadata={
                "difficulty": scenario.difficulty.value,
                "iac_types": [t.value for t in scenario.expected_iac_types],
            },
        )

        self.results.append(result)
        return result

    def run_all(
        self,
        scenarios: List[BenchmarkScenario],
        generator_fn: Optional[Callable] = None,
    ) -> List[BenchmarkResult]:
        results = []
        for scenario in scenarios:
            result = self.run_scenario(scenario, generator_fn)
            results.append(result)
        return results

    def _validate(self, code: str, iac_type: IaCType) -> Dict[str, Any]:
        if self.validator_fn:
            return self.validator_fn(code, iac_type)

        result = {
            "syntax_valid": False,
            "semantic_valid": False,
            "deployable": False,
            "errors": [],
        }

        if not code or len(code.strip()) < 10:
            result["errors"].append("Generated code is empty or too short")
            return result

        if iac_type == IaCType.TERRAFORM:
            result["syntax_valid"] = self._check_terraform_syntax(code)
        elif iac_type == IaCType.KUBERNETES:
            result["syntax_valid"] = self._check_yaml_syntax(code)
        elif iac_type == IaCType.DOCKERFILE:
            result["syntax_valid"] = self._check_dockerfile_syntax(code)
        elif iac_type == IaCType.DOCKER_COMPOSE:
            result["syntax_valid"] = self._check_yaml_syntax(code)
        elif iac_type == IaCType.ANSIBLE:
            result["syntax_valid"] = self._check_yaml_syntax(code)
        elif iac_type == IaCType.VAGRANT:
            result["syntax_valid"] = self._check_vagrant_syntax(code)
        else:
            result["syntax_valid"] = True

        if not result["syntax_valid"]:
            result["errors"].append(f"Syntax validation failed for {iac_type.value}")
            return result

        result["semantic_valid"] = self._check_semantic_validity(code, iac_type)

        if not result["semantic_valid"]:
            result["errors"].append("Semantic validation failed")
            return result

        result["deployable"] = result["semantic_valid"]

        return result

    def _check_terraform_syntax(self, code: str) -> bool:
        if code.count("{") != code.count("}"):
            return False

        keywords = [
            "resource",
            "provider",
            "variable",
            "output",
            "module",
            "data",
            "terraform",
        ]
        if not any(kw in code for kw in keywords):
            return False
        return True

    def _check_yaml_syntax(self, code: str) -> bool:
        try:
            import yaml

            list(yaml.safe_load_all(code))
            return True
        except:
            return False

    def _check_dockerfile_syntax(self, code: str) -> bool:
        lines = [
            l.strip()
            for l in code.split("\n")
            if l.strip() and not l.strip().startswith("#")
        ]
        if not lines:
            return False

        first_instruction = lines[0].split()[0].upper() if lines[0].split() else ""
        return first_instruction in ["FROM", "ARG"]

    def _check_vagrant_syntax(self, code: str) -> bool:
        return "Vagrant.configure" in code and "config.vm" in code

    def _check_semantic_validity(self, code: str, iac_type: IaCType) -> bool:
        if iac_type == IaCType.KUBERNETES:
            return "apiVersion" in code and "kind" in code
        elif iac_type == IaCType.TERRAFORM:
            return "resource" in code or "module" in code or "data" in code
        return True

    def _calculate_quality_scores(
        self,
        code: Optional[str],
        scenario: BenchmarkScenario,
        syntax_valid: bool,
        semantic_valid: bool,
        deployable: bool,
    ) -> Dict[str, float]:
        scores = {
            "syntax_correctness": 1.0 if syntax_valid else 0.0,
            "semantic_validity": 1.0 if semantic_valid else 0.0,
            "deployability": 1.0 if deployable else 0.0,
            "completeness": 0.0,
            "readability": 0.0,
            "parameterization": 0.0,
        }

        if not code:
            return scores

        mentioned = sum(
            1 for r in scenario.required_resources if r.lower() in code.lower()
        )
        scores["completeness"] = mentioned / max(len(scenario.required_resources), 1)

        lines = code.split("\n")
        comment_lines = sum(
            1 for l in lines if l.strip().startswith("#") or l.strip().startswith("//")
        )
        scores["readability"] = min(1.0, comment_lines / max(len(lines), 1) * 5)

        var_patterns = ["var.", "${", "variable", "vars.", "{{"]
        var_count = sum(code.count(p) for p in var_patterns)
        scores["parameterization"] = min(1.0, var_count / 10)

        return scores

    def get_summary(self) -> Dict[str, Any]:
        if not self.results:
            return {}

        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        first_attempt = sum(1 for r in self.results if r.first_attempt_success)

        pass_at_k = {}
        for k in [1, 5, 10, 25]:
            pass_at_k[k] = (
                sum(1 for r in self.results if r.success and r.iterations <= k) / total
            )

        avg_iterations = sum(r.iterations for r in self.results) / total
        avg_time = sum(r.time_taken_ms for r in self.results) / total

        quality_dims = [
            "syntax_correctness",
            "semantic_validity",
            "deployability",
            "completeness",
            "readability",
            "parameterization",
        ]
        avg_quality = {}
        for dim in quality_dims:
            values = [r.quality_scores.get(dim, 0) for r in self.results]
            avg_quality[dim] = sum(values) / len(values)

        return {
            "total_scenarios": total,
            "successful": successful,
            "success_rate": successful / total,
            "first_attempt_success_rate": first_attempt / total,
            "pass_at_k": pass_at_k,
            "average_iterations": avg_iterations,
            "average_time_ms": avg_time,
            "average_quality_scores": avg_quality,
            "by_difficulty": self._group_by_difficulty(),
            "by_iac_type": self._group_by_iac_type(),
        }

    def _group_by_difficulty(self) -> Dict[str, Dict]:
        groups = {}
        for result in self.results:
            diff = result.metadata.get("difficulty", "unknown")
            if diff not in groups:
                groups[diff] = {"total": 0, "success": 0}
            groups[diff]["total"] += 1
            if result.success:
                groups[diff]["success"] += 1

        for diff in groups:
            groups[diff]["rate"] = groups[diff]["success"] / groups[diff]["total"]
        return groups

    def _group_by_iac_type(self) -> Dict[str, Dict]:
        groups = {}
        for result in self.results:
            types = result.metadata.get("iac_types", ["unknown"])
            for iac_type in types:
                if iac_type not in groups:
                    groups[iac_type] = {"total": 0, "success": 0}
                groups[iac_type]["total"] += 1
                if result.success:
                    groups[iac_type]["success"] += 1

        for iac_type in groups:
            groups[iac_type]["rate"] = (
                groups[iac_type]["success"] / groups[iac_type]["total"]
            )
        return groups


def create_iac_benchmarks() -> List[BenchmarkScenario]:
    scenarios = []

    scenarios.append(
        BenchmarkScenario(
            id="simple-001",
            name="Basic Web Server Dockerfile",
            description="Generate a Dockerfile for a simple Python Flask web application",
            natural_language_request="Create a Dockerfile for a Python Flask application that runs on port 5000",
            expected_iac_types=[IaCType.DOCKERFILE],
            difficulty=DifficultyLevel.SIMPLE,
            required_resources=["python", "flask", "port_5000"],
            validation_criteria={"has_from": True, "has_expose": True, "has_cmd": True},
            tags=["docker", "python", "web"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="simple-002",
            name="Basic Nginx ConfigMap",
            description="Generate a Kubernetes ConfigMap for Nginx configuration",
            natural_language_request="Create a Kubernetes ConfigMap named nginx-config with a basic nginx.conf file",
            expected_iac_types=[IaCType.KUBERNETES],
            difficulty=DifficultyLevel.SIMPLE,
            required_resources=["configmap", "nginx"],
            validation_criteria={"kind": "ConfigMap", "has_data": True},
            tags=["kubernetes", "nginx", "configmap"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="simple-003",
            name="AWS S3 Bucket",
            description="Generate Terraform for a simple S3 bucket",
            natural_language_request="Create a Terraform configuration for an AWS S3 bucket with versioning enabled",
            expected_iac_types=[IaCType.TERRAFORM],
            difficulty=DifficultyLevel.SIMPLE,
            required_resources=["aws_s3_bucket", "versioning"],
            validation_criteria={"has_resource": True, "has_versioning": True},
            tags=["terraform", "aws", "s3"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="simple-004",
            name="Basic Vagrant Box",
            description="Generate a simple Vagrant configuration",
            natural_language_request="Create a Vagrantfile for an Ubuntu 22.04 virtual machine with 2GB RAM",
            expected_iac_types=[IaCType.VAGRANT],
            difficulty=DifficultyLevel.SIMPLE,
            required_resources=["ubuntu", "memory_2gb"],
            validation_criteria={"has_box": True, "has_memory": True},
            tags=["vagrant", "ubuntu", "vm"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="simple-005",
            name="Ansible Ping Playbook",
            description="Generate a simple Ansible playbook",
            natural_language_request="Create an Ansible playbook that pings all hosts and installs curl",
            expected_iac_types=[IaCType.ANSIBLE],
            difficulty=DifficultyLevel.SIMPLE,
            required_resources=["ping", "apt", "curl"],
            validation_criteria={"has_hosts": True, "has_tasks": True},
            tags=["ansible", "playbook", "basic"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="medium-001",
            name="Multi-stage Docker Build",
            description="Generate a multi-stage Dockerfile for a Node.js application",
            natural_language_request="Create a multi-stage Dockerfile for a Node.js application with build and production stages, using node:18-alpine",
            expected_iac_types=[IaCType.DOCKERFILE],
            difficulty=DifficultyLevel.MEDIUM,
            required_resources=["node", "multi_stage", "alpine", "npm_build"],
            validation_criteria={"has_multi_stage": True, "has_alpine": True},
            tags=["docker", "nodejs", "multi-stage"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="medium-002",
            name="Kubernetes Deployment with Service",
            description="Generate a Kubernetes Deployment and Service for a web application",
            natural_language_request="Create a Kubernetes Deployment with 3 replicas for a web application on port 8080, with a LoadBalancer Service",
            expected_iac_types=[IaCType.KUBERNETES],
            difficulty=DifficultyLevel.MEDIUM,
            required_resources=["deployment", "service", "replicas", "loadbalancer"],
            validation_criteria={
                "has_deployment": True,
                "has_service": True,
                "replicas": 3,
            },
            tags=["kubernetes", "deployment", "service"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="medium-003",
            name="Docker Compose Web Stack",
            description="Generate a Docker Compose file for a web application with database",
            natural_language_request="Create a Docker Compose file with nginx, a Python app, and PostgreSQL with persistent volume",
            expected_iac_types=[IaCType.DOCKER_COMPOSE],
            difficulty=DifficultyLevel.MEDIUM,
            required_resources=["nginx", "python", "postgresql", "volumes"],
            validation_criteria={"services_count": 3, "has_volumes": True},
            tags=["docker-compose", "nginx", "postgresql"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="medium-004",
            name="AWS VPC with Subnets",
            description="Generate Terraform for AWS VPC infrastructure",
            natural_language_request="Create Terraform for an AWS VPC with 2 public and 2 private subnets across 2 availability zones",
            expected_iac_types=[IaCType.TERRAFORM],
            difficulty=DifficultyLevel.MEDIUM,
            required_resources=["vpc", "subnet", "internet_gateway", "nat_gateway"],
            validation_criteria={"has_vpc": True, "subnet_count": 4},
            tags=["terraform", "aws", "vpc", "networking"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="medium-005",
            name="Ansible LAMP Stack",
            description="Generate an Ansible playbook for LAMP stack installation",
            natural_language_request="Create an Ansible playbook to install and configure Apache, MySQL, and PHP on Ubuntu servers",
            expected_iac_types=[IaCType.ANSIBLE],
            difficulty=DifficultyLevel.MEDIUM,
            required_resources=["apache", "mysql", "php", "handlers"],
            validation_criteria={"has_handlers": True, "package_count": 3},
            tags=["ansible", "lamp", "ubuntu"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="complex-001",
            name="Kubernetes StatefulSet with PVC",
            description="Generate a Kubernetes StatefulSet for a database with persistent storage",
            natural_language_request="Create a Kubernetes StatefulSet for PostgreSQL with 3 replicas, persistent volume claims, headless service, and resource limits",
            expected_iac_types=[IaCType.KUBERNETES],
            difficulty=DifficultyLevel.COMPLEX,
            required_resources=[
                "statefulset",
                "pvc",
                "headless_service",
                "resource_limits",
                "postgresql",
            ],
            validation_criteria={
                "has_statefulset": True,
                "has_pvc": True,
                "has_service": True,
            },
            tags=["kubernetes", "statefulset", "postgresql", "persistent"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="complex-002",
            name="Helm Chart for Microservice",
            description="Generate a Helm chart for a microservice application",
            natural_language_request="Create a Helm chart for a microservice with Deployment, Service, Ingress, HPA, and configurable values",
            expected_iac_types=[IaCType.HELM],
            difficulty=DifficultyLevel.COMPLEX,
            required_resources=["deployment", "service", "ingress", "hpa", "values"],
            validation_criteria={
                "has_chart_yaml": True,
                "has_values": True,
                "has_templates": True,
            },
            tags=["helm", "kubernetes", "microservice"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="complex-003",
            name="AWS EKS Cluster",
            description="Generate Terraform for an AWS EKS cluster",
            natural_language_request="Create Terraform for an AWS EKS cluster with managed node groups, IAM roles, and VPC configuration",
            expected_iac_types=[IaCType.TERRAFORM],
            difficulty=DifficultyLevel.COMPLEX,
            required_resources=[
                "eks_cluster",
                "node_group",
                "iam_role",
                "vpc",
                "security_group",
            ],
            validation_criteria={
                "has_eks": True,
                "has_iam": True,
                "has_node_group": True,
            },
            tags=["terraform", "aws", "eks", "kubernetes"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="complex-004",
            name="Multi-Container Pod with Sidecar",
            description="Generate a Kubernetes Pod with main container and sidecar",
            natural_language_request="Create a Kubernetes Pod with a main application container, a logging sidecar using fluentd, and shared volume",
            expected_iac_types=[IaCType.KUBERNETES],
            difficulty=DifficultyLevel.COMPLEX,
            required_resources=[
                "pod",
                "containers",
                "sidecar",
                "shared_volume",
                "fluentd",
            ],
            validation_criteria={"container_count": 2, "has_shared_volume": True},
            tags=["kubernetes", "pod", "sidecar", "logging"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="complex-005",
            name="Ansible Role for Kubernetes",
            description="Generate an Ansible role for Kubernetes cluster setup",
            natural_language_request="Create an Ansible role to set up a Kubernetes cluster with containerd, kubeadm, and CNI plugin",
            expected_iac_types=[IaCType.ANSIBLE],
            difficulty=DifficultyLevel.COMPLEX,
            required_resources=["containerd", "kubeadm", "cni", "role_structure"],
            validation_criteria={
                "has_tasks": True,
                "has_handlers": True,
                "has_defaults": True,
            },
            tags=["ansible", "kubernetes", "role"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="expert-001",
            name="Full Stack K8s Application",
            description="Generate complete Kubernetes manifests for a full-stack application",
            natural_language_request="""Create Kubernetes manifests for a full-stack application with:
        - Frontend deployment with nginx (3 replicas)
        - Backend API deployment with Node.js (3 replicas)
        - PostgreSQL StatefulSet
        - Redis deployment for caching
        - Ingress with TLS
        - Network policies
        - Resource quotas and limits
        - Horizontal Pod Autoscalers""",
            expected_iac_types=[IaCType.KUBERNETES],
            difficulty=DifficultyLevel.EXPERT,
            required_resources=[
                "deployment",
                "statefulset",
                "service",
                "ingress",
                "hpa",
                "network_policy",
                "pvc",
            ],
            validation_criteria={
                "deployment_count": 3,
                "has_ingress": True,
                "has_hpa": True,
                "has_network_policy": True,
            },
            tags=["kubernetes", "full-stack", "production"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="expert-002",
            name="AWS Production Infrastructure",
            description="Generate Terraform for production-ready AWS infrastructure",
            natural_language_request="""Create Terraform for production AWS infrastructure:
        - VPC with public/private subnets across 3 AZs
        - EKS cluster with managed node groups
        - RDS PostgreSQL with Multi-AZ
        - ElastiCache Redis cluster
        - ALB with WAF
        - CloudWatch alarms and dashboards
        - Secrets Manager for credentials
        - S3 buckets with encryption""",
            expected_iac_types=[IaCType.TERRAFORM],
            difficulty=DifficultyLevel.EXPERT,
            required_resources=[
                "vpc",
                "eks",
                "rds",
                "elasticache",
                "alb",
                "waf",
                "cloudwatch",
                "s3",
            ],
            validation_criteria={
                "module_count": 5,
                "has_rds": True,
                "has_encryption": True,
            },
            tags=["terraform", "aws", "production", "enterprise"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="expert-003",
            name="Complete CI/CD Pipeline IaC",
            description="Generate infrastructure for a complete CI/CD pipeline",
            natural_language_request="""Create infrastructure code for a CI/CD pipeline:
        - Docker Compose for local development environment
        - Kubernetes manifests for staging/production
        - Terraform for cloud resources
        - Ansible playbook for server configuration
        All configurations should use consistent naming and be parameterized for different environments""",
            expected_iac_types=[
                IaCType.DOCKER_COMPOSE,
                IaCType.KUBERNETES,
                IaCType.TERRAFORM,
                IaCType.ANSIBLE,
            ],
            difficulty=DifficultyLevel.EXPERT,
            required_resources=[
                "docker_compose",
                "kubernetes",
                "terraform",
                "ansible",
                "environments",
            ],
            validation_criteria={"format_count": 4, "has_environment_vars": True},
            tags=["ci-cd", "multi-format", "environments"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="arvan-001",
            name="ArvanCloud VM Instance",
            description="Generate Terraform for ArvanCloud compute instance",
            natural_language_request="Create Terraform configuration for an ArvanCloud VM instance with Ubuntu 22.04, 2 vCPU, 4GB RAM in ir-thr-ba1 region",
            expected_iac_types=[IaCType.TERRAFORM],
            difficulty=DifficultyLevel.MEDIUM,
            required_resources=["arvancloud_iaas_abrak", "flavor", "image", "network"],
            validation_criteria={"provider": "arvancloud", "has_instance": True},
            tags=["terraform", "arvancloud", "compute"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="arvan-002",
            name="ArvanCloud Network Setup",
            description="Generate Terraform for ArvanCloud network infrastructure",
            natural_language_request="Create Terraform for ArvanCloud network with VPC, subnet, security group allowing SSH and HTTP, and floating IP",
            expected_iac_types=[IaCType.TERRAFORM],
            difficulty=DifficultyLevel.MEDIUM,
            required_resources=[
                "arvancloud_iaas_network",
                "arvancloud_iaas_subnet",
                "arvancloud_iaas_security_group",
                "arvancloud_iaas_floatingip",
            ],
            validation_criteria={
                "provider": "arvancloud",
                "has_network": True,
                "has_security_group": True,
            },
            tags=["terraform", "arvancloud", "networking"],
        )
    )

    scenarios.append(
        BenchmarkScenario(
            id="arvan-003",
            name="ArvanCloud Kubernetes Cluster",
            description="Generate Terraform for ArvanCloud managed Kubernetes",
            natural_language_request="Create Terraform for ArvanCloud managed Kubernetes cluster with 3 worker nodes and auto-scaling",
            expected_iac_types=[IaCType.TERRAFORM],
            difficulty=DifficultyLevel.COMPLEX,
            required_resources=[
                "arvancloud_iaas_k8s_cluster",
                "node_pool",
                "auto_scaling",
            ],
            validation_criteria={"provider": "arvancloud", "has_k8s": True},
            tags=["terraform", "arvancloud", "kubernetes"],
        )
    )

    return scenarios


def create_synthetic_test_data(n_samples: int = 1000, seed: int = 42) -> Dict[str, Any]:
    random.seed(seed)

    iac_samples = []
    iac_labels = []

    iac_types = [
        "terraform",
        "kubernetes",
        "dockerfile",
        "docker_compose",
        "ansible",
        "vagrant",
        "helm",
    ]

    for _ in range(n_samples):
        iac_type = random.choice(iac_types)

        features = {
            "code_length": random.randint(100, 5000),
            "line_count": random.randint(10, 200),
            "brace_count": 0,
            "colon_count": 0,
            "keyword_resource": 0,
            "keyword_apiVersion": 0,
            "keyword_FROM": 0,
            "keyword_services": 0,
            "keyword_hosts": 0,
            "keyword_Vagrant": 0,
            "unique_tokens": random.randint(20, 200),
            "comment_density": random.uniform(0.01, 0.2),
            "nesting_depth": random.randint(1, 10),
        }

        if iac_type == "terraform":
            features["brace_count"] = random.randint(10, 100)
            features["keyword_resource"] = random.randint(1, 20)
        elif iac_type == "kubernetes":
            features["colon_count"] = random.randint(20, 150)
            features["keyword_apiVersion"] = random.randint(1, 10)
        elif iac_type == "dockerfile":
            features["keyword_FROM"] = random.randint(1, 5)
        elif iac_type == "docker_compose":
            features["colon_count"] = random.randint(15, 80)
            features["keyword_services"] = random.randint(1, 10)
        elif iac_type == "ansible":
            features["colon_count"] = random.randint(20, 100)
            features["keyword_hosts"] = random.randint(1, 5)
        elif iac_type == "vagrant":
            features["keyword_Vagrant"] = random.randint(1, 3)
            features["brace_count"] = random.randint(5, 30)

        for key in features:
            if isinstance(features[key], int) and features[key] > 0:
                features[key] += random.randint(-2, 2)
                features[key] = max(0, features[key])

        iac_samples.append(list(features.values()))
        iac_labels.append(iac_types.index(iac_type))

    normal_samples = []
    anomaly_samples = []

    for _ in range(int(n_samples * 0.9)):
        sample = [
            random.gauss(100, 20),
            random.gauss(60, 15),
            random.gauss(500, 100),
            random.gauss(50, 10),
            random.gauss(10, 3),
        ]
        normal_samples.append(sample)

    for _ in range(int(n_samples * 0.1)):
        sample = [
            random.gauss(100, 20) + random.choice([50, -30]),
            random.gauss(60, 15) + random.choice([40, -20]),
            random.gauss(500, 100) * random.choice([2, 0.3]),
            random.gauss(50, 10) + random.choice([30, -25]),
            random.gauss(10, 3) * random.choice([3, 5]),
        ]
        anomaly_samples.append(sample)

    return {
        "classification": {
            "samples": iac_samples,
            "labels": iac_labels,
            "label_names": iac_types,
            "feature_names": list(features.keys()),
        },
        "anomaly_detection": {
            "normal": normal_samples,
            "anomalies": anomaly_samples,
        },
        "metadata": {
            "n_samples": n_samples,
            "seed": seed,
            "generated_at": datetime.now().isoformat(),
        },
    }
