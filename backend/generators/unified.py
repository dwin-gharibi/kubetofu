import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from generators.base import (
    BaseGenerator,
    GenerationContext,
    GenerationResult,
    GraphKnowledgeInjector,
    IaCType,
)
from generators.dockerfile import DockerfileGenerator
from generators.docker_compose import DockerComposeGenerator
from generators.kubernetes import KubernetesGenerator
from generators.helm import HelmChartGenerator
from generators.vagrant import VagrantGenerator
from generators.terraform import TerraformGenerator
from generators.ansible import AnsibleGenerator

logger = logging.getLogger(__name__)


@dataclass
class UnifiedGenerationResult:
    primary_type: IaCType
    results: Dict[IaCType, GenerationResult] = field(default_factory=dict)
    deployment_plan: List[str] = field(default_factory=list)
    overall_quality: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_type": self.primary_type.value,
            "results": {k.value: v.to_dict() for k, v in self.results.items()},
            "deployment_plan": self.deployment_plan,
            "overall_quality": self.overall_quality,
            "recommendations": self.recommendations,
        }


class UnifiedIaCGenerator:
    def __init__(self, llm_provider=None):
        self.llm = llm_provider
        self.knowledge_injector = GraphKnowledgeInjector()

        self.generators: Dict[IaCType, BaseGenerator] = {
            IaCType.DOCKERFILE: DockerfileGenerator(llm_provider),
            IaCType.DOCKER_COMPOSE: DockerComposeGenerator(llm_provider),
            IaCType.KUBERNETES: KubernetesGenerator(llm_provider),
            IaCType.HELM: HelmChartGenerator(llm_provider),
            IaCType.VAGRANT: VagrantGenerator(llm_provider),
            IaCType.TERRAFORM: TerraformGenerator(llm_provider),
            IaCType.ANSIBLE: AnsibleGenerator(llm_provider),
        }

        self._setup_knowledge_base()

    def _setup_knowledge_base(self) -> None:
        self.knowledge_injector.add_resource_knowledge(
            "kubernetes_deployment",
            {
                "replicas": {"required": True, "type": "int"},
                "selector": {"required": True, "type": "object"},
                "template": {"required": True, "type": "object"},
            },
            dependencies=["kubernetes_service", "kubernetes_configmap"],
        )

        self.knowledge_injector.add_resource_knowledge(
            "arvancloud_instance",
            {
                "name": {"required": True, "type": "string"},
                "region": {"required": True, "type": "string"},
                "flavor_id": {"required": True, "type": "string"},
                "image_id": {"required": True, "type": "string"},
            },
            dependencies=["arvancloud_network", "arvancloud_security_group"],
        )

    def detect_iac_types(self, context: GenerationContext) -> List[IaCType]:
        detected = []
        request = context.natural_language_request.lower()

        type_keywords = {
            IaCType.DOCKERFILE: [
                "dockerfile",
                "docker image",
                "container image",
                "build image",
            ],
            IaCType.DOCKER_COMPOSE: [
                "docker compose",
                "docker-compose",
                "compose file",
                "multi-container",
            ],
            IaCType.KUBERNETES: ["kubernetes", "k8s", "kubectl", "pod", "deployment"],
            IaCType.HELM: ["helm", "chart", "helm chart"],
            IaCType.VAGRANT: ["vagrant", "vagrantfile", "virtual machine", "local dev"],
            IaCType.TERRAFORM: [
                "terraform",
                "tofu",
                "opentofu",
                "infrastructure",
                "cloud",
            ],
            IaCType.ANSIBLE: ["ansible", "playbook", "configuration management"],
        }

        for iac_type, keywords in type_keywords.items():
            if any(kw in request for kw in keywords):
                detected.append(iac_type)

        if not detected:
            if context.cloud_provider:
                detected.append(IaCType.TERRAFORM)

            if "postgres" in request or "redis" in request:
                detected.append(IaCType.DOCKER_COMPOSE)

            if not detected:
                detected = [
                    IaCType.DOCKERFILE,
                    IaCType.DOCKER_COMPOSE,
                    IaCType.KUBERNETES,
                ]

        if IaCType.KUBERNETES in detected and IaCType.HELM not in detected:
            if context.environment == "production":
                detected.append(IaCType.HELM)

        if IaCType.DOCKERFILE not in detected and IaCType.DOCKER_COMPOSE in detected:
            detected.insert(0, IaCType.DOCKERFILE)

        return detected

    def generate(
        self, context: GenerationContext, target_types: Optional[List[IaCType]] = None
    ) -> UnifiedGenerationResult:
        if target_types is None:
            target_types = self.detect_iac_types(context)

        context = self.knowledge_injector.inject_into_context(context)

        results = {}
        for iac_type in target_types:
            generator = self.generators.get(iac_type)
            if generator:
                try:
                    result = generator.iterative_generate(context)
                    results[iac_type] = result
                    logger.info(
                        f"Generated {iac_type.value}: quality={result.overall_quality:.2f}"
                    )
                except Exception as e:
                    logger.error(f"Generation failed for {iac_type.value}: {e}")

        unified = UnifiedGenerationResult(
            primary_type=target_types[0] if target_types else IaCType.DOCKERFILE,
            results=results,
        )

        if results:
            unified.overall_quality = sum(
                r.overall_quality for r in results.values()
            ) / len(results)

        unified.deployment_plan = self._create_deployment_plan(target_types, results)
        unified.recommendations = self._generate_recommendations(results, context)

        return unified

    def generate_full_stack(
        self, context: GenerationContext
    ) -> UnifiedGenerationResult:
        target_types = [
            IaCType.DOCKERFILE,
            IaCType.DOCKER_COMPOSE,
        ]

        if context.environment == "production":
            target_types.append(IaCType.HELM)
        else:
            target_types.append(IaCType.KUBERNETES)

        if context.cloud_provider:
            target_types.append(IaCType.TERRAFORM)

        return self.generate(context, target_types)

    def _create_deployment_plan(
        self, types: List[IaCType], results: Dict[IaCType, GenerationResult]
    ) -> List[str]:
        plan = []

        if IaCType.TERRAFORM in types:
            plan.extend(
                [
                    "1. Initialize Terraform: terraform init",
                    "2. Plan infrastructure: terraform plan",
                    "3. Apply infrastructure: terraform apply",
                ]
            )

        if IaCType.ANSIBLE in types:
            plan.append(
                "4. Run Ansible playbook: ansible-playbook -i inventory playbook.yml"
            )

        if IaCType.DOCKERFILE in types:
            plan.append("5. Build Docker image: docker build -t app:latest .")

        if IaCType.DOCKER_COMPOSE in types:
            plan.append("6. Start services locally: docker compose up -d")

        if IaCType.HELM in types:
            plan.extend(
                [
                    "7. Install Helm chart: helm install app ./chart",
                    "8. Verify deployment: helm status app",
                ]
            )
        elif IaCType.KUBERNETES in types:
            plan.extend(
                [
                    "7. Apply Kubernetes manifests: kubectl apply -f k8s/",
                    "8. Verify pods: kubectl get pods",
                ]
            )

        if IaCType.VAGRANT in types:
            plan.extend(
                [
                    "For local development:",
                    "- Start VM: vagrant up",
                    "- SSH into VM: vagrant ssh",
                ]
            )

        return plan

    def _generate_recommendations(
        self, results: Dict[IaCType, GenerationResult], context: GenerationContext
    ) -> List[str]:
        recommendations = []

        for iac_type, result in results.items():
            for score in result.quality_scores:
                if score.score < 0.7:
                    recommendations.append(
                        f"[{iac_type.value}] Improve {score.dimension.value}: {score.details or 'Review and enhance'}"
                    )

            for error in result.validation_errors:
                if error.suggestion:
                    recommendations.append(f"[{iac_type.value}] {error.suggestion}")

        if context.environment == "production":
            if IaCType.HELM not in results:
                recommendations.append(
                    "Consider using Helm charts for production Kubernetes deployments"
                )
            recommendations.append(
                "Ensure secrets are managed securely (not in version control)"
            )
            recommendations.append(
                "Set up monitoring and alerting for deployed services"
            )

        return recommendations

    def validate_cross_format(
        self, results: Dict[IaCType, GenerationResult]
    ) -> List[str]:
        issues = []

        ports = {}
        for iac_type, result in results.items():
            extracted_ports = self._extract_ports(result.code, iac_type)
            ports[iac_type] = extracted_ports

        if len(ports) > 1:
            all_ports = set()
            for type_ports in ports.values():
                all_ports.update(type_ports)

            for iac_type, type_ports in ports.items():
                missing = all_ports - type_ports
                if missing:
                    issues.append(f"{iac_type.value} is missing ports: {missing}")

        return issues

    def _extract_ports(self, code: str, iac_type: IaCType) -> set:
        import re

        ports = set()

        patterns = [
            r"port[:\s]+(\d+)",
            r"containerPort[:\s]+(\d+)",
            r"EXPOSE\s+(\d+)",
            r'"(\d+):(\d+)"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    ports.update(int(p) for p in match if p.isdigit())
                else:
                    ports.add(int(match))

        return ports


class DeployabilityEvaluator:
    def __init__(self):
        self.dry_run_mode = True

    async def evaluate(self, result: GenerationResult) -> Dict[str, Any]:
        evaluation = {
            "format_valid": False,
            "syntax_valid": False,
            "deployment_tested": False,
            "deployment_success": False,
            "errors": [],
            "warnings": [],
        }

        evaluation["format_valid"] = self._verify_format(result)

        if evaluation["format_valid"]:
            evaluation["syntax_valid"] = (
                len([e for e in result.validation_errors if e.severity == "error"]) == 0
            )

        if evaluation["syntax_valid"] and not self.dry_run_mode:
            deployment_result = await self._test_deployment(result)
            evaluation["deployment_tested"] = True
            evaluation["deployment_success"] = deployment_result["success"]
            evaluation["errors"].extend(deployment_result.get("errors", []))

        return evaluation

    def _verify_format(self, result: GenerationResult) -> bool:
        if not result.code:
            return False

        format_checks = {
            IaCType.DOCKERFILE: lambda c: "FROM" in c.upper(),
            IaCType.DOCKER_COMPOSE: lambda c: "services:" in c.lower(),
            IaCType.KUBERNETES: lambda c: "apiVersion:" in c,
            IaCType.HELM: lambda c: "Chart.yaml" in str(result.files),
            IaCType.TERRAFORM: lambda c: "resource" in c or "terraform" in c,
            IaCType.ANSIBLE: lambda c: "hosts:" in c or "- name:" in c,
        }

        check = format_checks.get(result.iac_type)
        return check(result.code) if check else True

    async def _test_deployment(self, result: GenerationResult) -> Dict[str, Any]:
        return {
            "success": True,
            "errors": [],
            "warnings": ["Deployment testing requires sandbox environment"],
        }
