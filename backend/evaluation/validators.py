import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


class ValidationStage(Enum):
    FORMAT = "format"
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    DEPLOYMENT = "deployment"


class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationError:
    stage: ValidationStage
    severity: ErrorSeverity
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "severity": self.severity.value,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    valid: bool
    stage_reached: ValidationStage
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def format_valid(self) -> bool:
        return self.stage_reached.value in ["syntax", "semantic", "deployment"]

    @property
    def syntax_valid(self) -> bool:
        return self.stage_reached.value in ["semantic", "deployment"]

    @property
    def semantic_valid(self) -> bool:
        return self.stage_reached.value == "deployment"

    @property
    def deployable(self) -> bool:
        return self.valid and self.stage_reached == ValidationStage.DEPLOYMENT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "stage_reached": self.stage_reached.value,
            "format_valid": self.format_valid,
            "syntax_valid": self.syntax_valid,
            "semantic_valid": self.semantic_valid,
            "deployable": self.deployable,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "metadata": self.metadata,
        }


class BaseValidator(ABC):
    @abstractmethod
    def validate(self, code: str) -> ValidationResult:
        pass

    def _create_error(
        self,
        stage: ValidationStage,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        line: Optional[int] = None,
        suggestion: Optional[str] = None,
    ) -> ValidationError:
        return ValidationError(
            stage=stage,
            severity=severity,
            message=message,
            line=line,
            suggestion=suggestion,
        )


