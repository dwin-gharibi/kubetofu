import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProjectFileInput(BaseModel):
    files: List[Dict[str, str]] = Field(
        description="List of files with 'name', 'path', and 'content' keys"
    )


class DockerfileGeneratorInput(BaseModel):
    project_name: str = Field(description="Name of the project")
    language: str = Field(
        description="Programming language (python, javascript, go, rust, java)"
    )
    framework: Optional[str] = Field(
        default=None, description="Framework (fastapi, django, express, nestjs, etc.)"
    )
    port: int = Field(default=8000, description="Application port to expose")
    base_image: Optional[str] = Field(
        default=None, description="Custom base image override"
    )
    build_command: Optional[str] = Field(
        default=None, description="Custom build command"
    )
    start_command: Optional[str] = Field(
        default=None, description="Custom start command"
    )
    multi_stage: bool = Field(
        default=True, description="Use multi-stage build for smaller images"
    )
    include_healthcheck: bool = Field(
        default=True, description="Include HEALTHCHECK instruction"
    )
    non_root_user: bool = Field(
        default=True, description="Run as non-root user for security"
    )


class KubernetesGeneratorInput(BaseModel):
    app_name: str = Field(description="Application name (used for resource names)")
    image: str = Field(description="Docker image name with optional tag")
    replicas: int = Field(default=3, description="Number of pod replicas")
    port: int = Field(default=8000, description="Container port")
    service_type: str = Field(
        default="ClusterIP",
        description="Service type: ClusterIP, NodePort, LoadBalancer",
    )
    cpu_request: str = Field(default="100m", description="CPU request")
    cpu_limit: str = Field(default="500m", description="CPU limit")
    memory_request: str = Field(default="256Mi", description="Memory request")
    memory_limit: str = Field(default="512Mi", description="Memory limit")
    enable_hpa: bool = Field(default=True, description="Enable HorizontalPodAutoscaler")
    hpa_min_replicas: int = Field(default=3, description="HPA minimum replicas")
    hpa_max_replicas: int = Field(default=10, description="HPA maximum replicas")
    hpa_cpu_target: int = Field(
        default=70, description="HPA CPU utilization target percentage"
    )

    enable_ingress: bool = Field(default=False, description="Generate Ingress resource")
    ingress_host: Optional[str] = Field(default=None, description="Ingress hostname")
    ingress_tls: bool = Field(default=True, description="Enable TLS for ingress")

    enable_pdb: bool = Field(default=True, description="Enable PodDisruptionBudget")

    env_vars: Optional[Dict[str, str]] = Field(
        default=None, description="Environment variables"
    )
    secret_refs: Optional[List[str]] = Field(
        default=None, description="Secret names to mount"
    )
    configmap_refs: Optional[List[str]] = Field(
        default=None, description="ConfigMap names to mount"
    )


class TerraformGeneratorInput(BaseModel):
    provider: str = Field(description="Cloud provider: aws, gcp, azure, arvancloud")
    resource_type: str = Field(
        description="Resource type: vpc, ec2, rds, eks, s3, etc."
    )
    name: str = Field(description="Resource name")
    region: str = Field(default="us-east-1", description="Cloud region")
    environment: str = Field(default="production", description="Environment name")

    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Provider-specific configuration"
    )

    tags: Optional[Dict[str, str]] = Field(default=None, description="Resource tags")


class DockerComposeGeneratorInput(BaseModel):
    project_name: str = Field(description="Project name")
    services: List[Dict[str, Any]] = Field(
        description="List of services with their config"
    )
    networks: Optional[List[str]] = Field(default=None, description="Custom networks")
    volumes: Optional[List[str]] = Field(default=None, description="Named volumes")


class SecurityScanInput(BaseModel):
    code: str = Field(description="IaC code to scan")
    code_type: str = Field(description="Type: terraform, kubernetes, dockerfile")


