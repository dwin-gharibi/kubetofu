import logging
import re
from typing import Any, Dict, List, Optional

from agents.core.base import (
    AgentConfig,
    BaseAgent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


SECURITY_RULES = [
    {
        "id": "SEC001",
        "name": "Public SSH Access",
        "severity": "HIGH",
        "pattern": r"0\.0\.0\.0/0.*22",
        "message": "SSH port 22 is open to the internet (0.0.0.0/0)",
        "recommendation": "Restrict SSH access to specific IP ranges or use a bastion host",
    },
    {
        "id": "SEC002",
        "name": "Public Database Access",
        "severity": "CRITICAL",
        "pattern": r"0\.0\.0\.0/0.*(3306|5432|27017|6379)",
        "message": "Database port is open to the internet",
        "recommendation": "Place databases in private subnets with no public access",
    },
    {
        "id": "SEC003",
        "name": "Unencrypted Storage",
        "severity": "MEDIUM",
        "pattern": r"encrypted\s*=\s*false",
        "message": "Storage volume is not encrypted",
        "recommendation": "Enable encryption for all storage volumes",
    },
    {
        "id": "SEC004",
        "name": "Hardcoded Secrets",
        "severity": "CRITICAL",
        "pattern": r"(password|secret|api_key|token)\s*=\s*\"[^\"]+\"",
        "message": "Hardcoded secrets found in configuration",
        "recommendation": "Use environment variables or a secrets manager",
    },
    {
        "id": "SEC005",
        "name": "Missing Security Group",
        "severity": "HIGH",
        "pattern": r"security_groups\s*=\s*\[\s*\]",
        "message": "Resource has no security groups assigned",
        "recommendation": "Apply appropriate security groups to all resources",
    },
    {
        "id": "SEC006",
        "name": "Privileged Container",
        "severity": "HIGH",
        "pattern": r"privileged\s*=\s*true",
        "message": "Container is running in privileged mode",
        "recommendation": "Avoid privileged containers unless absolutely necessary",
    },
    {
        "id": "SEC007",
        "name": "Root User Container",
        "severity": "MEDIUM",
        "pattern": r"run_as_user\s*=\s*0",
        "message": "Container is running as root user",
        "recommendation": "Run containers as non-root users",
    },
    {
        "id": "SEC008",
        "name": "Missing Network Policy",
        "severity": "MEDIUM",
        "pattern": r"kind:\s*Deployment(?!.*NetworkPolicy)",
        "message": "Kubernetes deployment without network policy",
        "recommendation": "Define network policies to restrict pod-to-pod communication",
    },
]


class ScanConfigurationTool(Tool):
    name = "scan_configuration"
    description = "Scan infrastructure configuration for security vulnerabilities"

    async def execute(self, configuration: str, **kwargs) -> ToolResult:
        findings = []

        for rule in SECURITY_RULES:
            if re.search(rule["pattern"], configuration, re.IGNORECASE | re.DOTALL):
                findings.append(
                    {
                        "rule_id": rule["id"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "recommendation": rule["recommendation"],
                    }
                )

        severity_scores = {"CRITICAL": 30, "HIGH": 20, "MEDIUM": 10, "LOW": 5}
        total_penalty = sum(severity_scores.get(f["severity"], 0) for f in findings)
        security_score = max(0, 100 - total_penalty)

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "findings": findings,
                "total_findings": len(findings),
                "security_score": security_score,
                "passed": len(findings) == 0,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Infrastructure configuration to scan",
                },
            },
            "required": ["configuration"],
        }


class CheckComplianceTool(Tool):
    name = "check_compliance"
    description = (
        "Check infrastructure compliance with security standards (CIS, SOC2, etc.)"
    )

    COMPLIANCE_CHECKS = {
        "CIS": [
            {
                "id": "CIS-1.1",
                "name": "Ensure MFA is enabled",
                "check": lambda c: "mfa" in c.lower(),
            },
            {
                "id": "CIS-1.2",
                "name": "Ensure password policy",
                "check": lambda c: "password_policy" in c.lower(),
            },
            {
                "id": "CIS-2.1",
                "name": "Ensure encryption at rest",
                "check": lambda c: "encrypted" in c.lower(),
            },
            {
                "id": "CIS-3.1",
                "name": "Ensure logging is enabled",
                "check": lambda c: "logging" in c.lower(),
            },
        ],
        "SOC2": [
            {
                "id": "SOC2-CC6.1",
                "name": "Logical access controls",
                "check": lambda c: "security_group" in c.lower(),
            },
            {
                "id": "SOC2-CC6.6",
                "name": "Encryption in transit",
                "check": lambda c: "https" in c.lower() or "tls" in c.lower(),
            },
            {
                "id": "SOC2-CC7.2",
                "name": "Monitoring",
                "check": lambda c: "monitoring" in c.lower(),
            },
        ],
    }

    async def execute(
        self,
        configuration: str,
        standards: List[str] = None,
        **kwargs,
    ) -> ToolResult:
        standards = standards or ["CIS"]
        results = {}

        for standard in standards:
            checks = self.COMPLIANCE_CHECKS.get(standard, [])
            standard_results = []

            for check in checks:
                passed = check["check"](configuration)
                standard_results.append(
                    {
                        "id": check["id"],
                        "name": check["name"],
                        "passed": passed,
                        "status": "PASS" if passed else "FAIL",
                    }
                )

            passed_count = sum(1 for r in standard_results if r["passed"])
            results[standard] = {
                "checks": standard_results,
                "passed": passed_count,
                "failed": len(standard_results) - passed_count,
                "compliance_percentage": (passed_count / len(standard_results) * 100)
                if standard_results
                else 100,
            }

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=results,
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Infrastructure configuration to check",
                },
                "standards": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Compliance standards to check (CIS, SOC2, etc.)",
                },
            },
            "required": ["configuration"],
        }