class SyntaxValidator(BaseValidator):
    def __init__(self, iac_type: str):
        self.iac_type = iac_type.lower()

    def validate(self, code: str) -> ValidationResult:
        if not code or not code.strip():
            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.FORMAT,
                errors=[
                    self._create_error(
                        ValidationStage.FORMAT,
                        "Empty or whitespace-only code",
                        suggestion="Provide non-empty configuration code",
                    )
                ],
            )

        if self.iac_type in ["terraform", "hcl", "tf"]:
            return self._validate_hcl(code)
        elif self.iac_type in [
            "kubernetes",
            "k8s",
            "yaml",
            "ansible",
            "docker_compose",
            "docker-compose",
            "helm",
        ]:
            return self._validate_yaml(code)
        elif self.iac_type in ["dockerfile", "docker"]:
            return self._validate_dockerfile(code)
        elif self.iac_type in ["vagrant", "vagrantfile"]:
            return self._validate_vagrantfile(code)
        else:
            return ValidationResult(
                valid=True,
                stage_reached=ValidationStage.SYNTAX,
                metadata={"iac_type": self.iac_type, "validation": "basic"},
            )

    def _validate_hcl(self, code: str) -> ValidationResult:
        errors = []
        warnings = []

        brace_count = 0
        bracket_count = 0
        in_string = False
        string_char = None
        line_num = 1

        for i, char in enumerate(code):
            if char == "\n":
                line_num += 1

            if char in ['"', "'"] and (i == 0 or code[i - 1] != "\\"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                continue

            if in_string:
                continue

            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count < 0:
                    errors.append(
                        self._create_error(
                            ValidationStage.SYNTAX,
                            "Unexpected closing brace",
                            line=line_num,
                            suggestion="Check for missing opening brace",
                        )
                    )
            elif char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1
                if bracket_count < 0:
                    errors.append(
                        self._create_error(
                            ValidationStage.SYNTAX,
                            "Unexpected closing bracket",
                            line=line_num,
                            suggestion="Check for missing opening bracket",
                        )
                    )

        if brace_count != 0:
            errors.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    f"Unbalanced braces: {brace_count} unclosed",
                    suggestion="Add closing braces to balance",
                )
            )

        if bracket_count != 0:
            errors.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    f"Unbalanced brackets: {bracket_count} unclosed",
                    suggestion="Add closing brackets to balance",
                )
            )

        keywords = [
            "resource",
            "provider",
            "variable",
            "output",
            "module",
            "data",
            "terraform",
            "locals",
        ]
        has_keyword = any(re.search(rf"\b{kw}\b", code) for kw in keywords)

        if not has_keyword:
            warnings.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    "No Terraform keywords found",
                    severity=ErrorSeverity.WARNING,
                    suggestion="Add resource, provider, or other Terraform blocks",
                )
            )

        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{'
        resources = re.findall(resource_pattern, code)

        if errors:
            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.FORMAT,
                errors=errors,
                warnings=warnings,
                metadata={"iac_type": "terraform", "resources_found": len(resources)},
            )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SYNTAX,
            errors=[],
            warnings=warnings,
            metadata={"iac_type": "terraform", "resources_found": len(resources)},
        )

    def _validate_yaml(self, code: str) -> ValidationResult:
        errors = []
        warnings = []

        try:
            import yaml

            docs = list(yaml.safe_load_all(code))

            if self.iac_type in ["kubernetes", "k8s"]:
                for doc in docs:
                    if doc and isinstance(doc, dict):
                        if "apiVersion" not in doc:
                            warnings.append(
                                self._create_error(
                                    ValidationStage.SYNTAX,
                                    "Missing 'apiVersion' field",
                                    severity=ErrorSeverity.WARNING,
                                    suggestion="Add apiVersion field for Kubernetes resource",
                                )
                            )
                        if "kind" not in doc:
                            warnings.append(
                                self._create_error(
                                    ValidationStage.SYNTAX,
                                    "Missing 'kind' field",
                                    severity=ErrorSeverity.WARNING,
                                    suggestion="Add kind field to specify resource type",
                                )
                            )

            return ValidationResult(
                valid=True,
                stage_reached=ValidationStage.SYNTAX,
                errors=[],
                warnings=warnings,
                metadata={"iac_type": self.iac_type, "documents": len(docs)},
            )

        except yaml.YAMLError as e:
            line = None
            if hasattr(e, "problem_mark") and e.problem_mark:
                line = e.problem_mark.line + 1

            errors.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    f"YAML parse error: {str(e)}",
                    line=line,
                    suggestion="Fix YAML syntax - check indentation and special characters",
                )
            )

            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.FORMAT,
                errors=errors,
                metadata={"iac_type": self.iac_type},
            )
        except Exception:
            return self._basic_yaml_validation(code)

    def _basic_yaml_validation(self, code: str) -> ValidationResult:
        errors = []
        lines = code.split("\n")

        indent_sizes = set()
        for i, line in enumerate(lines, 1):
            if line.strip() and not line.strip().startswith("#"):
                leading = len(line) - len(line.lstrip())
                if leading > 0:
                    indent_sizes.add(leading)

        for i, line in enumerate(lines, 1):
            if "\t" in line and not line.strip().startswith("#"):
                errors.append(
                    self._create_error(
                        ValidationStage.SYNTAX,
                        "Tab character found (YAML uses spaces)",
                        line=i,
                        suggestion="Replace tabs with spaces",
                    )
                )

        if errors:
            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.FORMAT,
                errors=errors,
                metadata={"iac_type": self.iac_type},
            )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SYNTAX,
            metadata={"iac_type": self.iac_type, "indent_sizes": list(indent_sizes)},
        )

    def _validate_dockerfile(self, code: str) -> ValidationResult:
        errors = []
        warnings = []

        valid_instructions = {
            "FROM",
            "RUN",
            "CMD",
            "LABEL",
            "MAINTAINER",
            "EXPOSE",
            "ENV",
            "ADD",
            "COPY",
            "ENTRYPOINT",
            "VOLUME",
            "USER",
            "WORKDIR",
            "ARG",
            "ONBUILD",
            "STOPSIGNAL",
            "HEALTHCHECK",
            "SHELL",
        }

        lines = code.split("\n")
        has_from = False
        from_before_arg_only = True

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if stripped.endswith("\\"):
                continue

            parts = stripped.split(None, 1)
            if not parts:
                continue

            instruction = parts[0].upper()

            if instruction not in valid_instructions:
                if i > 1 and lines[i - 2].strip().endswith("\\"):
                    continue
                errors.append(
                    self._create_error(
                        ValidationStage.SYNTAX,
                        f"Unknown instruction: {instruction}",
                        line=i,
                        suggestion=f"Use valid instruction: {', '.join(sorted(valid_instructions))}",
                    )
                )

            if instruction == "FROM":
                has_from = True
            elif instruction != "ARG" and not has_from:
                from_before_arg_only = False

        if not has_from:
            errors.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    "Missing FROM instruction",
                    suggestion="Add FROM instruction to specify base image",
                )
            )

        if not from_before_arg_only and not has_from:
            errors.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    "FROM must be first instruction (ARG allowed before)",
                    suggestion="Move FROM instruction to the beginning",
                )
            )

        if errors:
            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.FORMAT,
                errors=errors,
                warnings=warnings,
                metadata={"iac_type": "dockerfile"},
            )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SYNTAX,
            warnings=warnings,
            metadata={"iac_type": "dockerfile", "line_count": len(lines)},
        )

    def _validate_vagrantfile(self, code: str) -> ValidationResult:
        errors = []
        warnings = []

        if "Vagrant.configure" not in code:
            errors.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    "Missing Vagrant.configure block",
                    suggestion='Add Vagrant.configure("2") do |config| ... end',
                )
            )

        if "config.vm" not in code:
            warnings.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    "No VM configuration found",
                    severity=ErrorSeverity.WARNING,
                    suggestion="Add config.vm.box and other VM settings",
                )
            )

        do_count = len(re.findall(r"\bdo\b", code))
        end_count = len(re.findall(r"\bend\b", code))

        if do_count != end_count:
            errors.append(
                self._create_error(
                    ValidationStage.SYNTAX,
                    f"Unbalanced do/end blocks: {do_count} do, {end_count} end",
                    suggestion="Check for missing 'end' keywords",
                )
            )

        if errors:
            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.FORMAT,
                errors=errors,
                warnings=warnings,
                metadata={"iac_type": "vagrant"},
            )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SYNTAX,
            warnings=warnings,
            metadata={"iac_type": "vagrant"},
        )


