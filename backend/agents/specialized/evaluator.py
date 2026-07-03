import logging
import re
from typing import Any, Dict, Optional

from agents.core.base import (
    AgentConfig,
    BaseAgent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)

BEST_PRACTICES = {
    "terraform": [
        {
            "id": "TF001",
            "name": "Use variables for configuration",
            "pattern": r"var\.",
            "required": True,
            "message": "Use variables instead of hardcoded values",
        },
        {
            "id": "TF002",
            "name": "Use locals for computed values",
            "pattern": r"locals\s*{",
            "required": False,
            "message": "Consider using locals for computed values",
        },
        {
            "id": "TF003",
            "name": "Use modules for reusability",
            "pattern": r"module\s+",
            "required": False,
            "message": "Consider using modules for reusable infrastructure",
        },
        {
            "id": "TF004",
            "name": "Define outputs",
            "pattern": r"output\s+",
            "required": True,
            "message": "Define outputs for important resource attributes",
        },
        {
            "id": "TF005",
            "name": "Use resource naming convention",
            "pattern": r"name\s*=\s*\"[a-z][a-z0-9-]*\"",
            "required": True,
            "message": "Use lowercase with hyphens for resource names",
        },
        {
            "id": "TF006",
            "name": "Add descriptions to variables",
            "pattern": r"description\s*=",
            "required": True,
            "message": "Add descriptions to all variables",
        },
        {
            "id": "TF007",
            "name": "Use tags for resources",
            "pattern": r"tags\s*=",
            "required": True,
            "message": "Add tags to all resources for organization",
        },
    ],
    "kubernetes": [
        {
            "id": "K8S001",
            "name": "Define resource limits",
            "pattern": r"resources:\s*\n\s*limits:",
            "required": True,
            "message": "Define resource limits for containers",
        },
        {
            "id": "K8S002",
            "name": "Use readiness probes",
            "pattern": r"readinessProbe:",
            "required": True,
            "message": "Define readiness probes for containers",
        },
        {
            "id": "K8S003",
            "name": "Use liveness probes",
            "pattern": r"livenessProbe:",
            "required": True,
            "message": "Define liveness probes for containers",
        },
        {
            "id": "K8S004",
            "name": "Specify image tag",
            "pattern": r"image:\s*[^:]+:[^\s]+",
            "required": True,
            "message": "Always specify image tags, avoid using 'latest'",
        },
        {
            "id": "K8S005",
            "name": "Use namespaces",
            "pattern": r"namespace:",
            "required": True,
            "message": "Specify namespace for resources",
        },
    ],
}


class ValidateConfigurationTool(Tool):
    name = "validate_configuration"
    description = "Validate infrastructure configuration syntax and structure"

    async def execute(
        self,
        configuration: str,
        config_type: str = "terraform",
        **kwargs,
    ) -> ToolResult:
        errors = []
        warnings = []

        if config_type == "terraform":
            if configuration.count("{") != configuration.count("}"):
                errors.append(
                    {
                        "type": "syntax",
                        "message": "Mismatched braces in configuration",
                    }
                )

            if configuration.count('"') % 2 != 0:
                errors.append(
                    {
                        "type": "syntax",
                        "message": "Unclosed string literal",
                    }
                )

            if not re.search(r"provider\s+", configuration):
                warnings.append(
                    {
                        "type": "structure",
                        "message": "No provider block found",
                    }
                )

            if not re.search(r"resource\s+", configuration) and not re.search(
                r"module\s+", configuration
            ):
                warnings.append(
                    {
                        "type": "structure",
                        "message": "No resources or modules defined",
                    }
                )

        elif config_type == "kubernetes":
            try:
                import yaml

                yaml.safe_load(configuration)
            except:
                errors.append(
                    {
                        "type": "syntax",
                        "message": "Invalid YAML syntax",
                    }
                )

            if not re.search(r"apiVersion:", configuration):
                errors.append(
                    {
                        "type": "structure",
                        "message": "Missing apiVersion field",
                    }
                )

            if not re.search(r"kind:", configuration):
                errors.append(
                    {
                        "type": "structure",
                        "message": "Missing kind field",
                    }
                )

        valid = len(errors) == 0

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "valid": valid,
                "errors": errors,
                "warnings": warnings,
                "config_type": config_type,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Configuration to validate",
                },
                "config_type": {
                    "type": "string",
                    "description": "Type of configuration (terraform, kubernetes)",
                    "default": "terraform",
                },
            },
            "required": ["configuration"],
        }


