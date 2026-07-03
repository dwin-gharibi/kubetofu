import os
import json
import time
import subprocess
import tempfile
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class CloudProvider(Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ARVANCLOUD = "arvancloud"
    LOCAL_DOCKER = "docker"
    LOCAL_K8S = "k8s"


class DeploymentStatus(Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    DESTROYED = "destroyed"
    TIMEOUT = "timeout"


@dataclass
class DeploymentConfig:
    provider: CloudProvider
    region: str = "us-west-2"
    timeout_seconds: int = 600
    cleanup: bool = True
    dry_run: bool = False
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class DeploymentResult:
    success: bool
    status: DeploymentStatus
    provider: CloudProvider
    deployment_time_ms: float
    destroy_time_ms: float = 0.0
    resources_created: List[str] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    cost_estimate: Optional[float] = None


@dataclass
class HealthCheckResult:
    healthy: bool
    endpoint_reachable: bool
    response_time_ms: float
    status_code: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


class CloudDeploymentTester(ABC):
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.temp_dir: Optional[str] = None

    @abstractmethod
    def deploy(self, iac_code: str, iac_type: str) -> DeploymentResult:
        pass

    @abstractmethod
    def destroy(self, deployment_id: str) -> bool:
        pass

    @abstractmethod
    def health_check(self, outputs: Dict[str, Any]) -> HealthCheckResult:
        pass

    def _create_temp_dir(self) -> str:
        self.temp_dir = tempfile.mkdtemp(prefix="kubetofu_")
        return self.temp_dir

    def _cleanup_temp_dir(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    def _run_command(
        self,
        cmd: List[str],
        cwd: str = None,
        timeout: int = None,
    ) -> Tuple[int, str, str]:
        timeout = timeout or self.config.timeout_seconds

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.temp_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)


class TerraformTester(CloudDeploymentTester):
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self.state_file = None

    def deploy(self, iac_code: str, iac_type: str = "terraform") -> DeploymentResult:
        start_time = time.time()
        logs = []
        errors = []
        resources = []

        try:
            work_dir = self._create_temp_dir()

            tf_file = os.path.join(work_dir, "main.tf")
            with open(tf_file, "w") as f:
                f.write(iac_code)

            logs.append(f"Created Terraform file at {tf_file}")

            logs.append("Running terraform init...")
            ret, stdout, stderr = self._run_command(["terraform", "init"])
            logs.append(stdout)

            if ret != 0:
                errors.append(f"terraform init failed: {stderr}")
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    errors=errors,
                    logs=logs,
                )

            logs.append("Running terraform validate...")
            ret, stdout, stderr = self._run_command(["terraform", "validate", "-json"])
            logs.append(stdout)

            if ret != 0:
                errors.append(f"terraform validate failed: {stderr}")
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    errors=errors,
                    logs=logs,
                )

            logs.append("Running terraform plan...")
            ret, stdout, stderr = self._run_command(
                ["terraform", "plan", "-out=tfplan", "-json"]
            )
            logs.append(stdout)

            if ret != 0:
                errors.append(f"terraform plan failed: {stderr}")
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    errors=errors,
                    logs=logs,
                )

            resources = self._parse_plan_resources(stdout)

            if self.config.dry_run:
                logs.append("Dry run mode - skipping apply")
                return DeploymentResult(
                    success=True,
                    status=DeploymentStatus.PENDING,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    resources_created=resources,
                    logs=logs,
                )

            logs.append("Running terraform apply...")
            ret, stdout, stderr = self._run_command(
                ["terraform", "apply", "-auto-approve", "-json", "tfplan"],
                timeout=self.config.timeout_seconds,
            )
            logs.append(stdout)

            if ret != 0:
                errors.append(f"terraform apply failed: {stderr}")
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    errors=errors,
                    logs=logs,
                )

            logs.append("Getting outputs...")
            ret, stdout, stderr = self._run_command(["terraform", "output", "-json"])
            outputs = json.loads(stdout) if ret == 0 and stdout else {}

            deployment_time = (time.time() - start_time) * 1000

            return DeploymentResult(
                success=True,
                status=DeploymentStatus.RUNNING,
                provider=self.config.provider,
                deployment_time_ms=deployment_time,
                resources_created=resources,
                outputs=outputs,
                logs=logs,
            )

        except Exception as e:
            errors.append(str(e))
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                logs=logs,
            )

    def destroy(self, deployment_id: str = None) -> bool:
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return False

        ret, stdout, stderr = self._run_command(
            ["terraform", "destroy", "-auto-approve"],
            timeout=self.config.timeout_seconds,
        )

        if self.config.cleanup:
            self._cleanup_temp_dir()

        return ret == 0

    def health_check(self, outputs: Dict[str, Any]) -> HealthCheckResult:
        import urllib.request
        import urllib.error

        endpoint = None
        for key in ["public_ip", "endpoint", "url", "dns_name", "address"]:
            if key in outputs:
                val = outputs[key]
                if isinstance(val, dict):
                    endpoint = val.get("value")
                else:
                    endpoint = val
                break

        if not endpoint:
            return HealthCheckResult(
                healthy=False,
                endpoint_reachable=False,
                response_time_ms=0,
                details={"error": "No endpoint found in outputs"},
            )

        if not endpoint.startswith("http"):
            endpoint = f"http://{endpoint}"

        start = time.time()
        try:
            req = urllib.request.Request(endpoint)
            with urllib.request.urlopen(req, timeout=10) as response:
                response_time = (time.time() - start) * 1000
                return HealthCheckResult(
                    healthy=True,
                    endpoint_reachable=True,
                    response_time_ms=response_time,
                    status_code=response.status,
                )
        except urllib.error.HTTPError as e:
            response_time = (time.time() - start) * 1000
            return HealthCheckResult(
                healthy=e.code < 500,
                endpoint_reachable=True,
                response_time_ms=response_time,
                status_code=e.code,
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                endpoint_reachable=False,
                response_time_ms=0,
                details={"error": str(e)},
            )

    def _parse_plan_resources(self, plan_output: str) -> List[str]:
        resources = []

        for line in plan_output.split("\n"):
            if '"type":"planned_change"' in line or '"type":"resource_drift"' in line:
                try:
                    data = json.loads(line)
                    change = data.get("change", {})
                    resource = change.get("resource", {})
                    addr = resource.get("addr", "")
                    if addr:
                        resources.append(addr)
                except json.JSONDecodeError:
                    pass
            elif "# " in line and " will be created" in line:
                parts = line.split(" ")
                if len(parts) > 1:
                    resources.append(parts[1])

        return resources