class SemanticValidator(BaseValidator):
    def __init__(self, iac_type: str):
        self.iac_type = iac_type.lower()

    def validate(self, code: str) -> ValidationResult:
        syntax_validator = SyntaxValidator(self.iac_type)
        syntax_result = syntax_validator.validate(code)

        if not syntax_result.syntax_valid:
            return syntax_result

        if self.iac_type in ["terraform", "hcl", "tf"]:
            return self._validate_terraform_semantics(code, syntax_result)
        elif self.iac_type in ["kubernetes", "k8s"]:
            return self._validate_kubernetes_semantics(code, syntax_result)
        elif self.iac_type in ["dockerfile", "docker"]:
            return self._validate_dockerfile_semantics(code, syntax_result)
        elif self.iac_type in ["ansible"]:
            return self._validate_ansible_semantics(code, syntax_result)

        syntax_result.stage_reached = ValidationStage.SEMANTIC
        return syntax_result

    def _validate_terraform_semantics(
        self, code: str, syntax_result: ValidationResult
    ) -> ValidationResult:
        errors = list(syntax_result.errors)
        warnings = list(syntax_result.warnings)

        if "provider" not in code:
            warnings.append(
                self._create_error(
                    ValidationStage.SEMANTIC,
                    "No provider block found",
                    severity=ErrorSeverity.WARNING,
                    suggestion="Add provider block for cloud provider configuration",
                )
            )

        var_refs = re.findall(r"var\.(\w+)", code)
        var_defs = re.findall(r'variable\s+"(\w+)"', code)

        for ref in set(var_refs):
            if ref not in var_defs:
                warnings.append(
                    self._create_error(
                        ValidationStage.SEMANTIC,
                        f"Variable '{ref}' referenced but not defined",
                        severity=ErrorSeverity.WARNING,
                        suggestion=f'Add variable "{ref}" block or use correct variable name',
                    )
                )

        resource_refs = {}
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
        for match in re.finditer(resource_pattern, code):
            resource_type, resource_name = match.groups()
            full_name = f"{resource_type}.{resource_name}"

            refs = re.findall(rf"{resource_type}\.(\w+)\.", code)
            resource_refs[full_name] = refs

        if errors:
            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.SYNTAX,
                errors=errors,
                warnings=warnings,
                metadata=syntax_result.metadata,
            )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SEMANTIC,
            errors=[],
            warnings=warnings,
            metadata={
                **syntax_result.metadata,
                "resources": list(resource_refs.keys()),
            },
        )

    def _validate_kubernetes_semantics(
        self, code: str, syntax_result: ValidationResult
    ) -> ValidationResult:
        errors = list(syntax_result.errors)
        warnings = list(syntax_result.warnings)

        try:
            import yaml

            docs = list(yaml.safe_load_all(code))

            for doc in docs:
                if not doc or not isinstance(doc, dict):
                    continue

                kind = doc.get("kind", "")
                doc.get("apiVersion", "")
                metadata = doc.get("metadata", {})

                if "name" not in metadata:
                    errors.append(
                        self._create_error(
                            ValidationStage.SEMANTIC,
                            f"Missing metadata.name for {kind}",
                            suggestion="Add name field under metadata",
                        )
                    )

                if kind == "Deployment":
                    spec = doc.get("spec", {})
                    if "selector" not in spec:
                        errors.append(
                            self._create_error(
                                ValidationStage.SEMANTIC,
                                "Deployment missing spec.selector",
                                suggestion="Add selector to match pod template labels",
                            )
                        )
                    if "template" not in spec:
                        errors.append(
                            self._create_error(
                                ValidationStage.SEMANTIC,
                                "Deployment missing spec.template",
                                suggestion="Add template for pod specification",
                            )
                        )

                elif kind == "Service":
                    spec = doc.get("spec", {})
                    if "selector" not in spec:
                        warnings.append(
                            self._create_error(
                                ValidationStage.SEMANTIC,
                                "Service without selector won't route to pods",
                                severity=ErrorSeverity.WARNING,
                                suggestion="Add selector to match target pods",
                            )
                        )
                    if "ports" not in spec:
                        errors.append(
                            self._create_error(
                                ValidationStage.SEMANTIC,
                                "Service missing ports",
                                suggestion="Add ports configuration",
                            )
                        )

        except Exception:
            pass

        if errors:
            return ValidationResult(
                valid=False,
                stage_reached=ValidationStage.SYNTAX,
                errors=errors,
                warnings=warnings,
                metadata=syntax_result.metadata,
            )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SEMANTIC,
            errors=[],
            warnings=warnings,
            metadata=syntax_result.metadata,
        )

    def _validate_dockerfile_semantics(
        self, code: str, syntax_result: ValidationResult
    ) -> ValidationResult:
        warnings = list(syntax_result.warnings)

        if "HEALTHCHECK" not in code:
            warnings.append(
                self._create_error(
                    ValidationStage.SEMANTIC,
                    "No HEALTHCHECK instruction",
                    severity=ErrorSeverity.WARNING,
                    suggestion="Add HEALTHCHECK for container health monitoring",
                )
            )

        if "USER" not in code:
            warnings.append(
                self._create_error(
                    ValidationStage.SEMANTIC,
                    "Running as root (no USER instruction)",
                    severity=ErrorSeverity.WARNING,
                    suggestion="Add USER instruction to run as non-root",
                )
            )

        if "ADD" in code and "http" not in code.lower() and ".tar" not in code.lower():
            warnings.append(
                self._create_error(
                    ValidationStage.SEMANTIC,
                    "Using ADD instead of COPY for local files",
                    severity=ErrorSeverity.INFO,
                    suggestion="Use COPY for local files, ADD for URLs/archives",
                )
            )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SEMANTIC,
            errors=[],
            warnings=warnings,
            metadata=syntax_result.metadata,
        )

    def _validate_ansible_semantics(
        self, code: str, syntax_result: ValidationResult
    ) -> ValidationResult:
        warnings = list(syntax_result.warnings)

        try:
            import yaml

            docs = list(yaml.safe_load_all(code))

            for doc in docs:
                if not doc:
                    continue

                if isinstance(doc, list):
                    for play in doc:
                        if isinstance(play, dict):
                            if "hosts" not in play:
                                warnings.append(
                                    self._create_error(
                                        ValidationStage.SEMANTIC,
                                        "Play missing 'hosts' field",
                                        severity=ErrorSeverity.WARNING,
                                        suggestion="Add hosts: field to specify target hosts",
                                    )
                                )
                            if "tasks" not in play and "roles" not in play:
                                warnings.append(
                                    self._create_error(
                                        ValidationStage.SEMANTIC,
                                        "Play has no tasks or roles",
                                        severity=ErrorSeverity.WARNING,
                                        suggestion="Add tasks: or roles: to the play",
                                    )
                                )
        except Exception:
            pass

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.SEMANTIC,
            errors=[],
            warnings=warnings,
            metadata=syntax_result.metadata,
        )


