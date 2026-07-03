import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


class IaCType(str, Enum):
    DOCKERFILE = "dockerfile"
    DOCKER_COMPOSE = "docker_compose"
    KUBERNETES = "kubernetes"
    HELM = "helm"
    VAGRANT = "vagrant"
    TERRAFORM = "terraform"
    OPENTOFU = "opentofu"
    ANSIBLE = "ansible"
    CLOUDFORMATION = "cloudformation"
    PULUMI = "pulumi"


class QualityDimension(str, Enum):
    SYNTAX_CORRECTNESS = "syntax_correctness"
    SEMANTIC_VALIDITY = "semantic_validity"
    SCHEMA_COMPLIANCE = "schema_compliance"

    DEPLOYABILITY = "deployability"
    INTENT_ALIGNMENT = "intent_alignment"
    COMPLETENESS = "completeness"

    SECURITY_COMPLIANCE = "security_compliance"
    COST_EFFICIENCY = "cost_efficiency"
    PERFORMANCE = "performance"

    READABILITY = "readability"
    MODULARITY = "modularity"
    DOCUMENTATION = "documentation"

    IDEMPOTENCY = "idempotency"
    ERROR_HANDLING = "error_handling"
    PARAMETERIZATION = "parameterization"


class ErrorCategory(str, Enum):
    SYNTAX_INVALID_TOKEN = "syntax_invalid_token"
    SYNTAX_MISSING_BRACKET = "syntax_missing_bracket"
    SYNTAX_INDENTATION = "syntax_indentation"

    SEMANTIC_TYPE_MISMATCH = "semantic_type_mismatch"
    SEMANTIC_UNDEFINED_REFERENCE = "semantic_undefined_reference"
    SEMANTIC_CIRCULAR_DEPENDENCY = "semantic_circular_dependency"

    CONFIG_MISSING_REQUIRED = "config_missing_required"
    CONFIG_INVALID_VALUE = "config_invalid_value"
    CONFIG_DEPRECATED = "config_deprecated"

    PROVIDER_NOT_FOUND = "provider_not_found"
    PROVIDER_AUTH_FAILURE = "provider_auth_failure"
    PROVIDER_API_ERROR = "provider_api_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    RESOURCE_CONFLICT = "resource_conflict"

    INTENT_MISALIGNMENT = "intent_misalignment"
    INTENT_INCOMPLETE = "intent_incomplete"
    INTENT_OVER_SPECIFICATION = "intent_over_specification"


@dataclass
class ValidationError:
    category: ErrorCategory
    message: str
    location: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "location": self.location,
            "line": self.line,
            "suggestion": self.suggestion,
            "severity": self.severity,
        }


@dataclass
class QualityScore:
    dimension: QualityDimension
    score: float
    details: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationContext:
    natural_language_request: str
    target_type: IaCType

    cloud_provider: Optional[str] = None
    region: Optional[str] = None
    environment: str = "development"

    services: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

    security_requirements: List[str] = field(default_factory=list)
    compliance_frameworks: List[str] = field(default_factory=list)

    scalability_requirements: Optional[Dict[str, Any]] = None
    resource_limits: Optional[Dict[str, Any]] = None

    previous_attempts: List[Dict[str, Any]] = field(default_factory=list)
    feedback: Optional[str] = None

    injected_knowledge: Optional[Dict[str, Any]] = None

    def add_attempt(self, code: str, errors: List[ValidationError]) -> None:
        self.previous_attempts.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "code": code,
                "errors": [e.to_dict() for e in errors],
            }
        )


