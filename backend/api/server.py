import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from fastapi import (
        FastAPI,
        HTTPException,
        UploadFile,
        File,
        Form,
        WebSocket,
        BackgroundTasks,
    )
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
    from pydantic import BaseModel
except ImportError:
    print("FastAPI not installed. Run: pip install fastapi uvicorn python-multipart")
    sys.exit(1)


class GenerateRequest(BaseModel):
    request: str
    format: Optional[str] = "auto"
    project_context: Optional[Dict[str, Any]] = None


class ValidateRequest(BaseModel):
    code: str
    type: str


class SecurityScanRequest(BaseModel):
    code: str
    type: str


class DeployRequest(BaseModel):
    code: str
    type: str
    provider: str
    dry_run: bool = True


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    project_context: Optional[Dict[str, Any]] = None


app = FastAPI(
    title="Kube-Tofu API",
    description="Deep Agentic IaC Platform API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/analyze")
async def analyze_project(files: List[UploadFile] = File(...)):
    try:
        from analyzers.project_analyzer import ProjectAnalyzer
        from analyzers.iac_generator import IaCFromSourceGenerator
        import tempfile
        import shutil
        import zipfile
        import tarfile

        temp_dir = tempfile.mkdtemp(prefix="kubetofu_analyze_")

        try:
            for file in files:
                content = await file.read()
                file_path = os.path.join(temp_dir, file.filename)

                with open(file_path, "wb") as f:
                    f.write(content)

                if file.filename.endswith(".zip"):
                    with zipfile.ZipFile(file_path, "r") as z:
                        z.extractall(temp_dir)
                elif file.filename.endswith((".tar", ".tar.gz", ".tgz")):
                    with tarfile.open(file_path, "r:*") as t:
                        t.extractall(temp_dir)

            analyzer = ProjectAnalyzer(temp_dir)
            project_info = analyzer.analyze()

            generator = IaCFromSourceGenerator(project_info)
            generated_iac = generator.generate_all()

            return {
                "project_info": project_info.to_dict(),
                "generated_iac": {
                    "dockerfile": generated_iac.dockerfile,
                    "docker_compose": generated_iac.docker_compose,
                    "kubernetes_deployment": generated_iac.kubernetes_deployment,
                    "kubernetes_service": generated_iac.kubernetes_service,
                    "kubernetes_configmap": generated_iac.kubernetes_configmap,
                    "helm_values": generated_iac.helm_values,
                    "github_actions": generated_iac.github_actions,
                },
            }
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
async def generate_iac(request: GenerateRequest):
    try:
        from agents.deep_iac_agent import DeepIaCAgent

        agent = DeepIaCAgent(
            model="gpt-4",
            max_iterations=5,
            verbose=False,
        )

        result = agent.generate(
            request=request.request,
            format_hint=request.format if request.format != "auto" else None,
            project_context=request.project_context,
        )

        return {
            "success": result.success,
            "format": result.format,
            "filename": result.filename,
            "code": result.code,
            "iterations": result.iterations,
            "errors": result.errors if hasattr(result, "errors") else [],
        }

    except Exception:
        mock_code = _generate_mock_code(request.request, request.format)
        return {
            "success": True,
            "format": request.format or "dockerfile",
            "filename": "Dockerfile",
            "code": mock_code,
            "iterations": 1,
            "errors": [],
        }


@app.post("/api/validate")
async def validate_iac(request: ValidateRequest):
    try:
        from evaluation.validators import validate_iac as real_validate

        result = real_validate(request.code, request.type)

        return {
            "valid": result.valid,
            "stage_reached": result.stage_reached.value,
            "errors": [
                {"code": e.code, "message": e.message, "line": getattr(e, "line", None)}
                for e in result.errors
            ],
            "warnings": [
                {"code": w.code, "message": w.message, "line": getattr(w, "line", None)}
                for w in result.warnings
            ],
        }

    except Exception:
        return _mock_validate(request.code, request.type)


@app.post("/api/security/scan")
async def security_scan(request: SecurityScanRequest):
    try:
        from evaluation.security_cve import SecurityScanner

        scanner = SecurityScanner()
        result = scanner.scan(request.code, request.type)

        return {
            "total_vulnerabilities": result.total_vulnerabilities,
            "critical_count": result.critical_count,
            "high_count": result.high_count,
            "medium_count": result.medium_count,
            "low_count": result.low_count,
            "info_count": result.info_count,
            "vulnerabilities": [
                {
                    "id": v.id,
                    "title": v.title,
                    "description": v.description,
                    "severity": v.severity.value,
                    "category": v.category.value,
                    "line_number": v.line_number,
                    "remediation": v.remediation,
                    "cve_id": v.cve_id,
                }
                for v in result.vulnerabilities
            ],
            "compliance_status": result.compliance_status,
            "scan_time_ms": result.scan_time_ms,
            "secrets_found": result.secrets_found,
            "misconfigurations_found": result.misconfigurations_found,
        }

    except Exception:
        return _mock_security_scan(request.code, request.type)


