import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityCategory(Enum):
    CVE = "cve"
    MISCONFIGURATION = "misconfiguration"
    SECRET_EXPOSURE = "secret_exposure"
    INSECURE_DEFAULT = "insecure_default"
    COMPLIANCE = "compliance"
    BEST_PRACTICE = "best_practice"


class ComplianceFramework(Enum):
    CIS = "cis"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    NIST = "nist"


@dataclass
class CVEEntry:
    cve_id: str
    description: str
    severity: Severity
    cvss_score: float
    affected_products: List[str]
    affected_versions: List[str]
    fix_version: Optional[str] = None
    published_date: Optional[str] = None
    references: List[str] = field(default_factory=list)


@dataclass
class SecurityVulnerability:
    id: str
    title: str
    description: str
    severity: Severity
    category: VulnerabilityCategory
    line_number: Optional[int] = None
    file_path: Optional[str] = None
    code_snippet: Optional[str] = None
    remediation: Optional[str] = None
    cve_id: Optional[str] = None
    compliance_frameworks: List[ComplianceFramework] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityScanResult:
    total_vulnerabilities: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    vulnerabilities: List[SecurityVulnerability]
    compliance_status: Dict[str, bool]
    scan_time_ms: float
    secrets_found: int
    misconfigurations_found: int


class CVEDatabase:
    def __init__(self):
        self.cves = self._load_cve_database()

    def _load_cve_database(self) -> Dict[str, CVEEntry]:
        cves = {}

        cves["CVE-2023-48795"] = CVEEntry(
            cve_id="CVE-2023-48795",
            description="SSH Protocol vulnerability in Terraform SSH provisioner",
            severity=Severity.HIGH,
            cvss_score=5.9,
            affected_products=["terraform"],
            affected_versions=["<1.7.0"],
            fix_version="1.7.0",
            published_date="2023-12-18",
        )

        cves["CVE-2022-40674"] = CVEEntry(
            cve_id="CVE-2022-40674",
            description="Expat XML Parser vulnerability affecting Terraform",
            severity=Severity.CRITICAL,
            cvss_score=9.8,
            affected_products=["terraform", "expat"],
            affected_versions=["<2.4.9"],
            fix_version="2.4.9",
            published_date="2022-09-16",
        )

        cves["CVE-2024-21626"] = CVEEntry(
            cve_id="CVE-2024-21626",
            description="Container escape via runc container working directory",
            severity=Severity.CRITICAL,
            cvss_score=8.6,
            affected_products=["kubernetes", "runc", "docker"],
            affected_versions=["runc<1.1.12"],
            fix_version="1.1.12",
            published_date="2024-01-31",
        )

        cves["CVE-2023-5528"] = CVEEntry(
            cve_id="CVE-2023-5528",
            description="Kubernetes Windows nodes command injection",
            severity=Severity.HIGH,
            cvss_score=7.2,
            affected_products=["kubernetes"],
            affected_versions=["<1.28.4"],
            fix_version="1.28.4",
            published_date="2023-11-14",
        )

        cves["CVE-2023-2728"] = CVEEntry(
            cve_id="CVE-2023-2728",
            description="ServiceAccount token audience validation bypass",
            severity=Severity.HIGH,
            cvss_score=6.5,
            affected_products=["kubernetes"],
            affected_versions=["<1.27.3"],
            fix_version="1.27.3",
            published_date="2023-06-15",
        )

        cves["CVE-2024-24557"] = CVEEntry(
            cve_id="CVE-2024-24557",
            description="Docker Moby image build cache poison",
            severity=Severity.MEDIUM,
            cvss_score=6.9,
            affected_products=["docker"],
            affected_versions=["<25.0.2"],
            fix_version="25.0.2",
            published_date="2024-02-01",
        )

        cves["CVE-2023-28840"] = CVEEntry(
            cve_id="CVE-2023-28840",
            description="Docker Swarm encrypted overlay network attacks",
            severity=Severity.HIGH,
            cvss_score=7.5,
            affected_products=["docker"],
            affected_versions=["<24.0.0"],
            fix_version="24.0.0",
            published_date="2023-04-04",
        )

        cves["CVE-2022-36049"] = CVEEntry(
            cve_id="CVE-2022-36049",
            description="Helm allows Denial of Service via large schema files",
            severity=Severity.MEDIUM,
            cvss_score=6.5,
            affected_products=["helm"],
            affected_versions=["<3.10.3"],
            fix_version="3.10.3",
            published_date="2022-09-07",
        )

        cves["CVE-2023-29022"] = CVEEntry(
            cve_id="CVE-2023-29022",
            description="AWS VPC security group misconfiguration",
            severity=Severity.MEDIUM,
            cvss_score=5.3,
            affected_products=["aws", "terraform-aws"],
            affected_versions=["<5.0.0"],
            fix_version="5.0.0",
            published_date="2023-04-15",
        )

        return cves

    def lookup_cve(self, cve_id: str) -> Optional[CVEEntry]:
        return self.cves.get(cve_id)

    def search_by_product(self, product: str) -> List[CVEEntry]:
        results = []
        product_lower = product.lower()
        for cve in self.cves.values():
            if any(product_lower in p.lower() for p in cve.affected_products):
                results.append(cve)
        return results

    def search_by_severity(self, severity: Severity) -> List[CVEEntry]:
        return [cve for cve in self.cves.values() if cve.severity == severity]