class KubernetesTester(CloudDeploymentTester):
    def __init__(self, config: DeploymentConfig, namespace: str = "kubetofu-test"):
        super().__init__(config)
        self.namespace = namespace

    def deploy(self, iac_code: str, iac_type: str = "kubernetes") -> DeploymentResult:
        start_time = time.time()
        logs = []
        errors = []

        try:
            work_dir = self._create_temp_dir()

            manifest_file = os.path.join(work_dir, "manifest.yaml")
            with open(manifest_file, "w") as f:
                f.write(iac_code)

            logs.append(f"Created manifest at {manifest_file}")

            self._run_command(
                [
                    "kubectl",
                    "create",
                    "namespace",
                    self.namespace,
                    "--dry-run=client",
                    "-o",
                    "yaml",
                ]
            )

            if self.config.dry_run:
                ret, stdout, stderr = self._run_command(
                    [
                        "kubectl",
                        "apply",
                        "-f",
                        manifest_file,
                        "--dry-run=server",
                        "-n",
                        self.namespace,
                    ]
                )
                logs.append(stdout)

                if ret != 0:
                    errors.append(f"Dry run failed: {stderr}")
                    return DeploymentResult(
                        success=False,
                        status=DeploymentStatus.FAILED,
                        provider=self.config.provider,
                        deployment_time_ms=(time.time() - start_time) * 1000,
                        errors=errors,
                        logs=logs,
                    )

                return DeploymentResult(
                    success=True,
                    status=DeploymentStatus.PENDING,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    logs=logs,
                )

            logs.append("Applying manifest...")
            ret, stdout, stderr = self._run_command(
                [
                    "kubectl",
                    "apply",
                    "-f",
                    manifest_file,
                    "-n",
                    self.namespace,
                ]
            )
            logs.append(stdout)

            if ret != 0:
                errors.append(f"kubectl apply failed: {stderr}")
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    errors=errors,
                    logs=logs,
                )

            logs.append("Waiting for deployments...")
            ret, stdout, stderr = self._run_command(
                [
                    "kubectl",
                    "wait",
                    "--for=condition=available",
                    "--timeout=120s",
                    "deployment",
                    "--all",
                    "-n",
                    self.namespace,
                ],
                timeout=130,
            )
            logs.append(stdout)

            resources = self._get_created_resources()

            deployment_time = (time.time() - start_time) * 1000

            return DeploymentResult(
                success=True,
                status=DeploymentStatus.RUNNING,
                provider=self.config.provider,
                deployment_time_ms=deployment_time,
                resources_created=resources,
                logs=logs,
            )

        except Exception as e:
            errors.append(str(e))
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                logs=logs,
            )

    def destroy(self, deployment_id: str = None) -> bool:
        ret, _, _ = self._run_command(
            [
                "kubectl",
                "delete",
                "namespace",
                self.namespace,
                "--ignore-not-found=true",
            ]
        )

        if self.config.cleanup:
            self._cleanup_temp_dir()

        return ret == 0

    def health_check(self, outputs: Dict[str, Any]) -> HealthCheckResult:
        ret, stdout, stderr = self._run_command(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                self.namespace,
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )

        if ret != 0:
            return HealthCheckResult(
                healthy=False,
                endpoint_reachable=False,
                response_time_ms=0,
                details={"error": stderr},
            )

        phases = stdout.split()
        all_running = all(p == "Running" for p in phases) if phases else False

        return HealthCheckResult(
            healthy=all_running,
            endpoint_reachable=all_running,
            response_time_ms=0,
            details={"pod_phases": phases},
        )

    def _get_created_resources(self) -> List[str]:
        resources = []

        ret, stdout, _ = self._run_command(
            [
                "kubectl",
                "get",
                "all",
                "-n",
                self.namespace,
                "-o",
                "name",
            ]
        )

        if ret == 0:
            resources = [r.strip() for r in stdout.split("\n") if r.strip()]

        return resources