@tool(args_schema=ProjectFileInput)
def analyze_project_files(files: List[Dict[str, str]]) -> str:
    analysis = {
        "language": "unknown",
        "framework": None,
        "service_type": "unknown",
        "dependencies": [],
        "databases": [],
        "ports": [],
        "env_vars": [],
        "has_dockerfile": False,
        "has_kubernetes": False,
        "has_terraform": False,
        "has_docker_compose": False,
        "has_ci_cd": False,
        "entry_point": None,
        "test_framework": None,
        "package_manager": None,
        "suggestions": [],
        "security_notes": [],
    }

    filenames = {f.get("name", "").lower(): f for f in files}
    file_paths = [f.get("path", "").lower() for f in files]

    analysis["has_dockerfile"] = any("dockerfile" in fn for fn in filenames)
    analysis["has_docker_compose"] = any(
        "docker-compose" in fn or "compose.y" in fn for fn in filenames
    )
    analysis["has_kubernetes"] = any(
        fn.endswith((".yaml", ".yml"))
        and any(
            kw in fn
            for kw in [
                "k8s",
                "kubernetes",
                "deployment",
                "service",
                "ingress",
                "kustomization",
            ]
        )
        for fn in filenames
    )
    analysis["has_terraform"] = any(fn.endswith(".tf") for fn in filenames)
    analysis["has_ci_cd"] = any(
        ".github/workflows" in p or ".gitlab-ci" in p or "jenkinsfile" in fn
        for fn, p in zip(filenames.keys(), file_paths)
    )

    for f in files:
        name = f.get("name", "").lower()
        content = f.get("content", "")
        f.get("path", "").lower()

        if name == "requirements.txt":
            analysis["language"] = "python"
            analysis["package_manager"] = "pip"
            deps = _parse_requirements_txt(content)
            analysis["dependencies"].extend(deps)

            dep_names = [d["name"].lower() for d in deps]
            if "django" in dep_names:
                analysis["framework"] = "django"
                analysis["service_type"] = "web"
            elif "fastapi" in dep_names:
                analysis["framework"] = "fastapi"
                analysis["service_type"] = "api"
            elif "flask" in dep_names:
                analysis["framework"] = "flask"
                analysis["service_type"] = "api"
            elif "celery" in dep_names:
                analysis["service_type"] = "worker"

            if any(
                db in dep_names for db in ["psycopg2", "psycopg2-binary", "asyncpg"]
            ):
                if "postgresql" not in analysis["databases"]:
                    analysis["databases"].append("postgresql")
            if any(
                db in dep_names
                for db in ["pymysql", "mysqlclient", "mysql-connector-python"]
            ):
                if "mysql" not in analysis["databases"]:
                    analysis["databases"].append("mysql")
            if any(db in dep_names for db in ["pymongo", "motor"]):
                if "mongodb" not in analysis["databases"]:
                    analysis["databases"].append("mongodb")
            if any(db in dep_names for db in ["redis", "aioredis"]):
                if "redis" not in analysis["databases"]:
                    analysis["databases"].append("redis")

            if any(t in dep_names for t in ["pytest", "pytest-cov", "pytest-asyncio"]):
                analysis["test_framework"] = "pytest"
            elif "unittest" in dep_names:
                analysis["test_framework"] = "unittest"

        elif name == "pyproject.toml":
            analysis["language"] = "python"
            analysis["package_manager"] = (
                "poetry" if "[tool.poetry]" in content else "pip"
            )

        elif name == "setup.py":
            analysis["language"] = "python"

        elif name == "package.json":
            analysis["package_manager"] = "npm"
            try:
                pkg = json.loads(content)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                for dep_name, version in deps.items():
                    analysis["dependencies"].append(
                        {"name": dep_name, "version": version}
                    )

                if "typescript" in deps:
                    analysis["language"] = "typescript"
                else:
                    analysis["language"] = "javascript"

                if "next" in deps:
                    analysis["framework"] = "nextjs"
                    analysis["service_type"] = "web"
                elif "express" in deps:
                    analysis["framework"] = "express"
                    analysis["service_type"] = "api"
                elif "@nestjs/core" in deps:
                    analysis["framework"] = "nestjs"
                    analysis["service_type"] = "api"
                elif "react" in deps and "next" not in deps:
                    analysis["framework"] = "react"
                    analysis["service_type"] = "web"
                elif "vue" in deps:
                    analysis["framework"] = "vue"
                    analysis["service_type"] = "web"

                analysis["entry_point"] = pkg.get("main", "index.js")

                if "jest" in deps:
                    analysis["test_framework"] = "jest"
                elif "mocha" in deps:
                    analysis["test_framework"] = "mocha"

            except json.JSONDecodeError:
                pass

        elif name == "yarn.lock":
            analysis["package_manager"] = "yarn"

        elif name == "pnpm-lock.yaml":
            analysis["package_manager"] = "pnpm"

        elif name == "go.mod":
            analysis["language"] = "go"
            analysis["service_type"] = "api"
            analysis["package_manager"] = "go modules"

            for line in content.split("\n"):
                if line.strip().startswith(("require", "//")) or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 2:
                    analysis["dependencies"].append(
                        {
                            "name": parts[0],
                            "version": parts[1] if len(parts) > 1 else "",
                        }
                    )

        elif name == "cargo.toml":
            analysis["language"] = "rust"
            analysis["package_manager"] = "cargo"

        elif name == "pom.xml":
            analysis["language"] = "java"
            analysis["package_manager"] = "maven"
            if "spring-boot" in content.lower():
                analysis["framework"] = "spring-boot"
                analysis["service_type"] = "api"

        elif name == "build.gradle" or name == "build.gradle.kts":
            analysis["language"] = "java"
            analysis["package_manager"] = "gradle"
            if "spring-boot" in content.lower():
                analysis["framework"] = "spring-boot"

        elif name in [".env.example", ".env.sample", ".env.template"]:
            env_matches = re.findall(r"^([A-Z_][A-Z0-9_]*)=", content, re.MULTILINE)
            analysis["env_vars"].extend(env_matches)

        if any(
            db in content.lower() for db in ["postgresql", "postgres", "pg_", "psycopg"]
        ):
            if "postgresql" not in analysis["databases"]:
                analysis["databases"].append("postgresql")
        if any(db in content.lower() for db in ["mysql", "mariadb"]):
            if "mysql" not in analysis["databases"]:
                analysis["databases"].append("mysql")
        if "mongodb" in content.lower() or "mongoose" in content.lower():
            if "mongodb" not in analysis["databases"]:
                analysis["databases"].append("mongodb")
        if "redis" in content.lower():
            if "redis" not in analysis["databases"]:
                analysis["databases"].append("redis")
        if "elasticsearch" in content.lower():
            if "elasticsearch" not in analysis["databases"]:
                analysis["databases"].append("elasticsearch")

        port_patterns = [
            r"(?:PORT|port|EXPOSE)[:\s=]+(\d{4,5})",
            r"listen\s*\(\s*(\d{4,5})",
            r"\.listen\((\d{4,5})",
            r'bind[:\s=]+["\']?0\.0\.0\.0:(\d{4,5})',
        ]
        for pattern in port_patterns:
            matches = re.findall(pattern, content)
            for port in matches:
                p = int(port)
                if 1000 < p < 65536 and p not in analysis["ports"]:
                    analysis["ports"].append(p)

        if re.search(
            r'(password|secret|api_key|apikey|token)\s*=\s*["\'][^"\']+["\']',
            content,
            re.IGNORECASE,
        ):
            if "احتمال وجود رمز عبور در کد" not in analysis["security_notes"]:
                analysis["security_notes"].append(
                    "احتمال وجود رمز عبور در کد - استفاده از secrets manager توصیه می‌شود"
                )

    if not analysis["has_dockerfile"]:
        analysis["suggestions"].append(
            f"ایجاد Dockerfile برای {analysis['language']}/{analysis['framework'] or 'native'}"
        )

    if not analysis["has_kubernetes"] and analysis["has_dockerfile"]:
        analysis["suggestions"].append("ایجاد مانیفست‌های Kubernetes برای استقرار")

    if analysis["databases"] and not analysis["has_terraform"]:
        analysis["suggestions"].append(
            f"ایجاد Terraform برای {', '.join(analysis['databases'])}"
        )

    if not analysis["has_ci_cd"]:
        analysis["suggestions"].append(
            "ایجاد CI/CD pipeline (GitHub Actions یا GitLab CI)"
        )

    if analysis["security_notes"]:
        analysis["suggestions"].append("بررسی و رفع مشکلات امنیتی شناسایی شده")

    return json.dumps(analysis, ensure_ascii=False, indent=2)