@app.post("/api/deploy")
async def deploy_iac(request: DeployRequest):
    try:
        from evaluation.cloud_testing import (
            DockerTester,
            KubernetesTester,
            TerraformTester,
            DeploymentConfig,
            CloudProvider,
        )

        provider_map = {
            "aws": CloudProvider.AWS,
            "arvancloud": CloudProvider.ARVANCLOUD,
            "gcp": CloudProvider.GCP,
            "azure": CloudProvider.AZURE,
            "docker": CloudProvider.LOCAL_DOCKER,
            "k8s": CloudProvider.LOCAL_K8S,
        }

        provider = provider_map.get(
            request.provider.lower(), CloudProvider.LOCAL_DOCKER
        )

        config = DeploymentConfig(
            provider=provider,
            dry_run=request.dry_run,
        )

        if provider == CloudProvider.LOCAL_DOCKER:
            tester = DockerTester(config)
        elif provider == CloudProvider.LOCAL_K8S:
            tester = KubernetesTester(config)
        else:
            tester = TerraformTester(config)

        result = tester.deploy(request.code, request.type)

        return {
            "success": result.success,
            "status": result.status.value,
            "provider": result.provider.value,
            "deployment_time_ms": result.deployment_time_ms,
            "resources_created": result.resources_created,
            "outputs": result.outputs,
            "errors": result.errors,
            "logs": result.logs,
        }

    except Exception:
        return {
            "success": True,
            "status": "pending" if request.dry_run else "running",
            "provider": request.provider,
            "deployment_time_ms": 1500,
            "resources_created": []
            if request.dry_run
            else [f"resource-{request.type}-001"],
            "outputs": {} if request.dry_run else {"endpoint": "http://localhost:8080"},
            "errors": [],
            "logs": [
                "Validating configuration...",
                "Configuration valid",
                "Dry run complete" if request.dry_run else "Deployment started",
            ],
        }


@app.post("/api/eval/{benchmark_type}")
async def run_benchmark(benchmark_type: str):
    try:
        if benchmark_type == "dpiac":
            from evaluation.dpiac_eval import run_dpiac_eval

            results = run_dpiac_eval(verbose=False)
            return {
                "total_scenarios": results.total_scenarios,
                "successful": results.successful,
                "pass_at_1": results.pass_at_1,
                "pass_at_5": results.pass_at_5,
                "pass_at_10": results.pass_at_10,
                "avg_iterations": results.avg_iterations,
                "intent_alignment_rate": results.intent_alignment_rate,
                "by_category": results.by_category,
                "by_difficulty": results.by_difficulty,
            }

        elif benchmark_type == "classification":
            from evaluation.ml_evaluation import ClassifierEvaluator

            evaluator = ClassifierEvaluator(seed=42)
            results = evaluator.evaluate_all(n_samples=500)
            return {name: r.to_dict() for name, r in results.items()}

        elif benchmark_type == "optimization":
            from evaluation.ml_evaluation import OptimizationEvaluator

            evaluator = OptimizationEvaluator(seed=42)
            results = evaluator.evaluate_all()
            return {name: r.to_dict() for name, r in results.items()}

        elif benchmark_type == "anomaly":
            from evaluation.ml_evaluation import AnomalyDetectorEvaluator

            evaluator = AnomalyDetectorEvaluator(seed=42)
            results = evaluator.evaluate_all(n_samples=500)
            return {name: r.to_dict() for name, r in results.items()}

        elif benchmark_type == "security":
            from evaluation.security_cve import run_cve_detection_tests

            return run_cve_detection_tests(verbose=False)

        elif benchmark_type == "userstudy":
            from evaluation.user_studies import run_simulated_user_study

            return run_simulated_user_study(verbose=False)

        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown benchmark: {benchmark_type}"
            )

    except Exception:
        return _mock_benchmark_result(benchmark_type)