class DockerTester(CloudDeploymentTester):
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self.container_ids: List[str] = []

    def deploy(self, iac_code: str, iac_type: str = "dockerfile") -> DeploymentResult:
        start_time = time.time()
        logs = []
        errors = []

        try:
            work_dir = self._create_temp_dir()

            if iac_type == "dockerfile":
                return self._deploy_dockerfile(
                    iac_code, work_dir, logs, errors, start_time
                )
            elif iac_type == "docker-compose":
                return self._deploy_compose(
                    iac_code, work_dir, logs, errors, start_time
                )
            else:
                errors.append(f"Unsupported IaC type: {iac_type}")
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    provider=self.config.provider,
                    deployment_time_ms=(time.time() - start_time) * 1000,
                    errors=errors,
                    logs=logs,
                )

        except Exception as e:
            errors.append(str(e))
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                logs=logs,
            )

    def _deploy_dockerfile(
        self,
        iac_code: str,
        work_dir: str,
        logs: List[str],
        errors: List[str],
        start_time: float,
    ) -> DeploymentResult:
        dockerfile = os.path.join(work_dir, "Dockerfile")
        with open(dockerfile, "w") as f:
            f.write(iac_code)

        app_file = os.path.join(work_dir, "app.py")
        with open(app_file, "w") as f:
            f.write("""
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
""")

        image_name = f"kubetofu-test-{int(time.time())}"

        logs.append("Building Docker image...")
        ret, stdout, stderr = self._run_command(
            [
                "docker",
                "build",
                "-t",
                image_name,
                ".",
            ]
        )
        logs.append(stdout)

        if ret != 0:
            errors.append(f"Docker build failed: {stderr}")
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                logs=logs,
            )

        if self.config.dry_run:
            logs.append("Dry run - skipping container run")
            return DeploymentResult(
                success=True,
                status=DeploymentStatus.PENDING,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                resources_created=[f"image:{image_name}"],
                logs=logs,
            )

        logs.append("Running container...")
        ret, stdout, stderr = self._run_command(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-p",
                "8080:8000",
                image_name,
            ]
        )

        if ret != 0:
            errors.append(f"Docker run failed: {stderr}")
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                logs=logs,
            )

        container_id = stdout.strip()
        self.container_ids.append(container_id)
        logs.append(f"Container started: {container_id[:12]}")

        time.sleep(2)

        deployment_time = (time.time() - start_time) * 1000

        return DeploymentResult(
            success=True,
            status=DeploymentStatus.RUNNING,
            provider=self.config.provider,
            deployment_time_ms=deployment_time,
            resources_created=[f"container:{container_id[:12]}", f"image:{image_name}"],
            outputs={"endpoint": "http://localhost:8080"},
            logs=logs,
        )

    def _deploy_compose(
        self,
        iac_code: str,
        work_dir: str,
        logs: List[str],
        errors: List[str],
        start_time: float,
    ) -> DeploymentResult:
        compose_file = os.path.join(work_dir, "docker-compose.yml")
        with open(compose_file, "w") as f:
            f.write(iac_code)

        project_name = f"kubetofu-{int(time.time())}"

        logs.append("Validating docker-compose...")
        ret, stdout, stderr = self._run_command(
            [
                "docker-compose",
                "-f",
                compose_file,
                "config",
            ]
        )

        if ret != 0:
            errors.append(f"docker-compose validation failed: {stderr}")
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                logs=logs,
            )

        if self.config.dry_run:
            logs.append("Dry run - skipping deployment")
            return DeploymentResult(
                success=True,
                status=DeploymentStatus.PENDING,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                logs=logs,
            )

        logs.append("Starting services...")
        ret, stdout, stderr = self._run_command(
            [
                "docker-compose",
                "-f",
                compose_file,
                "-p",
                project_name,
                "up",
                "-d",
            ]
        )
        logs.append(stdout)

        if ret != 0:
            errors.append(f"docker-compose up failed: {stderr}")
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                provider=self.config.provider,
                deployment_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                logs=logs,
            )

        ret, stdout, _ = self._run_command(
            [
                "docker-compose",
                "-f",
                compose_file,
                "-p",
                project_name,
                "ps",
                "-q",
            ]
        )
        containers = stdout.strip().split("\n") if stdout else []

        deployment_time = (time.time() - start_time) * 1000

        return DeploymentResult(
            success=True,
            status=DeploymentStatus.RUNNING,
            provider=self.config.provider,
            deployment_time_ms=deployment_time,
            resources_created=[f"container:{c[:12]}" for c in containers if c],
            logs=logs,
        )

    def destroy(self, deployment_id: str = None) -> bool:
        success = True

        for container_id in self.container_ids:
            ret, _, _ = self._run_command(
                [
                    "docker",
                    "stop",
                    container_id,
                ]
            )
            if ret != 0:
                success = False

        self.container_ids = []

        if self.config.cleanup:
            self._cleanup_temp_dir()

        return success

    def health_check(self, outputs: Dict[str, Any]) -> HealthCheckResult:
        import urllib.request
        import urllib.error

        endpoint = outputs.get("endpoint", "http://localhost:8080")

        start = time.time()
        try:
            req = urllib.request.Request(endpoint)
            with urllib.request.urlopen(req, timeout=5) as response:
                response_time = (time.time() - start) * 1000
                return HealthCheckResult(
                    healthy=True,
                    endpoint_reachable=True,
                    response_time_ms=response_time,
                    status_code=response.status,
                )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                endpoint_reachable=False,
                response_time_ms=0,
                details={"error": str(e)},
            )