def _parse_requirements_txt(content: str) -> List[Dict[str, str]]:
    deps = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        match = re.match(r"^([a-zA-Z0-9_-]+)\s*([<>=!]+)?\s*(.*)$", line)
        if match:
            name = match.group(1)
            version = f"{match.group(2) or ''}{match.group(3) or ''}".strip()
            deps.append({"name": name, "version": version})

    return deps


@tool(args_schema=DockerfileGeneratorInput)
def generate_optimized_dockerfile(
    project_name: str,
    language: str,
    framework: Optional[str] = None,
    port: int = 8000,
    base_image: Optional[str] = None,
    build_command: Optional[str] = None,
    start_command: Optional[str] = None,
    multi_stage: bool = True,
    include_healthcheck: bool = True,
    non_root_user: bool = True,
) -> str:
    """
    تولید Dockerfile بهینه با multi-stage build، امنیت و بهترین روش‌ها.

    Generate an optimized Dockerfile with:
    - Multi-stage builds for smaller images
    - Non-root user for security
    - Health checks for container orchestration
    - Optimized layer caching
    - Security best practices
    """

    configs = {
        "python": {
            "base": "python:3.11-slim",
            "builder_base": "python:3.11-slim",
            "install_deps": "pip install --no-cache-dir --user -r requirements.txt",
            "copy_deps": "COPY --from=builder /root/.local /root/.local",
            "path_update": "ENV PATH=/root/.local/bin:$PATH",
            "default_cmd": {
                "fastapi": "uvicorn main:app --host 0.0.0.0 --port {port}",
                "django": "gunicorn --bind 0.0.0.0:{port} --workers 4 config.wsgi:application",
                "flask": "gunicorn --bind 0.0.0.0:{port} --workers 4 app:app",
                "default": "python main.py",
            },
            "healthcheck_cmd": "curl -f http://localhost:{port}/health || exit 1",
        },
        "javascript": {
            "base": "node:20-alpine",
            "builder_base": "node:20-alpine",
            "install_deps": "npm ci --only=production",
            "copy_deps": "COPY --from=builder /app/node_modules ./node_modules",
            "path_update": "",
            "default_cmd": {
                "nextjs": "node server.js",
                "express": "node index.js",
                "nestjs": "node dist/main.js",
                "default": "node index.js",
            },
            "healthcheck_cmd": "wget -q --spider http://localhost:{port}/health || exit 1",
        },
        "typescript": {
            "base": "node:20-alpine",
            "builder_base": "node:20-alpine",
            "install_deps": "npm ci",
            "build_cmd": "npm run build",
            "copy_deps": "COPY --from=builder /app/node_modules ./node_modules\nCOPY --from=builder /app/dist ./dist",
            "path_update": "",
            "default_cmd": {
                "nextjs": "node server.js",
                "nestjs": "node dist/main.js",
                "default": "node dist/index.js",
            },
            "healthcheck_cmd": "wget -q --spider http://localhost:{port}/health || exit 1",
        },
        "go": {
            "base": "scratch",
            "builder_base": "golang:1.21-alpine",
            "install_deps": "go mod download",
            "build_cmd": "CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main .",
            "copy_deps": "COPY --from=builder /app/main .\nCOPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/",
            "path_update": "",
            "default_cmd": {"default": "./main"},
            "healthcheck_cmd": None,
        },
        "rust": {
            "base": "debian:bookworm-slim",
            "builder_base": "rust:1.75-slim",
            "install_deps": "cargo build --release",
            "copy_deps": f"COPY --from=builder /app/target/release/{project_name} /usr/local/bin/",
            "path_update": "",
            "default_cmd": {"default": f"/usr/local/bin/{project_name}"},
            "healthcheck_cmd": "curl -f http://localhost:{port}/health || exit 1",
        },
    }

    lang = language.lower()
    config = configs.get(lang, configs["python"])

    final_base = base_image or config["base"]
    builder_base = config.get("builder_base", final_base)
    cmd = start_command or config["default_cmd"].get(
        framework, config["default_cmd"]["default"]
    ).format(port=port)
    healthcheck = (
        config.get("healthcheck_cmd", "").format(port=port)
        if include_healthcheck
        else ""
    )

    lines = [
        f"# Dockerfile برای پروژه {project_name}",
        f"# زبان: {language}, فریم‌ورک: {framework or 'native'}",
        "# تولید شده توسط کیوب‌توفو",
        "",
    ]

    if multi_stage and lang != "go":
        lines.extend(
            [
                "# ===== مرحله ساخت =====",
                f"FROM {builder_base} AS builder",
                "",
                "WORKDIR /app",
                "",
                "# کپی فایل‌های وابستگی",
            ]
        )

        if lang == "python":
            lines.append("COPY requirements.txt .")
            lines.append(f"RUN {config['install_deps']}")
        elif lang in ["javascript", "typescript"]:
            lines.append("COPY package*.json ./")
            lines.append(f"RUN {config['install_deps']}")
            if lang == "typescript" or framework == "nextjs":
                lines.extend(
                    [
                        "",
                        "# کپی کد و ساخت",
                        "COPY . .",
                        f"RUN {build_command or config.get('build_cmd', 'npm run build')}",
                    ]
                )

        lines.extend(
            [
                "",
                "# ===== مرحله اجرا =====",
                f"FROM {final_base}",
                "",
                "WORKDIR /app",
                "",
                "# کپی وابستگی‌ها از مرحله ساخت",
                config["copy_deps"],
            ]
        )

        if config.get("path_update"):
            lines.append(config["path_update"])

        lines.extend(
            [
                "",
                "# کپی کد اپلیکیشن",
                "COPY . .",
            ]
        )
    else:
        lines.extend(
            [
                f"FROM {builder_base} AS builder",
                "",
                "WORKDIR /app",
                "",
            ]
        )

        if lang == "go":
            lines.extend(
                [
                    "# کپی فایل‌های Go",
                    "COPY go.mod go.sum ./",
                    f"RUN {config['install_deps']}",
                    "",
                    "# کپی کد و ساخت",
                    "COPY . .",
                    f"RUN {config['build_cmd']}",
                    "",
                    "# ===== مرحله اجرا =====",
                    f"FROM {final_base}",
                    "",
                    "WORKDIR /app",
                    "",
                    config["copy_deps"],
                ]
            )
        else:
            lines.extend(
                [
                    "COPY . .",
                    f"RUN {config['install_deps']}",
                ]
            )

    if non_root_user and lang != "go":
        lines.extend(
            [
                "",
                "# ایجاد کاربر غیر-root برای امنیت",
            ]
        )
        if "alpine" in final_base:
            lines.append(
                "RUN addgroup -g 1001 -S appgroup && adduser -S appuser -u 1001 -G appgroup"
            )
        else:
            lines.append("RUN useradd --create-home --shell /bin/bash appuser")
        lines.extend(
            [
                "RUN chown -R appuser:appgroup /app 2>/dev/null || chown -R appuser /app",
                "USER appuser",
            ]
        )

    lines.extend(
        [
            "",
            "# متغیرهای محیطی",
            "ENV NODE_ENV=production"
            if lang in ["javascript", "typescript"]
            else "ENV PYTHONDONTWRITEBYTECODE=1",
        ]
    )

    lines.extend(
        [
            "",
            "# پورت",
            f"EXPOSE {port}",
        ]
    )

    if healthcheck and include_healthcheck:
        lines.extend(
            [
                "",
                "# Health check",
                "HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\",
                f"  CMD {healthcheck}",
            ]
        )

    lines.extend(
        [
            "",
            "# اجرای اپلیکیشن",
        ]
    )

    if cmd.startswith("./"):
        lines.append(f'ENTRYPOINT ["{cmd}"]')
    else:
        cmd_parts = cmd.split()
        cmd_json = json.dumps(cmd_parts)
        lines.append(f"CMD {cmd_json}")

    return "\n".join(lines)