class AnalyzeNetworkTool(Tool):
    name = "analyze_network"
    description = "Analyze network configuration for security issues"

    async def execute(self, configuration: str, **kwargs) -> ToolResult:
        analysis = {
            "public_exposure": [],
            "internal_segmentation": [],
            "recommendations": [],
        }

        if re.search(r"public_ip|floating_ip|eip", configuration, re.IGNORECASE):
            analysis["public_exposure"].append(
                {
                    "finding": "Resources with public IPs detected",
                    "risk": "MEDIUM",
                }
            )

        if "0.0.0.0/0" in configuration:
            analysis["public_exposure"].append(
                {
                    "finding": "Wide-open CIDR (0.0.0.0/0) detected",
                    "risk": "HIGH",
                }
            )
            analysis["recommendations"].append(
                "Restrict CIDR blocks to specific IP ranges"
            )

        if not re.search(r"subnet|vpc|network", configuration, re.IGNORECASE):
            analysis["internal_segmentation"].append(
                {
                    "finding": "No network segmentation detected",
                    "risk": "MEDIUM",
                }
            )
            analysis["recommendations"].append(
                "Implement network segmentation with private subnets"
            )

        if not re.search(r"security_group|firewall", configuration, re.IGNORECASE):
            analysis["recommendations"].append(
                "Add security groups/firewall rules to control traffic"
            )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=analysis,
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Network configuration to analyze",
                },
            },
            "required": ["configuration"],
        }


class GenerateSecurityReportTool(Tool):
    name = "generate_security_report"
    description = "Generate a comprehensive security report for infrastructure"

    async def execute(
        self,
        scan_results: Dict[str, Any],
        compliance_results: Dict[str, Any] = None,
        network_analysis: Dict[str, Any] = None,
        **kwargs,
    ) -> ToolResult:
        report = {
            "summary": {
                "security_score": scan_results.get("security_score", 0),
                "total_findings": scan_results.get("total_findings", 0),
                "critical_findings": 0,
                "high_findings": 0,
                "medium_findings": 0,
                "low_findings": 0,
            },
            "findings": scan_results.get("findings", []),
            "compliance": compliance_results or {},
            "network": network_analysis or {},
            "recommendations": [],
        }

        for finding in report["findings"]:
            severity = finding.get("severity", "").lower()
            key = f"{severity}_findings"
            if key in report["summary"]:
                report["summary"][key] += 1

        for finding in report["findings"]:
            if finding.get("recommendation"):
                report["recommendations"].append(
                    {
                        "priority": finding.get("severity"),
                        "action": finding.get("recommendation"),
                        "related_finding": finding.get("rule_id"),
                    }
                )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=report,
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "scan_results": {
                    "type": "object",
                    "description": "Results from security scan",
                },
                "compliance_results": {
                    "type": "object",
                    "description": "Results from compliance check",
                },
                "network_analysis": {
                    "type": "object",
                    "description": "Results from network analysis",
                },
            },
            "required": ["scan_results"],
        }


class SecurityAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        default_config = AgentConfig(
            name="SecurityAgent",
            description="Infrastructure security scanning and compliance agent",
            temperature=0.1,
            max_iterations=10,
            tools=[
                "scan_configuration",
                "check_compliance",
                "analyze_network",
                "generate_security_report",
            ],
        )
        super().__init__(config or default_config, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are an expert Security Agent for Kube-Tofu.

Your role is to:
1. Scan infrastructure configurations for security vulnerabilities
2. Check compliance with security standards (CIS, SOC2, HIPAA, PCI-DSS)
3. Analyze network configurations for security issues
4. Identify hardcoded secrets and credentials
5. Suggest security hardening measures
6. Generate comprehensive security reports

Security best practices you enforce:
- Principle of least privilege
- Defense in depth
- Encryption at rest and in transit
- Network segmentation
- Regular security patching
- Logging and monitoring
- Secure secrets management

When analyzing infrastructure:
- Always check for public exposure of sensitive services
- Verify encryption is enabled for storage and transit
- Ensure proper IAM policies and RBAC
- Check for overly permissive security groups
- Validate container security configurations
- Review Kubernetes security contexts

Be thorough but prioritize findings by severity:
- CRITICAL: Immediate action required
- HIGH: Fix before deployment
- MEDIUM: Fix within sprint
- LOW: Address when convenient

Always provide actionable recommendations for each finding."""

    def _register_default_tools(self) -> None:
        self.tool_registry.register(ScanConfigurationTool())
        self.tool_registry.register(CheckComplianceTool())
        self.tool_registry.register(AnalyzeNetworkTool())
        self.tool_registry.register(GenerateSecurityReportTool())

    async def process_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return await self.run(task, context)

    async def scan(self, configuration: str) -> Dict[str, Any]:
        task = f"""Perform a comprehensive security scan on this infrastructure configuration:

{configuration}

Please:
1. Scan for security vulnerabilities
2. Check compliance with CIS and SOC2 standards
3. Analyze network security
4. Generate a security report with recommendations
"""
        return await self.run(task)

    async def check_compliance(
        self,
        configuration: str,
        standards: List[str],
    ) -> Dict[str, Any]:
        task = f"""Check this infrastructure configuration for compliance with {", ".join(standards)}:

{configuration}
"""
        return await self.run(task)