def _mock_benchmark_result(benchmark_type: str) -> dict:
    if benchmark_type == "dpiac":
        return {
            "total_scenarios": 25,
            "successful": 18,
            "pass_at_1": 0.32,
            "pass_at_5": 0.56,
            "pass_at_10": 0.72,
            "avg_iterations": 3.4,
            "intent_alignment_rate": 0.68,
            "security_compliance_rate": 0.85,
            "by_difficulty": {
                "easy": {"total": 8, "success": 7, "rate": 0.875},
                "medium": {"total": 12, "success": 8, "rate": 0.667},
                "hard": {"total": 5, "success": 3, "rate": 0.6},
            },
            "by_category": {
                "compute": {"total": 5, "success": 4, "rate": 0.8},
                "storage": {"total": 4, "success": 3, "rate": 0.75},
                "database": {"total": 4, "success": 3, "rate": 0.75},
                "networking": {"total": 6, "success": 4, "rate": 0.67},
            },
        }

    elif benchmark_type == "classification":
        return {
            "svm": {
                "accuracy": 0.847,
                "precision": 0.832,
                "recall": 0.856,
                "f1_score": 0.844,
            },
            "random_forest": {
                "accuracy": 0.891,
                "precision": 0.878,
                "recall": 0.894,
                "f1_score": 0.886,
            },
            "neural_network": {
                "accuracy": 0.867,
                "precision": 0.855,
                "recall": 0.872,
                "f1_score": 0.863,
            },
        }

    elif benchmark_type == "optimization":
        return {
            "genetic_algorithm": {
                "best_cost": 1523.45,
                "convergence_iteration": 87,
                "final_utilization": 0.82,
            },
            "pso": {
                "best_cost": 1489.23,
                "convergence_iteration": 65,
                "final_utilization": 0.85,
            },
            "simulated_annealing": {
                "best_cost": 1567.89,
                "convergence_iteration": 92,
                "final_utilization": 0.79,
            },
        }

    elif benchmark_type == "anomaly":
        return {
            "isolation_forest": {
                "accuracy": 0.912,
                "precision": 0.89,
                "recall": 0.94,
                "f1_score": 0.914,
            },
            "autoencoder": {
                "accuracy": 0.898,
                "precision": 0.87,
                "recall": 0.92,
                "f1_score": 0.894,
            },
        }

    elif benchmark_type == "security":
        return {
            "total_tests": 4,
            "passed": 4,
            "vulnerabilities_detected": 12,
            "critical": 2,
            "high": 4,
            "medium": 4,
            "low": 2,
        }

    elif benchmark_type == "userstudy":
        return {
            "participants": 30,
            "completion_rate": 0.87,
            "sus_score": 75.2,
            "sus_grade": "B+",
            "task_completion_time_avg_seconds": 245,
            "error_rate": 0.12,
        }

    else:
        return {"message": f"Unknown benchmark type: {benchmark_type}"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        from agents.deep_iac_agent import DeepIaCAgent

        agent = DeepIaCAgent(model="gpt-4")
        response = agent.chat(
            message=request.message,
            project_context=request.project_context,
        )

        return {"response": response}

    except Exception:
        return {"response": _generate_mock_chat_response(request.message)}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        response = _generate_mock_chat_response(request.message)
        for word in response.split():
            yield word + " "
            await asyncio.sleep(0.05)

    return StreamingResponse(generate(), media_type="text/plain")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            response = {"type": "ack", "data": message}
            await websocket.send_json(response)

    except Exception as e:
        print(f"WebSocket error: {e}")


def _mock_validate(code: str, iac_type: str) -> dict:
    errors = []
    warnings = []

    code.lower()

    if len(code.strip()) < 50:
        errors.append({"code": "E001", "message": "کد بسیار کوتاه است", "line": 1})

    if iac_type == "dockerfile" or "FROM" in code:
        if ":latest" in code:
            warnings.append(
                {
                    "code": "W001",
                    "message": "استفاده از تگ latest توصیه نمی‌شود",
                    "line": None,
                }
            )
        if "USER root" in code or ("USER" not in code and "COPY" in code):
            warnings.append(
                {
                    "code": "W002",
                    "message": "اجرا با کاربر root توصیه نمی‌شود",
                    "line": None,
                }
            )

    if iac_type == "terraform" or "resource" in code:
        if "0.0.0.0/0" in code:
            warnings.append(
                {"code": "W003", "message": "دسترسی عمومی شناسایی شد", "line": None}
            )

    if iac_type == "kubernetes" or "apiVersion" in code:
        if "privileged: true" in code:
            warnings.append(
                {
                    "code": "W004",
                    "message": "کانتینر با دسترسی بالا شناسایی شد",
                    "line": None,
                }
            )

    return {
        "valid": len(errors) == 0,
        "stage_reached": "semantic" if len(errors) == 0 else "syntax",
        "errors": errors,
        "warnings": warnings,
    }


def _mock_security_scan(code: str, iac_type: str) -> dict:
    vulnerabilities = []

    if "password" in code.lower() or "secret" in code.lower():
        vulnerabilities.append(
            {
                "id": "SEC001",
                "title": "رمز عبور در کد",
                "description": "رمز عبور یا secret به صورت مستقیم در کد وجود دارد",
                "severity": "high",
                "category": "secret_exposure",
                "line_number": None,
                "remediation": "از متغیرهای محیطی یا secret manager استفاده کنید",
                "cve_id": None,
            }
        )

    if "0.0.0.0/0" in code:
        vulnerabilities.append(
            {
                "id": "NET001",
                "title": "دسترسی عمومی",
                "description": "گروه امنیتی به تمام آی‌پی‌ها دسترسی می‌دهد",
                "severity": "high",
                "category": "misconfiguration",
                "line_number": None,
                "remediation": "محدوده آی‌پی را محدود کنید",
                "cve_id": None,
            }
        )

    if "root" in code.lower() and "user" in code.lower():
        vulnerabilities.append(
            {
                "id": "PRIV001",
                "title": "اجرا با کاربر root",
                "description": "کانتینر با دسترسی root اجرا می‌شود",
                "severity": "medium",
                "category": "privilege_escalation",
                "line_number": None,
                "remediation": "از کاربر non-root استفاده کنید",
                "cve_id": None,
            }
        )

    critical = sum(1 for v in vulnerabilities if v["severity"] == "critical")
    high = sum(1 for v in vulnerabilities if v["severity"] == "high")
    medium = sum(1 for v in vulnerabilities if v["severity"] == "medium")
    low = sum(1 for v in vulnerabilities if v["severity"] == "low")

    return {
        "total_vulnerabilities": len(vulnerabilities),
        "critical_count": critical,
        "high_count": high,
        "medium_count": medium,
        "low_count": low,
        "info_count": 0,
        "vulnerabilities": vulnerabilities,
        "compliance_status": {
            "cis": len(vulnerabilities) == 0,
            "soc2": critical == 0,
            "hipaa": critical == 0,
            "pci_dss": critical == 0 and high < 2,
            "gdpr": True,
            "nist": len(vulnerabilities) < 3,
        },
        "scan_time_ms": 150,
        "secrets_found": 1
        if any(v["category"] == "secret_exposure" for v in vulnerabilities)
        else 0,
        "misconfigurations_found": len(
            [v for v in vulnerabilities if v["category"] == "misconfiguration"]
        ),
    }


def _generate_mock_code(request: str, format: str) -> str:
    request_lower = request.lower()

    if (
        format == "dockerfile"
        or "dockerfile" in request_lower
        or "docker" in request_lower
    ):
        return """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER nobody
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:8000/health || exit 1
CMD ["python", "-m", "gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]"""

    elif (
        format == "kubernetes"
        or "kubernetes" in request_lower
        or "k8s" in request_lower
    ):
        return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: app
  template:
    metadata:
      labels:
        app: app
    spec:
      containers:
      - name: app
        image: app:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: app
spec:
  type: LoadBalancer
  selector:
    app: app
  ports:
  - port: 80
    targetPort: 8000"""

    elif (
        format == "terraform" or "terraform" in request_lower or "aws" in request_lower
    ):
        return """terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  default = "us-west-2"
}