class SecurityRule:
    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        severity: Severity,
        category: VulnerabilityCategory,
        remediation: str,
        compliance: List[ComplianceFramework] = None,
    ):
        self.id = id
        self.title = title
        self.description = description
        self.severity = severity
        self.category = category
        self.remediation = remediation
        self.compliance = compliance or []

    def check(self, code: str, iac_type: str) -> List[SecurityVulnerability]:
        raise NotImplementedError


class PatternRule(SecurityRule):
    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        severity: Severity,
        category: VulnerabilityCategory,
        remediation: str,
        patterns: List[str],
        iac_types: List[str] = None,
        compliance: List[ComplianceFramework] = None,
    ):
        super().__init__(
            id, title, description, severity, category, remediation, compliance
        )
        self.patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
        self.iac_types = iac_types or []

    def check(self, code: str, iac_type: str) -> List[SecurityVulnerability]:
        if self.iac_types and iac_type not in self.iac_types:
            return []

        vulnerabilities = []

        for pattern in self.patterns:
            matches = pattern.finditer(code)
            for match in matches:
                line_number = code[: match.start()].count("\n") + 1

                lines = code.split("\n")
                start_line = max(0, line_number - 2)
                end_line = min(len(lines), line_number + 2)
                snippet = "\n".join(lines[start_line:end_line])

                vulnerabilities.append(
                    SecurityVulnerability(
                        id=f"{self.id}-{line_number}",
                        title=self.title,
                        description=self.description,
                        severity=self.severity,
                        category=self.category,
                        line_number=line_number,
                        code_snippet=snippet,
                        remediation=self.remediation,
                        compliance_frameworks=self.compliance,
                    )
                )

        return vulnerabilities