class CheckBestPracticesTool(Tool):
    name = "check_best_practices"
    description = "Check infrastructure configuration against best practices"

    async def execute(
        self,
        configuration: str,
        config_type: str = "terraform",
        **kwargs,
    ) -> ToolResult:
        practices = BEST_PRACTICES.get(config_type, [])
        results = []
        score = 100

        for practice in practices:
            matches = re.search(
                practice["pattern"], configuration, re.IGNORECASE | re.MULTILINE
            )
            passed = matches is not None

            if not passed and practice["required"]:
                score -= 10
            elif not passed:
                score -= 5

            results.append(
                {
                    "id": practice["id"],
                    "name": practice["name"],
                    "passed": passed,
                    "required": practice["required"],
                    "message": practice["message"] if not passed else "OK",
                }
            )

        score = max(0, score)

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "config_type": config_type,
                "score": score,
                "grade": self._score_to_grade(score),
                "checks": results,
                "passed_count": sum(1 for r in results if r["passed"]),
                "total_count": len(results),
            },
        )

    def _score_to_grade(self, score: int) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Configuration to check",
                },
                "config_type": {
                    "type": "string",
                    "description": "Type of configuration (terraform, kubernetes)",
                    "default": "terraform",
                },
            },
            "required": ["configuration"],
        }


class AnalyzeComplexityTool(Tool):
    name = "analyze_complexity"
    description = "Analyze the complexity of infrastructure configuration"

    async def execute(
        self,
        configuration: str,
        **kwargs,
    ) -> ToolResult:
        metrics = {
            "lines_of_code": len(configuration.split("\n")),
            "resource_count": len(re.findall(r'resource\s+"', configuration)),
            "module_count": len(re.findall(r'module\s+"', configuration)),
            "variable_count": len(re.findall(r'variable\s+"', configuration)),
            "output_count": len(re.findall(r'output\s+"', configuration)),
            "data_source_count": len(re.findall(r'data\s+"', configuration)),
            "provider_count": len(re.findall(r'provider\s+"', configuration)),
        }

        complexity_score = (
            metrics["resource_count"] * 5
            + metrics["module_count"] * 10
            + metrics["data_source_count"] * 3
            + metrics["lines_of_code"] / 50
        )

        if complexity_score < 20:
            complexity_level = "low"
            recommendation = "Configuration is straightforward"
        elif complexity_score < 50:
            complexity_level = "medium"
            recommendation = "Consider breaking into modules for maintainability"
        else:
            complexity_level = "high"
            recommendation = "Strongly recommend modularization and documentation"

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "metrics": metrics,
                "complexity_score": round(complexity_score, 2),
                "complexity_level": complexity_level,
                "recommendation": recommendation,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Configuration to analyze",
                },
            },
            "required": ["configuration"],
        }