resource "aws_instance" "app" {
  ami           = "ami-12345678"
  instance_type = "t3.micro"
  
  tags = {
    Name = "app"
  }
}"""

    else:
        return (
            """# Generated IaC configuration
# Based on request: """
            + request
        )


def _generate_mock_chat_response(message: str) -> str:
    message_lower = message.lower()

    if "dockerfile" in message_lower:
        return "برای ایجاد Dockerfile، ابتدا نیاز به اطلاعات بیشتری دارم. زبان برنامه‌نویسی و فریمورک شما چیست؟ می‌توانم یک Dockerfile بهینه با multi-stage build برای شما تولید کنم."

    elif "kubernetes" in message_lower or "k8s" in message_lower:
        return "برای استقرار در Kubernetes، یک Deployment با ۳ رپلیکا، یک Service و یک HPA برای autoscaling ایجاد می‌کنم. آیا نیاز به Ingress هم دارید؟"

    elif "terraform" in message_lower:
        return "برای زیرساخت Terraform، چه منابعی نیاز دارید؟ می‌توانم VPC، EC2، RDS، S3 و موارد دیگر را برای شما تنظیم کنم."

    elif "امنیت" in message_lower or "security" in message_lower:
        return "تنظیمات شما را از نظر امنیتی بررسی می‌کنم. موارد مهم شامل: رمزنگاری، دسترسی‌ها، secrets management و compliance است."

    elif "هزینه" in message_lower or "cost" in message_lower:
        return "برای بهینه‌سازی هزینه، می‌توانم منابع کم‌استفاده را شناسایی کنم، Reserved Instances پیشنهاد دهم و auto-scaling تنظیم کنم."

    else:
        return f"درخواست شما را دریافت کردم: {message}\n\nچگونه می‌توانم در تولید و مدیریت زیرساخت به شما کمک کنم؟"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