@dataclass
class GenerationResult:
    id: str
    iac_type: IaCType
    code: str
    files: Dict[str, str]
    is_valid: bool = False
    validation_errors: List[ValidationError] = field(default_factory=list)

    quality_scores: List[QualityScore] = field(default_factory=list)
    overall_quality: float = 0.0

    is_deployable: bool = False
    deployment_tested: bool = False
    deployment_errors: List[str] = field(default_factory=list)

    intent_alignment_score: float = 0.0
    correctness_congruence_gap: Optional[float] = None

    generation_time: float = 0.0
    iteration: int = 1
    model_used: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, iac_type: IaCType, code: str, **kwargs) -> "GenerationResult":
        return cls(
            id=str(uuid4()),
            iac_type=iac_type,
            code=code,
            files={f"main.{iac_type.value}": code},
            **kwargs,
        )

    def calculate_overall_quality(self) -> float:
        if not self.quality_scores:
            return 0.0

        weights = {
            QualityDimension.DEPLOYABILITY: 0.25,
            QualityDimension.INTENT_ALIGNMENT: 0.20,
            QualityDimension.SECURITY_COMPLIANCE: 0.15,
            QualityDimension.SYNTAX_CORRECTNESS: 0.10,
            QualityDimension.SEMANTIC_VALIDITY: 0.10,
            QualityDimension.COMPLETENESS: 0.10,
            QualityDimension.READABILITY: 0.05,
            QualityDimension.MODULARITY: 0.05,
        }

        total_weight = 0.0
        weighted_sum = 0.0

        for score in self.quality_scores:
            weight = weights.get(score.dimension, 0.05)
            weighted_sum += score.score * weight
            total_weight += weight

        self.overall_quality = weighted_sum / total_weight if total_weight > 0 else 0.0
        return self.overall_quality

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "iac_type": self.iac_type.value,
            "code": self.code,
            "files": self.files,
            "is_valid": self.is_valid,
            "validation_errors": [e.to_dict() for e in self.validation_errors],
            "quality_scores": [
                {"dimension": s.dimension.value, "score": s.score, "details": s.details}
                for s in self.quality_scores
            ],
            "overall_quality": self.overall_quality,
            "is_deployable": self.is_deployable,
            "deployment_tested": self.deployment_tested,
            "intent_alignment_score": self.intent_alignment_score,
            "generation_time": self.generation_time,
            "iteration": self.iteration,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseGenerator(ABC):
    iac_type: IaCType
    max_iterations: int = 10

    def __init__(self, llm_provider=None):
        self.llm = llm_provider
        self.validators: List[callable] = []
        self._setup_validators()

    @abstractmethod
    def _setup_validators(self) -> None:
        pass

    @abstractmethod
    def generate(self, context: GenerationContext) -> GenerationResult:
        pass

    @abstractmethod
    def validate_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        pass

    @abstractmethod
    def validate_semantics(self, code: str) -> Tuple[bool, List[ValidationError]]:
        pass

    def validate(self, code: str) -> Tuple[bool, List[ValidationError]]:
        all_errors = []

        syntax_valid, syntax_errors = self.validate_syntax(code)
        all_errors.extend(syntax_errors)

        if not syntax_valid:
            return False, all_errors

        semantic_valid, semantic_errors = self.validate_semantics(code)
        all_errors.extend(semantic_errors)

        for validator in self.validators:
            try:
                valid, errors = validator(code)
                all_errors.extend(errors)
            except Exception as e:
                logger.warning(f"Validator failed: {e}")

        return len(all_errors) == 0, all_errors

    def assess_quality(
        self, code: str, context: GenerationContext
    ) -> List[QualityScore]:
        scores = []

        syntax_valid, _ = self.validate_syntax(code)
        scores.append(
            QualityScore(
                dimension=QualityDimension.SYNTAX_CORRECTNESS,
                score=1.0 if syntax_valid else 0.0,
            )
        )

        semantic_valid, _ = self.validate_semantics(code)
        scores.append(
            QualityScore(
                dimension=QualityDimension.SEMANTIC_VALIDITY,
                score=1.0 if semantic_valid else 0.5,
            )
        )

        completeness = self._assess_completeness(code, context)
        scores.append(
            QualityScore(
                dimension=QualityDimension.COMPLETENESS,
                score=completeness,
            )
        )

        readability = self._assess_readability(code)
        scores.append(
            QualityScore(
                dimension=QualityDimension.READABILITY,
                score=readability,
            )
        )

        parameterization = self._assess_parameterization(code)
        scores.append(
            QualityScore(
                dimension=QualityDimension.PARAMETERIZATION,
                score=parameterization,
            )
        )

        return scores

    def _assess_completeness(self, code: str, context: GenerationContext) -> float:
        if not context.services:
            return 1.0

        mentioned = sum(1 for s in context.services if s.lower() in code.lower())
        return mentioned / len(context.services)

    def _assess_readability(self, code: str) -> float:
        lines = code.split("\n")

        comment_lines = sum(
            1 for l in lines if l.strip().startswith("#") or l.strip().startswith("//")
        )
        comment_ratio = comment_lines / max(len(lines), 1)

        long_lines = sum(1 for l in lines if len(l) > 120)
        line_length_score = 1.0 - (long_lines / max(len(lines), 1))

        blank_ratio = sum(1 for l in lines if not l.strip()) / max(len(lines), 1)
        structure_score = 1.0 if 0.1 <= blank_ratio <= 0.3 else 0.5

        return comment_ratio * 0.3 + line_length_score * 0.4 + structure_score * 0.3

    def _assess_parameterization(self, code: str) -> float:
        import re

        var_patterns = [
            r"\$\{[^}]+\}",
            r"\{\{[^}]+\}\}",
            r"\$[A-Z_]+",
            r"var\.[a-z_]+",
            r"params\.[a-z_]+",
        ]

        total_vars = 0
        for pattern in var_patterns:
            total_vars += len(re.findall(pattern, code))

        lines = len(code.split("\n"))
        var_density = total_vars / max(lines, 1)

        return min(var_density * 10, 1.0)

    def iterative_generate(self, context: GenerationContext) -> GenerationResult:
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Generation iteration {iteration}/{self.max_iterations}")

            result = self.generate(context)
            result.iteration = iteration

            is_valid, errors = self.validate(result.code)
            result.is_valid = is_valid
            result.validation_errors = errors

            result.quality_scores = self.assess_quality(result.code, context)
            result.calculate_overall_quality()

            if is_valid and result.overall_quality >= 0.8:
                logger.info(f"Generation succeeded at iteration {iteration}")
                return result

            context.add_attempt(result.code, errors)

            if errors:
                context.feedback = self._create_feedback(errors)

        logger.warning("Max iterations reached without full success")
        return result

    def _create_feedback(self, errors: List[ValidationError]) -> str:
        feedback_lines = ["Fix the following issues:"]
        for i, error in enumerate(errors[:5], 1):
            feedback_lines.append(f"{i}. {error.message}")
            if error.suggestion:
                feedback_lines.append(f"   Suggestion: {error.suggestion}")
        return "\n".join(feedback_lines)


class GraphKnowledgeInjector:
    def __init__(self, knowledge_base=None):
        self.knowledge_base = knowledge_base or {}
        self.resource_graph: Dict[str, List[str]] = {}

    def add_resource_knowledge(
        self, resource_type: str, properties: Dict[str, Any], dependencies: List[str]
    ) -> None:
        self.knowledge_base[resource_type] = {
            "properties": properties,
            "required": [k for k, v in properties.items() if v.get("required")],
            "optional": [k for k, v in properties.items() if not v.get("required")],
        }
        self.resource_graph[resource_type] = dependencies

    def get_relevant_knowledge(self, context: GenerationContext) -> Dict[str, Any]:
        relevant = {}

        for service in context.services:
            service_lower = service.lower()
            for resource_type, knowledge in self.knowledge_base.items():
                if service_lower in resource_type.lower():
                    relevant[resource_type] = knowledge

                    for dep in self.resource_graph.get(resource_type, []):
                        if dep in self.knowledge_base:
                            relevant[dep] = self.knowledge_base[dep]

        return relevant

    def inject_into_context(self, context: GenerationContext) -> GenerationContext:
        context.injected_knowledge = self.get_relevant_knowledge(context)
        return context
