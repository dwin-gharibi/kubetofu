import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import httpx

logger = logging.getLogger(__name__)


class TerraformInitInput(BaseModel):
    working_dir: str = Field(description="Working directory containing Terraform files")
    backend_config: Optional[Dict[str, str]] = Field(
        default=None, description="Backend configuration"
    )


class TerraformInitTool(BaseTool):
    name: str = "terraform_init"
    description: str = (
        "Initialize Terraform/OpenTofu in a working directory. Use before plan/apply."
    )
    args_schema: Type[BaseModel] = TerraformInitInput

    def _run(
        self, working_dir: str, backend_config: Optional[Dict[str, str]] = None
    ) -> str:
        cmd = ["tofu", "init", "-input=false", "-no-color"]

        if backend_config:
            for key, value in backend_config.items():
                cmd.extend([f"-backend-config={key}={value}"])

        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return f"Terraform initialized successfully in {working_dir}"
            else:
                return f"Terraform init failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return "Terraform init timed out after 5 minutes"
        except Exception as e:
            return f"Error running terraform init: {e}"


class TerraformPlanInput(BaseModel):
    working_dir: str = Field(description="Working directory")
    variables: Optional[Dict[str, str]] = Field(
        default=None, description="Variables to pass"
    )
    out_file: Optional[str] = Field(default=None, description="File to save the plan")


class TerraformPlanTool(BaseTool):
    name: str = "terraform_plan"
    description: str = "Generate an execution plan showing what changes will be made."
    args_schema: Type[BaseModel] = TerraformPlanInput

    def _run(
        self,
        working_dir: str,
        variables: Optional[Dict[str, str]] = None,
        out_file: Optional[str] = None,
    ) -> str:
        cmd = ["tofu", "plan", "-input=false", "-no-color"]

        if variables:
            for key, value in variables.items():
                cmd.extend(["-var", f"{key}={value}"])

        if out_file:
            cmd.extend(["-out", out_file])

        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )

            output = result.stdout

            add_count = output.count("will be created")
            change_count = output.count("will be updated")
            destroy_count = output.count("will be destroyed")

            summary = f"\nPlan Summary: {add_count} to add, {change_count} to change, {destroy_count} to destroy\n"

            return output + summary
        except subprocess.TimeoutExpired:
            return "Terraform plan timed out after 10 minutes"
        except Exception as e:
            return f"Error running terraform plan: {e}"


class TerraformApplyInput(BaseModel):
    working_dir: str = Field(description="Working directory")
    auto_approve: bool = Field(default=False, description="Skip approval prompt")
    plan_file: Optional[str] = Field(default=None, description="Plan file to apply")


class TerraformApplyTool(BaseTool):
    name: str = "terraform_apply"
    description: str = (
        "Apply infrastructure changes. Use with caution - this creates real resources!"
    )
    args_schema: Type[BaseModel] = TerraformApplyInput

    def _run(
        self,
        working_dir: str,
        auto_approve: bool = False,
        plan_file: Optional[str] = None,
    ) -> str:
        cmd = ["tofu", "apply", "-input=false", "-no-color"]

        if auto_approve:
            cmd.append("-auto-approve")

        if plan_file:
            cmd.append(plan_file)

        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=1800,
            )

            if result.returncode == 0:
                return f"Apply completed successfully!\n\n{result.stdout}"
            else:
                return f"Apply failed:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Terraform apply timed out after 30 minutes"
        except Exception as e:
            return f"Error running terraform apply: {e}"


class TerraformValidateInput(BaseModel):
    working_dir: str = Field(description="Working directory")