class CloudDeploymentRunner:
    def __init__(self):
        self.testers: Dict[CloudProvider, CloudDeploymentTester] = {}
        self.results: List[DeploymentResult] = []

    def add_tester(self, provider: CloudProvider, tester: CloudDeploymentTester):
        self.testers[provider] = tester

    def test_deployment(
        self,
        iac_code: str,
        iac_type: str,
        provider: CloudProvider,
    ) -> DeploymentResult:
        if provider not in self.testers:
            config = DeploymentConfig(provider=provider, dry_run=True)

            if provider == CloudProvider.LOCAL_DOCKER:
                self.testers[provider] = DockerTester(config)
            elif provider == CloudProvider.LOCAL_K8S:
                self.testers[provider] = KubernetesTester(config)
            else:
                self.testers[provider] = TerraformTester(config)

        tester = self.testers[provider]
        result = tester.deploy(iac_code, iac_type)
        self.results.append(result)

        return result

    def run_full_deployment_cycle(
        self,
        iac_code: str,
        iac_type: str,
        provider: CloudProvider,
        health_check: bool = True,
        cleanup: bool = True,
    ) -> Dict[str, Any]:
        cycle_start = time.time()

        deploy_result = self.test_deployment(iac_code, iac_type, provider)

        health_result = None
        destroy_success = True

        if deploy_result.success and health_check:
            tester = self.testers[provider]
            health_result = tester.health_check(deploy_result.outputs)

        if deploy_result.success and cleanup:
            tester = self.testers[provider]
            destroy_start = time.time()
            destroy_success = tester.destroy()
            destroy_time = (time.time() - destroy_start) * 1000
        else:
            destroy_time = 0

        total_time = (time.time() - cycle_start) * 1000

        return {
            "deployment": deploy_result,
            "health_check": health_result,
            "destroy_success": destroy_success,
            "total_time_ms": total_time,
            "destroy_time_ms": destroy_time,
        }

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)

        by_provider = {}
        for result in self.results:
            prov = result.provider.value
            if prov not in by_provider:
                by_provider[prov] = {"total": 0, "success": 0, "avg_time_ms": 0}
            by_provider[prov]["total"] += 1
            if result.success:
                by_provider[prov]["success"] += 1
            by_provider[prov]["avg_time_ms"] += result.deployment_time_ms

        for prov in by_provider:
            if by_provider[prov]["total"] > 0:
                by_provider[prov]["avg_time_ms"] /= by_provider[prov]["total"]
                by_provider[prov]["success_rate"] = (
                    by_provider[prov]["success"] / by_provider[prov]["total"]
                )

        return {
            "total_tests": total,
            "successful": successful,
            "success_rate": successful / total if total > 0 else 0,
            "by_provider": by_provider,
        }