class GenerateImprovementsTool(Tool):
    name = "generate_improvements"
    description = "Generate suggestions for improving infrastructure configuration"

    async def execute(
        self,
        configuration: str,
        validation_results: Dict[str, Any] = None,
        best_practices_results: Dict[str, Any] = None,
        **kwargs,
    ) -> ToolResult:
        improvements = []
        priority_scores = {"high": 3, "medium": 2, "low": 1}

        if validation_results:
            for error in validation_results.get("errors", []):
                improvements.append(
                    {
                        "priority": "high",
                        "category": "syntax",
                        "issue": error.get("message"),
                        "suggestion": "Fix the syntax error before proceeding",
                    }
                )

            for warning in validation_results.get("warnings", []):
                improvements.append(
                    {
                        "priority": "medium",
                        "category": "structure",
                        "issue": warning.get("message"),
                        "suggestion": "Consider addressing this structural issue",
                    }
                )

        if best_practices_results:
            for check in best_practices_results.get("checks", []):
                if not check.get("passed"):
                    improvements.append(
                        {
                            "priority": "high" if check.get("required") else "medium",
                            "category": "best_practices",
                            "issue": check.get("message"),
                            "suggestion": f"Implement: {check.get('name')}",
                        }
                    )

        if "sensitive" not in configuration.lower():
            improvements.append(
                {
                    "priority": "medium",
                    "category": "security",
                    "issue": "No sensitive variables detected",
                    "suggestion": "Mark sensitive variables with 'sensitive = true'",
                }
            )

        if "lifecycle" not in configuration.lower():
            improvements.append(
                {
                    "priority": "low",
                    "category": "operations",
                    "issue": "No lifecycle rules defined",
                    "suggestion": "Consider adding lifecycle rules for critical resources",
                }
            )

        improvements.sort(
            key=lambda x: priority_scores.get(x["priority"], 0),
            reverse=True,
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "improvements": improvements,
                "total_improvements": len(improvements),
                "high_priority": sum(
                    1 for i in improvements if i["priority"] == "high"
                ),
                "medium_priority": sum(
                    1 for i in improvements if i["priority"] == "medium"
                ),
                "low_priority": sum(1 for i in improvements if i["priority"] == "low"),
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Configuration to improve",
                },
                "validation_results": {
                    "type": "object",
                    "description": "Results from validation check",
                },
                "best_practices_results": {
                    "type": "object",
                    "description": "Results from best practices check",
                },
            },
            "required": ["configuration"],
        }


class EvaluatorAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        default_config = AgentConfig(
            name="EvaluatorAgent",
            description="Infrastructure quality assurance and evaluation agent",
            temperature=0.1,
            max_iterations=10,
            tools=[
                "validate_configuration",
                "check_best_practices",
                "analyze_complexity",
                "generate_improvements",
            ],
        )
        super().__init__(config or default_config, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are an expert Evaluator Agent for Kube-Tofu.

Your role is to:
1. Validate infrastructure configurations for correctness
2. Check compliance with best practices
3. Analyze configuration complexity
4. Generate improvement suggestions
5. Ensure code quality and maintainability

Quality standards you enforce:
- Proper syntax and structure
- Use of variables and locals
- Modular design
- Resource naming conventions
- Documentation and comments
- Security best practices
- Error handling
- Testing coverage

When evaluating infrastructure:
- Be thorough but constructive
- Prioritize issues by severity
- Provide actionable suggestions
- Consider maintainability
- Check for common anti-patterns
- Verify resource dependencies

Grading criteria:
- A (90-100): Excellent, production-ready
- B (80-89): Good, minor improvements needed
- C (70-79): Acceptable, several issues to address
- D (60-69): Below standard, significant improvements needed
- F (<60): Not acceptable, major rework required

Always explain the reasoning behind your evaluations."""

    def _register_default_tools(self) -> None:
        self.tool_registry.register(ValidateConfigurationTool())
        self.tool_registry.register(CheckBestPracticesTool())
        self.tool_registry.register(AnalyzeComplexityTool())
        self.tool_registry.register(GenerateImprovementsTool())

    async def process_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return await self.run(task, context)

    async def evaluate(
        self,
        configuration: str,
        config_type: str = "terraform",
    ) -> Dict[str, Any]:
        task = f"""Perform a comprehensive evaluation of this {config_type} configuration:

{configuration}

Please:
1. Validate the configuration syntax
2. Check against best practices
3. Analyze complexity
4. Generate improvement suggestions
5. Provide an overall grade and summary
"""
        return await self.run(task, {"config_type": config_type})