class SecurityScanner:
    def __init__(self):
        self.cve_db = CVEDatabase()
        self.rules = self._load_rules()

    def _load_rules(self) -> List[SecurityRule]:
        rules = []

        rules.extend(
            [
                PatternRule(
                    id="SEC001",
                    title="Hardcoded AWS Access Key",
                    description="AWS access key found hardcoded in configuration",
                    severity=Severity.CRITICAL,
                    category=VulnerabilityCategory.SECRET_EXPOSURE,
                    remediation="Use environment variables or AWS IAM roles instead of hardcoded credentials",
                    patterns=[
                        r"AKIA[0-9A-Z]{16}",
                        r'aws_access_key_id\s*=\s*["\'][A-Z0-9]{20}["\']',
                    ],
                    compliance=[ComplianceFramework.SOC2, ComplianceFramework.PCI_DSS],
                ),
                PatternRule(
                    id="SEC002",
                    title="Hardcoded AWS Secret Key",
                    description="AWS secret key found hardcoded in configuration",
                    severity=Severity.CRITICAL,
                    category=VulnerabilityCategory.SECRET_EXPOSURE,
                    remediation="Use environment variables or secrets manager",
                    patterns=[
                        r'aws_secret_access_key\s*=\s*["\'][A-Za-z0-9/+=]{40}["\']',
                    ],
                    compliance=[ComplianceFramework.SOC2, ComplianceFramework.PCI_DSS],
                ),
                PatternRule(
                    id="SEC003",
                    title="Hardcoded Private Key",
                    description="Private key material found in configuration",
                    severity=Severity.CRITICAL,
                    category=VulnerabilityCategory.SECRET_EXPOSURE,
                    remediation="Use secure key management like HashiCorp Vault",
                    patterns=[
                        r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----",
                        r"-----BEGIN OPENSSH PRIVATE KEY-----",
                    ],
                    compliance=[ComplianceFramework.SOC2, ComplianceFramework.HIPAA],
                ),
                PatternRule(
                    id="SEC004",
                    title="Hardcoded Password",
                    description="Password appears to be hardcoded",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.SECRET_EXPOSURE,
                    remediation="Use secrets manager or environment variables",
                    patterns=[
                        r'password\s*=\s*["\'][^"\']{8,}["\']',
                        r'db_password\s*=\s*["\'][^"\']+["\']',
                        r'admin_password\s*=\s*["\'][^"\']+["\']',
                    ],
                    compliance=[ComplianceFramework.SOC2, ComplianceFramework.PCI_DSS],
                ),
                PatternRule(
                    id="SEC005",
                    title="API Key Exposure",
                    description="API key appears to be hardcoded",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.SECRET_EXPOSURE,
                    remediation="Use environment variables or secrets manager",
                    patterns=[
                        r'api_key\s*=\s*["\'][a-zA-Z0-9_-]{20,}["\']',
                        r'apikey\s*=\s*["\'][a-zA-Z0-9_-]{20,}["\']',
                    ],
                    compliance=[ComplianceFramework.SOC2],
                ),
            ]
        )

        rules.extend(
            [
                PatternRule(
                    id="TF001",
                    title="Security Group Open to World",
                    description="Security group allows unrestricted access (0.0.0.0/0)",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Restrict CIDR blocks to specific IP ranges",
                    patterns=[
                        r'cidr_blocks\s*=\s*\[\s*["\']0\.0\.0\.0/0["\']\s*\]',
                    ],
                    iac_types=["terraform", "hcl"],
                    compliance=[ComplianceFramework.CIS, ComplianceFramework.SOC2],
                ),
                PatternRule(
                    id="TF002",
                    title="S3 Bucket Public Access",
                    description="S3 bucket allows public access",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Set acl = 'private' and block public access",
                    patterns=[
                        r'acl\s*=\s*["\']public-read["\']',
                        r'acl\s*=\s*["\']public-read-write["\']',
                    ],
                    iac_types=["terraform", "hcl"],
                    compliance=[ComplianceFramework.CIS, ComplianceFramework.SOC2],
                ),
                PatternRule(
                    id="TF003",
                    title="Unencrypted S3 Bucket",
                    description="S3 bucket lacks server-side encryption",
                    severity=Severity.MEDIUM,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Enable SSE-S3 or SSE-KMS encryption",
                    patterns=[
                        r'resource\s+"aws_s3_bucket"\s+"[^"]+"\s*\{(?:(?!server_side_encryption).)*\}',
                    ],
                    iac_types=["terraform", "hcl"],
                    compliance=[ComplianceFramework.CIS, ComplianceFramework.HIPAA],
                ),
                PatternRule(
                    id="TF004",
                    title="RDS Public Accessibility",
                    description="RDS instance is publicly accessible",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Set publicly_accessible = false",
                    patterns=[
                        r"publicly_accessible\s*=\s*true",
                    ],
                    iac_types=["terraform", "hcl"],
                    compliance=[ComplianceFramework.CIS, ComplianceFramework.SOC2],
                ),
                PatternRule(
                    id="TF005",
                    title="Unencrypted EBS Volume",
                    description="EBS volume is not encrypted",
                    severity=Severity.MEDIUM,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Set encrypted = true on EBS volumes",
                    patterns=[
                        r"encrypted\s*=\s*false",
                    ],
                    iac_types=["terraform", "hcl"],
                    compliance=[ComplianceFramework.CIS, ComplianceFramework.HIPAA],
                ),
            ]
        )

        rules.extend(
            [
                PatternRule(
                    id="K8S001",
                    title="Container Running as Root",
                    description="Container is running as root user",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Set securityContext.runAsNonRoot = true",
                    patterns=[
                        r"runAsUser:\s*0",
                    ],
                    iac_types=["kubernetes", "yaml", "helm"],
                    compliance=[ComplianceFramework.CIS],
                ),
                PatternRule(
                    id="K8S002",
                    title="Privileged Container",
                    description="Container runs in privileged mode",
                    severity=Severity.CRITICAL,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Set securityContext.privileged = false",
                    patterns=[
                        r"privileged:\s*true",
                    ],
                    iac_types=["kubernetes", "yaml", "helm"],
                    compliance=[ComplianceFramework.CIS],
                ),
                PatternRule(
                    id="K8S003",
                    title="Hostpath Volume Mount",
                    description="Pod mounts a hostPath volume",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Use PersistentVolumes or ConfigMaps instead",
                    patterns=[
                        r"hostPath:",
                    ],
                    iac_types=["kubernetes", "yaml", "helm"],
                    compliance=[ComplianceFramework.CIS],
                ),
                PatternRule(
                    id="K8S004",
                    title="Host Network Mode",
                    description="Pod uses host network namespace",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Set hostNetwork = false unless absolutely required",
                    patterns=[
                        r"hostNetwork:\s*true",
                    ],
                    iac_types=["kubernetes", "yaml", "helm"],
                    compliance=[ComplianceFramework.CIS],
                ),
                PatternRule(
                    id="K8S005",
                    title="Missing Resource Limits",
                    description="Container lacks resource limits",
                    severity=Severity.MEDIUM,
                    category=VulnerabilityCategory.BEST_PRACTICE,
                    remediation="Define resources.limits for CPU and memory",
                    patterns=[
                        r"containers:(?:(?!resources:).)*$",
                    ],
                    iac_types=["kubernetes", "yaml", "helm"],
                    compliance=[ComplianceFramework.CIS],
                ),
                PatternRule(
                    id="K8S006",
                    title="Default Namespace Usage",
                    description="Resources deployed to default namespace",
                    severity=Severity.LOW,
                    category=VulnerabilityCategory.BEST_PRACTICE,
                    remediation="Use dedicated namespaces for workloads",
                    patterns=[
                        r"namespace:\s*default",
                    ],
                    iac_types=["kubernetes", "yaml", "helm"],
                ),
            ]
        )

        rules.extend(
            [
                PatternRule(
                    id="DOC001",
                    title="Running as Root in Dockerfile",
                    description="Dockerfile does not specify non-root user",
                    severity=Severity.MEDIUM,
                    category=VulnerabilityCategory.MISCONFIGURATION,
                    remediation="Add USER directive to run as non-root",
                    patterns=[
                        r"^(?!.*USER).*CMD",
                    ],
                    iac_types=["dockerfile"],
                ),
                PatternRule(
                    id="DOC002",
                    title="Latest Tag Usage",
                    description="Using :latest tag is not recommended",
                    severity=Severity.LOW,
                    category=VulnerabilityCategory.BEST_PRACTICE,
                    remediation="Pin specific image versions for reproducibility",
                    patterns=[
                        r"FROM\s+\S+:latest",
                    ],
                    iac_types=["dockerfile"],
                ),
                PatternRule(
                    id="DOC003",
                    title="COPY with Wildcard",
                    description="COPY with * may include unintended files",
                    severity=Severity.LOW,
                    category=VulnerabilityCategory.BEST_PRACTICE,
                    remediation="Be explicit about files to copy",
                    patterns=[
                        r"COPY\s+\.\s+",
                        r"ADD\s+\.\s+",
                    ],
                    iac_types=["dockerfile"],
                ),
                PatternRule(
                    id="DOC004",
                    title="Secrets in ENV",
                    description="Sensitive data in ENV instruction",
                    severity=Severity.HIGH,
                    category=VulnerabilityCategory.SECRET_EXPOSURE,
                    remediation="Use build args or runtime secrets instead",
                    patterns=[
                        r"ENV\s+.*(?:PASSWORD|SECRET|API_KEY|TOKEN)=",
                    ],
                    iac_types=["dockerfile"],
                    compliance=[ComplianceFramework.SOC2],
                ),
            ]
        )

        return rules

    def scan(
        self,
        code: str,
        iac_type: str,
        file_path: Optional[str] = None,
    ) -> SecurityScanResult:
        import time

        start_time = time.time()

        vulnerabilities = []

        for rule in self.rules:
            try:
                found = rule.check(code, iac_type)
                for vuln in found:
                    vuln.file_path = file_path
                vulnerabilities.extend(found)
            except Exception:
                pass

        cve_vulns = self._check_cves(code, iac_type)
        vulnerabilities.extend(cve_vulns)

        critical = sum(1 for v in vulnerabilities if v.severity == Severity.CRITICAL)
        high = sum(1 for v in vulnerabilities if v.severity == Severity.HIGH)
        medium = sum(1 for v in vulnerabilities if v.severity == Severity.MEDIUM)
        low = sum(1 for v in vulnerabilities if v.severity == Severity.LOW)
        info = sum(1 for v in vulnerabilities if v.severity == Severity.INFO)

        secrets = sum(
            1
            for v in vulnerabilities
            if v.category == VulnerabilityCategory.SECRET_EXPOSURE
        )
        misconfigs = sum(
            1
            for v in vulnerabilities
            if v.category == VulnerabilityCategory.MISCONFIGURATION
        )

        compliance_status = self._check_compliance(vulnerabilities)

        scan_time = (time.time() - start_time) * 1000

        return SecurityScanResult(
            total_vulnerabilities=len(vulnerabilities),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            info_count=info,
            vulnerabilities=vulnerabilities,
            compliance_status=compliance_status,
            scan_time_ms=scan_time,
            secrets_found=secrets,
            misconfigurations_found=misconfigs,
        )

    def _check_cves(self, code: str, iac_type: str) -> List[SecurityVulnerability]:
        vulnerabilities = []
        code.lower()

        version_patterns = [
            (r'terraform.*required_version.*["\']([^"\']+)["\']', "terraform"),
            (r'version.*=.*["\'](\d+\.\d+\.\d+)["\']', "general"),
            (r"image:\s*\S+:(\S+)", "docker"),
        ]

        for pattern, product in version_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                match.group(1)
                for cve in self.cve_db.search_by_product(product):
                    vulnerabilities.append(
                        SecurityVulnerability(
                            id=f"CVE-CHECK-{cve.cve_id}",
                            title=f"Potential CVE: {cve.cve_id}",
                            description=cve.description,
                            severity=cve.severity,
                            category=VulnerabilityCategory.CVE,
                            cve_id=cve.cve_id,
                            remediation=f"Update to version {cve.fix_version} or later"
                            if cve.fix_version
                            else "Check for updates",
                        )
                    )

        return vulnerabilities

    def _check_compliance(
        self,
        vulnerabilities: List[SecurityVulnerability],
    ) -> Dict[str, bool]:
        frameworks = {}

        for framework in ComplianceFramework:
            blocking_vulns = [
                v
                for v in vulnerabilities
                if framework in v.compliance_frameworks
                and v.severity in [Severity.CRITICAL, Severity.HIGH]
            ]
            frameworks[framework.value] = len(blocking_vulns) == 0

        return frameworks

    def generate_report(
        self,
        result: SecurityScanResult,
        format: str = "text",
    ) -> str:
        if format == "json":
            return json.dumps(
                {
                    "summary": {
                        "total": result.total_vulnerabilities,
                        "critical": result.critical_count,
                        "high": result.high_count,
                        "medium": result.medium_count,
                        "low": result.low_count,
                        "secrets_found": result.secrets_found,
                        "misconfigurations": result.misconfigurations_found,
                    },
                    "compliance": result.compliance_status,
                    "vulnerabilities": [
                        {
                            "id": v.id,
                            "title": v.title,
                            "severity": v.severity.value,
                            "category": v.category.value,
                            "line": v.line_number,
                            "cve_id": v.cve_id,
                            "remediation": v.remediation,
                        }
                        for v in result.vulnerabilities
                    ],
                },
                indent=2,
            )

        lines = []
        lines.append("=" * 60)
        lines.append("SECURITY SCAN REPORT")
        lines.append("=" * 60)
        lines.append(f"Total Vulnerabilities: {result.total_vulnerabilities}")
        lines.append(f"  Critical: {result.critical_count}")
        lines.append(f"  High: {result.high_count}")
        lines.append(f"  Medium: {result.medium_count}")
        lines.append(f"  Low: {result.low_count}")
        lines.append(f"  Info: {result.info_count}")
        lines.append(f"Secrets Found: {result.secrets_found}")
        lines.append(f"Misconfigurations: {result.misconfigurations_found}")
        lines.append(f"Scan Time: {result.scan_time_ms:.1f}ms")
        lines.append("")
        lines.append("COMPLIANCE STATUS:")
        for framework, compliant in result.compliance_status.items():
            status = "✅ PASS" if compliant else "❌ FAIL"
            lines.append(f"  {framework.upper()}: {status}")
        lines.append("")
        lines.append("VULNERABILITIES:")
        lines.append("-" * 60)

        for vuln in sorted(result.vulnerabilities, key=lambda v: v.severity.value):
            lines.append(f"[{vuln.severity.value.upper()}] {vuln.title}")
            lines.append(f"  ID: {vuln.id}")
            if vuln.cve_id:
                lines.append(f"  CVE: {vuln.cve_id}")
            if vuln.line_number:
                lines.append(f"  Line: {vuln.line_number}")
            lines.append(f"  {vuln.description}")
            if vuln.remediation:
                lines.append(f"  Fix: {vuln.remediation}")
            lines.append("")

        return "\n".join(lines)