def run_cloud_deployment_tests(verbose: bool = True) -> Dict[str, Any]:
    runner = CloudDeploymentRunner()

    dockerfile = """FROM python:3.11-slim
WORKDIR /app
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]"""

    docker_config = DeploymentConfig(
        provider=CloudProvider.LOCAL_DOCKER,
        dry_run=True,
    )
    runner.add_tester(CloudProvider.LOCAL_DOCKER, DockerTester(docker_config))

    if verbose:
        print("Testing Docker deployment...")

    docker_result = runner.test_deployment(
        dockerfile,
        "dockerfile",
        CloudProvider.LOCAL_DOCKER,
    )

    if verbose:
        status = "✅" if docker_result.success else "❌"
        print(f"  {status} Docker: {docker_result.status.value}")

    k8s_manifest = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test
  template:
    metadata:
      labels:
        app: test
    spec:
      containers:
      - name: app
        image: nginx:latest
        ports:
        - containerPort: 80
"""

    k8s_config = DeploymentConfig(
        provider=CloudProvider.LOCAL_K8S,
        dry_run=True,
    )
    runner.add_tester(CloudProvider.LOCAL_K8S, KubernetesTester(k8s_config))

    if verbose:
        print("Testing Kubernetes deployment...")

    k8s_result = runner.test_deployment(
        k8s_manifest,
        "kubernetes",
        CloudProvider.LOCAL_K8S,
    )

    if verbose:
        status = "✅" if k8s_result.success else "❌"
        print(f"  {status} Kubernetes: {k8s_result.status.value}")

    terraform_code = """
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-west-2"
}

resource "aws_instance" "test" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
  
  tags = {
    Name = "kubetofu-test"
  }
}
"""

    tf_config = DeploymentConfig(
        provider=CloudProvider.AWS,
        dry_run=True,
    )
    runner.add_tester(CloudProvider.AWS, TerraformTester(tf_config))

    if verbose:
        print("Testing Terraform deployment...")

    tf_result = runner.test_deployment(
        terraform_code,
        "terraform",
        CloudProvider.AWS,
    )

    if verbose:
        status = "✅" if tf_result.success else "❌"
        print(f"  {status} Terraform (AWS): {tf_result.status.value}")

    summary = runner.get_summary()

    if verbose:
        print("\n" + "=" * 60)
        print("Cloud Deployment Test Summary")
        print("=" * 60)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Successful: {summary['successful']}")
        print(f"Success Rate: {summary['success_rate'] * 100:.1f}%")

    return summary


if __name__ == "__main__":
    run_cloud_deployment_tests()