@tool(args_schema=KubernetesGeneratorInput)
def generate_kubernetes_manifests(
    app_name: str,
    image: str,
    replicas: int = 3,
    port: int = 8000,
    service_type: str = "ClusterIP",
    cpu_request: str = "100m",
    cpu_limit: str = "500m",
    memory_request: str = "256Mi",
    memory_limit: str = "512Mi",
    enable_hpa: bool = True,
    hpa_min_replicas: int = 3,
    hpa_max_replicas: int = 10,
    hpa_cpu_target: int = 70,
    enable_ingress: bool = False,
    ingress_host: Optional[str] = None,
    ingress_tls: bool = True,
    enable_pdb: bool = True,
    env_vars: Optional[Dict[str, str]] = None,
    secret_refs: Optional[List[str]] = None,
    configmap_refs: Optional[List[str]] = None,
) -> str:
    """
    تولید مانیفست‌های کامل Kubernetes با بهترین روش‌ها.

    Generate complete Kubernetes manifests including:
    - Deployment with resource limits and probes
    - Service for internal/external access
    - HorizontalPodAutoscaler for auto-scaling
    - Ingress with TLS (optional)
    - PodDisruptionBudget for high availability
    """

    safe_name = re.sub(r"[^a-z0-9-]", "-", app_name.lower())
    manifests = []

    env_section = ""
    if env_vars:
        env_items = "\n".join(
            [
                f'        - name: {k}\n          value: "{v}"'
                for k, v in env_vars.items()
            ]
        )
        env_section = f"\n        env:\n{env_items}"

    if secret_refs:
        for secret in secret_refs:
            env_section += f"""
        envFrom:
        - secretRef:
            name: {secret}"""

    if configmap_refs:
        for cm in configmap_refs:
            env_section += f"""
        - configMapRef:
            name: {cm}"""

    deployment = f"""# Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {safe_name}
  labels:
    app: {safe_name}
    app.kubernetes.io/name: {safe_name}
    app.kubernetes.io/component: server
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {safe_name}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: {safe_name}
        app.kubernetes.io/name: {safe_name}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: {safe_name}
        image: {image}
        imagePullPolicy: Always
        ports:
        - containerPort: {port}
          name: http
        resources:
          requests:
            cpu: "{cpu_request}"
            memory: "{memory_request}"
          limits:
            cpu: "{cpu_limit}"
            memory: "{memory_limit}"
        livenessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: {port}
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 3{env_section}"""

    manifests.append(deployment)

    service = f"""---
# Service
apiVersion: v1
kind: Service
metadata:
  name: {safe_name}-service
  labels:
    app: {safe_name}
spec:
  selector:
    app: {safe_name}
  ports:
  - port: 80
    targetPort: {port}
    name: http
  type: {service_type}"""

    manifests.append(service)

    if enable_hpa:
        hpa = f"""---
# HorizontalPodAutoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {safe_name}-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {safe_name}
  minReplicas: {hpa_min_replicas}
  maxReplicas: {hpa_max_replicas}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {hpa_cpu_target}
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80"""
        manifests.append(hpa)

    if enable_pdb:
        pdb = f"""---
# PodDisruptionBudget
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {safe_name}-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: {safe_name}"""
        manifests.append(pdb)

    if enable_ingress and ingress_host:
        tls_section = ""
        if ingress_tls:
            tls_section = f"""
  tls:
  - hosts:
    - {ingress_host}
    secretName: {safe_name}-tls"""

        ingress = f"""---
# Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {safe_name}-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:{tls_section}
  rules:
  - host: {ingress_host}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {safe_name}-service
            port:
              number: 80"""
        manifests.append(ingress)

    return "\n".join(manifests)