class TerraformValidateTool(BaseTool):
    name: str = "terraform_validate"
    description: str = "Validate Terraform configuration files for syntax errors."
    args_schema: Type[BaseModel] = TerraformValidateInput

    def _run(self, working_dir: str) -> str:
        try:
            result = subprocess.run(
                ["tofu", "validate", "-json"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            data = json.loads(result.stdout)

            if data.get("valid"):
                return "Configuration is valid!"
            else:
                errors = []
                for diag in data.get("diagnostics", []):
                    severity = diag.get("severity", "error")
                    summary = diag.get("summary", "")
                    detail = diag.get("detail", "")
                    errors.append(f"[{severity.upper()}] {summary}: {detail}")

                return "Validation failed:\n" + "\n".join(errors)
        except Exception as e:
            return f"Error running terraform validate: {e}"


class KubectlInput(BaseModel):
    command: str = Field(description="kubectl subcommand (get, describe, apply, etc.)")
    resource: Optional[str] = Field(
        default=None, description="Resource type (pods, services, etc.)"
    )
    name: Optional[str] = Field(default=None, description="Resource name")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    flags: Optional[List[str]] = Field(default=None, description="Additional flags")


class KubectlTool(BaseTool):
    name: str = "kubectl"
    description: str = "Execute kubectl commands to manage Kubernetes resources. Supports get, describe, apply, delete, logs, etc."
    args_schema: Type[BaseModel] = KubectlInput

    def _run(
        self,
        command: str,
        resource: Optional[str] = None,
        name: Optional[str] = None,
        namespace: str = "default",
        flags: Optional[List[str]] = None,
    ) -> str:
        cmd = ["kubectl", command]

        if resource:
            cmd.append(resource)

        if name:
            cmd.append(name)

        cmd.extend(["-n", namespace])

        if flags:
            cmd.extend(flags)

        if command in ["get", "describe"] and "-o" not in str(flags):
            if command == "get":
                cmd.extend(["-o", "wide"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return result.stdout or "Command executed successfully"
            else:
                return f"kubectl error: {result.stderr}"
        except Exception as e:
            return f"Error running kubectl: {e}"


class KubernetesAnalyzerInput(BaseModel):
    namespace: str = Field(default="default", description="Namespace to analyze")
    resource_types: Optional[List[str]] = Field(
        default=None,
        description="Resource types to analyze (pods, services, ingress, etc.)",
    )


class KubernetesAnalyzerTool(BaseTool):
    name: str = "kubernetes_analyzer"
    description: str = "Analyze Kubernetes cluster for issues. Scans pods, services, ingress, PVCs, and more for problems."
    args_schema: Type[BaseModel] = KubernetesAnalyzerInput

    def _run(
        self,
        namespace: str = "default",
        resource_types: Optional[List[str]] = None,
    ) -> str:
        resource_types = resource_types or [
            "pods",
            "services",
            "ingress",
            "pvc",
            "deployments",
        ]

        issues = []

        for resource_type in resource_types:
            analyzer = getattr(self, f"_analyze_{resource_type}", None)
            if analyzer:
                resource_issues = analyzer(namespace)
                issues.extend(resource_issues)

        if not issues:
            return f"No issues found in namespace '{namespace}'"

        output = f"## Kubernetes Issues in '{namespace}'\n\n"

        for issue in issues:
            output += f"### {issue['severity']}: {issue['title']}\n"
            output += f"**Resource:** {issue['resource']}\n"
            output += f"**Details:** {issue['details']}\n"
            output += f"**Recommendation:** {issue['recommendation']}\n\n"

        return output

    def _analyze_pods(self, namespace: str) -> List[Dict]:
        issues = []

        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            pods = json.loads(result.stdout)

            for pod in pods.get("items", []):
                name = pod["metadata"]["name"]
                status = pod["status"]

                for cs in status.get("containerStatuses", []):
                    if cs.get("restartCount", 0) > 5:
                        issues.append(
                            {
                                "severity": "HIGH",
                                "title": "Pod in CrashLoopBackOff",
                                "resource": f"pod/{name}",
                                "details": f"Container {cs['name']} has restarted {cs['restartCount']} times",
                                "recommendation": "Check container logs and resource limits",
                            }
                        )

                    state = cs.get("lastState", {}).get("terminated", {})
                    if state.get("reason") == "OOMKilled":
                        issues.append(
                            {
                                "severity": "HIGH",
                                "title": "Container OOMKilled",
                                "resource": f"pod/{name}",
                                "details": f"Container {cs['name']} was killed due to out of memory",
                                "recommendation": "Increase memory limits or optimize application memory usage",
                            }
                        )

                if status.get("phase") == "Pending":
                    conditions = status.get("conditions", [])
                    for cond in conditions:
                        if cond.get("status") == "False":
                            issues.append(
                                {
                                    "severity": "MEDIUM",
                                    "title": "Pod stuck in Pending",
                                    "resource": f"pod/{name}",
                                    "details": cond.get("message", "Unknown reason"),
                                    "recommendation": "Check node resources and scheduling constraints",
                                }
                            )

        except Exception as e:
            logger.error(f"Error analyzing pods: {e}")

        return issues

    def _analyze_services(self, namespace: str) -> List[Dict]:
        issues = []

        try:
            result = subprocess.run(
                ["kubectl", "get", "svc", "-n", namespace, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            services = json.loads(result.stdout)

            for svc in services.get("items", []):
                name = svc["metadata"]["name"]
                spec = svc.get("spec", {})

                selector = spec.get("selector", {})
                if selector:
                    ep_result = subprocess.run(
                        [
                            "kubectl",
                            "get",
                            "endpoints",
                            name,
                            "-n",
                            namespace,
                            "-o",
                            "json",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if ep_result.returncode == 0:
                        endpoints = json.loads(ep_result.stdout)
                        subsets = endpoints.get("subsets", [])

                        if not subsets or not any(s.get("addresses") for s in subsets):
                            issues.append(
                                {
                                    "severity": "MEDIUM",
                                    "title": "Service has no endpoints",
                                    "resource": f"service/{name}",
                                    "details": "No pods match the service selector",
                                    "recommendation": "Check that pods exist and labels match the service selector",
                                }
                            )

        except Exception as e:
            logger.error(f"Error analyzing services: {e}")

        return issues

    def _analyze_ingress(self, namespace: str) -> List[Dict]:
        return []

    def _analyze_pvc(self, namespace: str) -> List[Dict]:
        issues = []

        try:
            result = subprocess.run(
                ["kubectl", "get", "pvc", "-n", namespace, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            pvcs = json.loads(result.stdout)

            for pvc in pvcs.get("items", []):
                name = pvc["metadata"]["name"]
                status = pvc.get("status", {}).get("phase")

                if status == "Pending":
                    issues.append(
                        {
                            "severity": "MEDIUM",
                            "title": "PVC stuck in Pending",
                            "resource": f"pvc/{name}",
                            "details": "Persistent volume claim cannot be bound",
                            "recommendation": "Check storage class availability and capacity",
                        }
                    )

        except Exception as e:
            logger.error(f"Error analyzing PVCs: {e}")

        return issues

    def _analyze_deployments(self, namespace: str) -> List[Dict]:
        issues = []

        try:
            result = subprocess.run(
                ["kubectl", "get", "deployments", "-n", namespace, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            deployments = json.loads(result.stdout)

            for deploy in deployments.get("items", []):
                name = deploy["metadata"]["name"]
                status = deploy.get("status", {})
                spec = deploy.get("spec", {})

                desired = spec.get("replicas", 0)
                available = status.get("availableReplicas", 0)

                if available < desired:
                    issues.append(
                        {
                            "severity": "HIGH",
                            "title": "Deployment not fully available",
                            "resource": f"deployment/{name}",
                            "details": f"Only {available}/{desired} replicas available",
                            "recommendation": "Check pod status and events for errors",
                        }
                    )

        except Exception as e:
            logger.error(f"Error analyzing deployments: {e}")

        return issues


class ArvanCloudPricingInput(BaseModel):
    resource_type: str = Field(
        description="Resource type (flavor, volume, floating_ip)"
    )
    region: str = Field(default="ir-thr-at1", description="ArvanCloud region")


class ArvanCloudPricingTool(BaseTool):
    name: str = "arvancloud_pricing"
    description: str = "Get real-time pricing from ArvanCloud. Fetches actual current prices from the API."
    args_schema: Type[BaseModel] = ArvanCloudPricingInput

    def _run(self, resource_type: str, region: str = "ir-thr-at1") -> str:
        api_key = os.environ.get("ARVAN_API_KEY", "")
        base_url = "https://napi.arvancloud.ir"

        headers = {
            "Authorization": f"Apikey {api_key}",
            "Content-Type": "application/json",
        }

        try:
            if resource_type == "flavor" or resource_type == "flavors":
                url = f"{base_url}/ecc/v1/regions/{region}/sizes"
                response = httpx.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    flavors = data.get("data", [])

                    output = "## ArvanCloud Compute Flavors\n\n"
                    output += "| Flavor ID | vCPUs | RAM (GB) | Price (IRR/hour) |\n"
                    output += "|-----------|-------|----------|------------------|\n"

                    for f in flavors[:15]:
                        output += f"| {f.get('id', 'N/A')} | {f.get('vcpus', 'N/A')} | {f.get('ram', 0) / 1024:.0f} | {f.get('price_per_hour', 'N/A')} |\n"

                    return output
                else:
                    return f"API error: {response.status_code} - {response.text}"

            elif resource_type == "volume" or resource_type == "volumes":
                return """## ArvanCloud Volume Pricing

| Type | Price (IRR/GB/month) |
|------|---------------------|
| SSD  | ~2,000              |
| HDD  | ~1,000              |

Note: Prices are approximate. Contact ArvanCloud for exact current pricing.
"""

            elif resource_type == "floating_ip":
                return """## ArvanCloud Floating IP Pricing

| Resource | Price (IRR/month) |
|----------|-------------------|
| Floating IP | ~50,000        |

Note: Prices are approximate. Contact ArvanCloud for exact current pricing.
"""

            else:
                return f"Unknown resource type: {resource_type}. Try: flavor, volume, floating_ip"

        except Exception as e:
            return f"Error fetching pricing: {e}"


class ArvanCloudResourceInput(BaseModel):
    action: str = Field(description="Action: list, get, create, delete")
    resource_type: str = Field(
        description="Resource type: servers, networks, volumes, etc."
    )
    resource_id: Optional[str] = Field(
        default=None, description="Resource ID for get/delete"
    )
    region: str = Field(default="ir-thr-at1", description="ArvanCloud region")
    params: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional parameters"
    )


class ArvanCloudResourceTool(BaseTool):
    name: str = "arvancloud_resource"
    description: str = "Manage ArvanCloud resources (servers, networks, volumes, etc.)"
    args_schema: Type[BaseModel] = ArvanCloudResourceInput

    ENDPOINTS = {
        "servers": "/ecc/v1/regions/{region}/servers",
        "networks": "/ecc/v1/regions/{region}/networks",
        "subnets": "/ecc/v1/regions/{region}/subnets",
        "volumes": "/ecc/v1/regions/{region}/volumes",
        "floating_ips": "/ecc/v1/regions/{region}/floats",
        "security_groups": "/ecc/v1/regions/{region}/securities",
        "images": "/ecc/v1/regions/{region}/images",
    }

    def _run(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        region: str = "ir-thr-at1",
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        api_key = os.environ.get("ARVAN_API_KEY", "")
        base_url = "https://napi.arvancloud.ir"

        if resource_type not in self.ENDPOINTS:
            return f"Unknown resource type: {resource_type}"

        endpoint = self.ENDPOINTS[resource_type].format(region=region)
        url = f"{base_url}{endpoint}"

        if resource_id:
            url = f"{url}/{resource_id}"

        headers = {
            "Authorization": f"Apikey {api_key}",
            "Content-Type": "application/json",
        }

        try:
            if action == "list":
                response = httpx.get(url, headers=headers, timeout=30)
            elif action == "get":
                response = httpx.get(url, headers=headers, timeout=30)
            elif action == "create":
                response = httpx.post(
                    url, headers=headers, json=params or {}, timeout=60
                )
            elif action == "delete":
                response = httpx.delete(url, headers=headers, timeout=60)
            else:
                return f"Unknown action: {action}"

            if response.status_code in [200, 201]:
                data = response.json()
                return json.dumps(data, indent=2)
            else:
                return f"API error: {response.status_code} - {response.text}"

        except Exception as e:
            return f"Error: {e}"


class GitHubSearchInput(BaseModel):
    query: str = Field(description="Search query")
    search_type: str = Field(
        default="repositories", description="Type: repositories, code, issues"
    )
    limit: int = Field(default=5, description="Max results to return")


class GitHubSearchTool(BaseTool):
    name: str = "github_search"
    description: str = "Search GitHub for Terraform modules, Kubernetes manifests, code examples, and issue solutions."
    args_schema: Type[BaseModel] = GitHubSearchInput

    def _run(
        self, query: str, search_type: str = "repositories", limit: int = 5
    ) -> str:
        token = os.environ.get("GITHUB_TOKEN", "")

        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if token:
            headers["Authorization"] = f"token {token}"

        search_endpoints = {
            "repositories": "https://api.github.com/search/repositories",
            "code": "https://api.github.com/search/code",
            "issues": "https://api.github.com/search/issues",
        }

        if search_type not in search_endpoints:
            return f"Unknown search type: {search_type}"

        url = search_endpoints[search_type]

        if "terraform" not in query.lower() and "kubernetes" not in query.lower():
            query = f"{query} terraform OR kubernetes"

        try:
            response = httpx.get(
                url,
                headers=headers,
                params={"q": query, "per_page": limit},
                timeout=30,
            )

            if response.status_code != 200:
                return f"GitHub API error: {response.status_code}"

            data = response.json()
            items = data.get("items", [])

            output = f"## GitHub Search Results: {query}\n\n"

            for item in items:
                if search_type == "repositories":
                    output += f"### [{item['full_name']}]({item['html_url']})\n"
                    output += f"⭐ {item.get('stargazers_count', 0)} | "
                    output += (
                        f"📝 {item.get('description', 'No description')[:100]}\n\n"
                    )
                elif search_type == "code":
                    output += f"### {item['repository']['full_name']}\n"
                    output += f"File: {item['path']}\n"
                    output += f"URL: {item['html_url']}\n\n"
                elif search_type == "issues":
                    output += f"### [{item['title']}]({item['html_url']})\n"
                    output += f"State: {item['state']} | Comments: {item.get('comments', 0)}\n\n"

            return output if items else "No results found"

        except Exception as e:
            return f"Error searching GitHub: {e}"


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Maximum results")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for documentation, tutorials, and solutions to infrastructure problems."
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5) -> str:
        api_key = os.environ.get("TAVILY_API_KEY", "")

        if not api_key:
            return "Tavily API key not configured. Set TAVILY_API_KEY environment variable."

        try:
            response = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_domains": [
                        "terraform.io",
                        "kubernetes.io",
                        "arvancloud.ir",
                        "docs.aws.amazon.com",
                        "cloud.google.com",
                        "stackoverflow.com",
                        "github.com",
                    ],
                },
                timeout=30,
            )

            if response.status_code != 200:
                return f"Search API error: {response.status_code}"

            data = response.json()
            results = data.get("results", [])

            output = f"## Web Search Results: {query}\n\n"

            for r in results:
                output += f"### [{r['title']}]({r['url']})\n"
                output += f"{r.get('content', '')[:200]}...\n\n"

            return output if results else "No results found"

        except Exception as e:
            return f"Error searching: {e}"


class HCLValidatorInput(BaseModel):
    content: str = Field(description="HCL/Terraform content to validate")


class HCLValidatorTool(BaseTool):
    name: str = "hcl_validator"
    description: str = "Validate Terraform/HCL configuration syntax and formatting."
    args_schema: Type[BaseModel] = HCLValidatorInput

    def _run(self, content: str) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            tf_file = os.path.join(tmpdir, "main.tf")

            with open(tf_file, "w") as f:
                f.write(content)

            try:
                subprocess.run(
                    ["tofu", "init", "-backend=false"],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=60,
                )

                result = subprocess.run(
                    ["tofu", "validate", "-json"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                data = json.loads(result.stdout)

                if data.get("valid"):
                    fmt_result = subprocess.run(
                        ["tofu", "fmt", "-check", "-diff"],
                        cwd=tmpdir,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if fmt_result.returncode == 0:
                        return "✅ Configuration is valid and properly formatted!"
                    else:
                        return f"✅ Configuration is valid but has formatting issues:\n{fmt_result.stdout}"
                else:
                    errors = []
                    for diag in data.get("diagnostics", []):
                        errors.append(
                            f"- {diag.get('severity', 'error')}: {diag.get('summary', '')}"
                        )

                    return "❌ Validation errors:\n" + "\n".join(errors)

            except Exception as e:
                return f"Error validating: {e}"


class YAMLValidatorInput(BaseModel):
    content: str = Field(description="YAML content to validate")
    schema_type: Optional[str] = Field(
        default=None, description="Schema type: kubernetes, helm, etc."
    )


class YAMLValidatorTool(BaseTool):
    name: str = "yaml_validator"
    description: str = (
        "Validate YAML syntax for Kubernetes manifests, Helm charts, etc."
    )
    args_schema: Type[BaseModel] = YAMLValidatorInput

    def _run(self, content: str, schema_type: Optional[str] = None) -> str:
        import yaml

        try:
            docs = list(yaml.safe_load_all(content))

            issues = []

            for i, doc in enumerate(docs):
                if doc is None:
                    continue

                if schema_type == "kubernetes":
                    if not doc.get("apiVersion"):
                        issues.append(f"Document {i + 1}: Missing 'apiVersion'")
                    if not doc.get("kind"):
                        issues.append(f"Document {i + 1}: Missing 'kind'")
                    if not doc.get("metadata", {}).get("name"):
                        issues.append(f"Document {i + 1}: Missing 'metadata.name'")

            if issues:
                return "⚠️ YAML is valid but has issues:\n" + "\n".join(
                    f"- {i}" for i in issues
                )

            return f"✅ YAML is valid! Found {len([d for d in docs if d])} document(s)."

        except yaml.YAMLError as e:
            return f"❌ YAML syntax error:\n{e}"
        except Exception as e:
            return f"Error validating YAML: {e}"


def create_all_tools() -> List[BaseTool]:
    return [
        TerraformInitTool(),
        TerraformPlanTool(),
        TerraformApplyTool(),
        TerraformValidateTool(),
        KubectlTool(),
        KubernetesAnalyzerTool(),
        ArvanCloudPricingTool(),
        ArvanCloudResourceTool(),
        GitHubSearchTool(),
        WebSearchTool(),
        HCLValidatorTool(),
        YAMLValidatorTool(),
    ]


def create_tools_for_agent(agent_type: str) -> List[BaseTool]:
    all_tools = create_all_tools()

    try:
        from agents.langchain.project_tools import get_project_tools

        project_tools = get_project_tools()
    except ImportError:
        project_tools = []

    tool_mapping = {
        "planner": [
            "terraform_init",
            "terraform_plan",
            "terraform_validate",
            "hcl_validator",
            "yaml_validator",
            "web_search",
            "github_search",
            "analyze_project_files",
            "generate_optimized_dockerfile",
            "generate_kubernetes_manifests",
            "generate_docker_compose",
        ],
        "security": [
            "terraform_validate",
            "hcl_validator",
            "yaml_validator",
            "web_search",
            "kubernetes_analyzer",
        ],
        "cost": [
            "arvancloud_pricing",
            "arvancloud_resource",
            "web_search",
        ],
        "deployment": [
            "terraform_init",
            "terraform_plan",
            "terraform_apply",
            "kubectl",
            "terraform_validate",
        ],
        "diagnostic": [
            "kubectl",
            "kubernetes_analyzer",
            "web_search",
            "github_search",
        ],
        "research": [
            "web_search",
            "github_search",
        ],
        "project_analyzer": [
            "analyze_project_files",
            "generate_optimized_dockerfile",
            "generate_kubernetes_manifests",
            "generate_docker_compose",
            "hcl_validator",
            "yaml_validator",
            "web_search",
            "github_search",
        ],
        "general": [
            "terraform_init",
            "terraform_plan",
            "terraform_validate",
            "kubectl",
            "kubernetes_analyzer",
            "hcl_validator",
            "yaml_validator",
            "web_search",
            "github_search",
            "analyze_project_files",
            "generate_optimized_dockerfile",
            "generate_kubernetes_manifests",
            "generate_docker_compose",
        ],
    }

    allowed_tools = tool_mapping.get(agent_type, tool_mapping["general"])

    combined_tools = all_tools + project_tools
    {t.name for t in combined_tools}

    return [t for t in combined_tools if t.name in allowed_tools]


def create_project_aware_tools() -> List[BaseTool]:
    try:
        from agents.langchain.project_tools import get_project_tools

        return get_project_tools() + [
            HCLValidatorTool(),
            YAMLValidatorTool(),
            WebSearchTool(),
            GitHubSearchTool(),
        ]
    except ImportError:
        return create_all_tools()