def run_security_scan(
    code: str, iac_type: str = "terraform", verbose: bool = True
) -> SecurityScanResult:
    scanner = SecurityScanner()
    result = scanner.scan(code, iac_type)

    if verbose:
        report = scanner.generate_report(result)
        print(report)

    return result


def run_cve_detection_tests(verbose: bool = True) -> Dict[str, Any]:
    scanner = SecurityScanner()

    test_cases = [
        {
            "name": "AWS Credentials Exposure",
            "code": """
provider "aws" {
  access_key = "AKIAIOSFODNN7EXAMPLE"
  secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  region     = "us-west-2"
}
""",
            "iac_type": "terraform",
            "expected_critical": 2,
        },
        {
            "name": "Open Security Group",
            "code": """
resource "aws_security_group" "allow_all" {
  name = "allow_all"
  
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
""",
            "iac_type": "terraform",
            "expected_high": 1,
        },
        {
            "name": "Privileged K8s Container",
            "code": """
apiVersion: v1
kind: Pod
metadata:
  name: privileged-pod
spec:
  containers:
  - name: app
    image: nginx
    securityContext:
      privileged: true
      runAsUser: 0
""",
            "iac_type": "kubernetes",
            "expected_critical": 1,
            "expected_high": 1,
        },
        {
            "name": "Dockerfile Secrets",
            "code": """
FROM python:3.11
ENV DATABASE_PASSWORD=secret123
COPY . /app
CMD ["python", "app.py"]
""",
            "iac_type": "dockerfile",
            "expected_high": 1,
        },
    ]

    results = []

    for test in test_cases:
        if verbose:
            print(f"\nTesting: {test['name']}")

        result = scanner.scan(test["code"], test["iac_type"])

        passed = True
        if "expected_critical" in test:
            if result.critical_count < test["expected_critical"]:
                passed = False
        if "expected_high" in test:
            if result.high_count < test["expected_high"]:
                passed = False

        results.append(
            {
                "name": test["name"],
                "passed": passed,
                "critical": result.critical_count,
                "high": result.high_count,
                "total": result.total_vulnerabilities,
            }
        )

        if verbose:
            status = "✅" if passed else "❌"
            print(
                f"  {status} Found {result.total_vulnerabilities} vulnerabilities "
                f"({result.critical_count} critical, {result.high_count} high)"
            )

    summary = {
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "details": results,
    }

    if verbose:
        print("\n" + "=" * 60)
        print("CVE Detection Test Summary")
        print("=" * 60)
        print(f"Tests: {summary['passed']}/{summary['total_tests']} passed")

    return summary


if __name__ == "__main__":
    run_cve_detection_tests()