@tool(args_schema=DockerComposeGeneratorInput)
def generate_docker_compose(
    project_name: str,
    services: List[Dict[str, Any]],
    networks: Optional[List[str]] = None,
    volumes: Optional[List[str]] = None,
) -> str:
    """
    تولید فایل docker-compose.yml برای محیط توسعه و تست.

    Generate docker-compose.yml for development and testing environments.
    """

    compose = {
        "version": "3.8",
        "services": {},
    }

    for svc in services:
        svc_name = svc.get("name", "app")
        svc_config = {
            "build": svc.get("build", "."),
            "ports": svc.get("ports", []),
        }

        if svc.get("environment"):
            svc_config["environment"] = svc["environment"]

        if svc.get("volumes"):
            svc_config["volumes"] = svc["volumes"]

        if svc.get("depends_on"):
            svc_config["depends_on"] = svc["depends_on"]

        if svc.get("image"):
            del svc_config["build"]
            svc_config["image"] = svc["image"]

        compose["services"][svc_name] = svc_config

    if networks:
        compose["networks"] = {net: {"driver": "bridge"} for net in networks}

    if volumes:
        compose["volumes"] = {vol: {} for vol in volumes}

    yaml_lines = [
        f"# docker-compose.yml for {project_name}",
        "# Generated by Kube-Tofu",
        "",
        "version: '3.8'",
        "",
        "services:",
    ]

    for svc_name, svc_config in compose["services"].items():
        yaml_lines.append(f"  {svc_name}:")
        for key, value in svc_config.items():
            if isinstance(value, list):
                yaml_lines.append(f"    {key}:")
                for item in value:
                    yaml_lines.append(f"      - {item}")
            elif isinstance(value, dict):
                yaml_lines.append(f"    {key}:")
                for k, v in value.items():
                    yaml_lines.append(f"      {k}: {v}")
            else:
                yaml_lines.append(f"    {key}: {value}")

    if networks:
        yaml_lines.extend(["", "networks:"])
        for net in networks:
            yaml_lines.append(f"  {net}:")
            yaml_lines.append("    driver: bridge")

    if volumes:
        yaml_lines.extend(["", "volumes:"])
        for vol in volumes:
            yaml_lines.append(f"  {vol}:")

    return "\n".join(yaml_lines)


def get_project_tools() -> List[BaseTool]:
    return [
        analyze_project_files,
        generate_optimized_dockerfile,
        generate_kubernetes_manifests,
        generate_docker_compose,
    ]