class DeployabilityValidator(BaseValidator):
    def __init__(self, iac_type: str, simulate: bool = True):
        self.iac_type = iac_type.lower()
        self.simulate = simulate

    def validate(self, code: str) -> ValidationResult:
        semantic_validator = SemanticValidator(self.iac_type)
        semantic_result = semantic_validator.validate(code)

        if not semantic_result.semantic_valid:
            return semantic_result

        if self.simulate:
            return self._simulate_deployment(code, semantic_result)
        else:
            return self._real_deployment_check(code, semantic_result)

    def _simulate_deployment(
        self, code: str, semantic_result: ValidationResult
    ) -> ValidationResult:
        warnings = list(semantic_result.warnings)

        deployment_checks = {
            "provider_available": True,
            "quota_check": True,
            "resource_check": True,
            "permission_check": True,
        }

        if self.iac_type in ["terraform", "hcl"]:
            if re.search(r'(access_key|secret_key|password)\s*=\s*"[^"]{10,}"', code):
                warnings.append(
                    self._create_error(
                        ValidationStage.DEPLOYMENT,
                        "Possible hardcoded credentials detected",
                        severity=ErrorSeverity.WARNING,
                        suggestion="Use variables or environment variables for sensitive data",
                    )
                )

        return ValidationResult(
            valid=True,
            stage_reached=ValidationStage.DEPLOYMENT,
            errors=[],
            warnings=warnings,
            metadata={
                **semantic_result.metadata,
                "deployment_checks": deployment_checks,
                "simulated": True,
            },
        )

    def _real_deployment_check(
        self, code: str, semantic_result: ValidationResult
    ) -> ValidationResult:
        return self._simulate_deployment(code, semantic_result)


def validate_iac(
    code: str, iac_type: str, full_validation: bool = True
) -> ValidationResult:
    if full_validation:
        validator = DeployabilityValidator(iac_type)
    else:
        validator = SemanticValidator(iac_type)

    return validator.validate(code)
