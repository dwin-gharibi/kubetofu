import logging
import operator
import json
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence, TypedDict

from django.conf import settings

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from agents.langchain.tools import create_all_tools

logger = logging.getLogger(__name__)


class ProjectContext(TypedDict, total=False):
    project_name: str
    language: str
    framework: str
    service_type: str
    databases: List[str]
    has_dockerfile: bool
    has_kubernetes: bool
    has_terraform: bool
    files: List[Dict[str, str]]
    ports: List[int]
    env_vars: List[str]


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    project: Optional[ProjectContext]
    plan: Optional[str]
    current_step: int
    total_steps: int
    artifacts: Dict[str, str]
    validation_errors: List[str]
    iteration_count: int
    max_iterations: int
    requires_approval: bool
    approval_request: Optional[str]
    is_approved: bool
    session_id: str
    agent_name: str
    start_time: str


class GenerateDockerfileInput(BaseModel):
    language: str = Field(
        description="Programming language (python, javascript, go, etc.)"
    )
    framework: Optional[str] = Field(
        default=None, description="Framework if any (django, fastapi, express, etc.)"
    )
    port: int = Field(default=8000, description="Application port")
    multi_stage: bool = Field(
        default=True, description="Use multi-stage build for smaller image"
    )


@tool(args_schema=GenerateDockerfileInput)
def generate_dockerfile(
    language: str,
    framework: Optional[str] = None,
    port: int = 8000,
    multi_stage: bool = True,
) -> str:
    templates = {
        "python": {
            "base": "python:3.11-slim",
            "fastapi": """# Multi-stage build for FastAPI
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:{port}/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"]""",
            "django": """# Multi-stage build for Django
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
ENV DJANGO_SETTINGS_MODULE=config.settings.production
EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:{port}/health || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:{port}", "--workers", "4", "config.wsgi:application"]""",
            "flask": """# Multi-stage build for Flask
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:{port}/health || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:{port}", "--workers", "4", "app:app"]""",
            "default": """# Python application
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE {port}
CMD ["python", "main.py"]""",
        },
        "javascript": {
            "base": "node:20-alpine",
            "nextjs": """# Multi-stage build for Next.js
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE {port}
ENV PORT={port}
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost:{port}/api/health || exit 1
CMD ["node", "server.js"]""",
            "express": """# Multi-stage build for Express.js
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY . .
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
USER nodejs
ENV NODE_ENV=production
EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost:{port}/health || exit 1
CMD ["node", "index.js"]""",
            "default": """# Node.js application
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
USER nodejs
ENV NODE_ENV=production
EXPOSE {port}
CMD ["node", "index.js"]""",
        },
        "go": {
            "base": "golang:1.21-alpine",
            "default": """# Multi-stage build for Go
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main .

FROM scratch
WORKDIR /app
COPY --from=builder /app/main .
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE {port}
ENTRYPOINT ["./main"]""",
        },
        "typescript": {
            "base": "node:20-alpine",
            "default": """# Multi-stage build for TypeScript
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY package*.json ./
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
USER nodejs
ENV NODE_ENV=production
EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost:{port}/health || exit 1
CMD ["node", "dist/index.js"]""",
        },
    }

    lang_templates = templates.get(language.lower(), templates["python"])
    template = lang_templates.get(
        framework.lower() if framework else "default", lang_templates.get("default", "")
    )

    if not template:
        template = """FROM alpine:latest
WORKDIR /app
COPY . .
EXPOSE {port}
CMD ["./start.sh"]"""

    return template.format(port=port)


class GenerateKubernetesInput(BaseModel):
    app_name: str = Field(description="Application name")
    image: str = Field(description="Docker image name")
    replicas: int = Field(default=3, description="Number of replicas")
    port: int = Field(default=8000, description="Container port")
    resources: Optional[Dict[str, str]] = Field(
        default=None, description="Resource limits"
    )
    ingress_host: Optional[str] = Field(default=None, description="Ingress hostname")


@tool(args_schema=GenerateKubernetesInput)
def generate_kubernetes(
    app_name: str,
    image: str,
    replicas: int = 3,
    port: int = 8000,
    resources: Optional[Dict[str, str]] = None,
    ingress_host: Optional[str] = None,
) -> str:
    safe_name = app_name.lower().replace("_", "-").replace(" ", "-")

    if not resources:
        resources = {
            "requests_memory": "256Mi",
            "requests_cpu": "100m",
            "limits_memory": "512Mi",
            "limits_cpu": "500m",
        }

    manifests = f"""# Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {safe_name}
  labels:
    app: {safe_name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {safe_name}
  template:
    metadata:
      labels:
        app: {safe_name}
    spec:
      containers:
      - name: {safe_name}
        image: {image}
        ports:
        - containerPort: {port}
        resources:
          requests:
            memory: "{resources.get("requests_memory", "256Mi")}"
            cpu: "{resources.get("requests_cpu", "100m")}"
          limits:
            memory: "{resources.get("limits_memory", "512Mi")}"
            cpu: "{resources.get("limits_cpu", "500m")}"
        livenessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: {port}
          initialDelaySeconds: 5
          periodSeconds: 5
---
# Service
apiVersion: v1
kind: Service
metadata:
  name: {safe_name}-service
spec:
  selector:
    app: {safe_name}
  ports:
  - port: 80
    targetPort: {port}
  type: ClusterIP
---
# HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {safe_name}-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {safe_name}
  minReplicas: {replicas}
  maxReplicas: {replicas * 3}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70"""

    if ingress_host:
        manifests += f"""
---
# Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {safe_name}-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - {ingress_host}
    secretName: {safe_name}-tls
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

    return manifests


class GenerateTerraformInput(BaseModel):
    provider: str = Field(description="Cloud provider (aws, gcp, azure, arvancloud)")
    resource_type: str = Field(
        description="Resource type to create (vpc, ec2, rds, k8s, etc.)"
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Resource configuration"
    )


@tool(args_schema=GenerateTerraformInput)
def generate_terraform(
    provider: str,
    resource_type: str,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    config = config or {}

    if provider.lower() == "aws":
        if resource_type == "vpc":
            return f"""# AWS VPC Configuration
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

variable "environment" {{
  default = "{config.get("environment", "production")}"
}}

variable "vpc_cidr" {{
  default = "{config.get("cidr", "10.0.0.0/16")}"
}}

# VPC
resource "aws_vpc" "main" {{
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {{
    Name        = "${{var.environment}}-vpc"
    Environment = var.environment
    ManagedBy   = "terraform"
  }}
}}

# Public Subnets
resource "aws_subnet" "public" {{
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {{
    Name = "${{var.environment}}-public-${{count.index + 1}}"
    Type = "public"
  }}
}}

# Private Subnets
resource "aws_subnet" "private" {{
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {{
    Name = "${{var.environment}}-private-${{count.index + 1}}"
    Type = "private"
  }}
}}

# Internet Gateway
resource "aws_internet_gateway" "main" {{
  vpc_id = aws_vpc.main.id

  tags = {{
    Name = "${{var.environment}}-igw"
  }}
}}

# NAT Gateway
resource "aws_eip" "nat" {{
  domain = "vpc"
}}

resource "aws_nat_gateway" "main" {{
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {{
    Name = "${{var.environment}}-nat"
  }}

  depends_on = [aws_internet_gateway.main]
}}

# Data source for AZs
data "aws_availability_zones" "available" {{
  state = "available"
}}

# Outputs
output "vpc_id" {{
  value = aws_vpc.main.id
}}

output "public_subnets" {{
  value = aws_subnet.public[*].id
}}

output "private_subnets" {{
  value = aws_subnet.private[*].id
}}"""
        elif resource_type == "rds":
            return f"""# AWS RDS PostgreSQL
resource "aws_db_instance" "main" {{
  identifier        = "{config.get("name", "mydb")}"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "{config.get("instance_class", "db.t3.medium")}"
  allocated_storage = {config.get("storage", 20)}
  
  db_name  = "{config.get("db_name", "myapp")}"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  multi_az               = {str(config.get("multi_az", True)).lower()}
  storage_encrypted      = true
  deletion_protection    = true
  
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"
  
  tags = {{
    Name        = "{config.get("name", "mydb")}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }}
}}

variable "db_username" {{
  description = "Database admin username"
  type        = string
  sensitive   = true
}}

variable "db_password" {{
  description = "Database admin password"
  type        = string
  sensitive   = true
}}"""

    elif provider.lower() == "arvancloud":
        return f"""# ArvanCloud Configuration
terraform {{
  required_providers {{
    arvan = {{
      source  = "arvancloud/arvan"
      version = "~> 1.0"
    }}
  }}
}}

provider "arvan" {{
  api_key = var.arvan_api_key
  region  = "{config.get("region", "ir-thr-at1")}"
}}

variable "arvan_api_key" {{
  description = "ArvanCloud API Key"
  type        = string
  sensitive   = true
}}

# Server
resource "arvan_iaas_server" "main" {{
  name        = "{config.get("name", "my-server")}"
  flavor_id   = "{config.get("flavor", "g2-2-1-0")}"
  image_id    = "{config.get("image", "debian-12")}"
  
  network_id  = arvan_iaas_network.main.id
  
  security_groups = [arvan_iaas_security_group.main.id]
  
  ssh_key_name = var.ssh_key_name
}}

variable "ssh_key_name" {{
  description = "SSH key name"
  type        = string
}}"""

    return f"# Terraform configuration for {provider}/{resource_type}\n# Configuration: {json.dumps(config)}"


class AnalyzeProjectInput(BaseModel):
    files: List[Dict[str, str]] = Field(
        description="List of files with name, path, and content"
    )


@tool(args_schema=AnalyzeProjectInput)
def analyze_project_structure(files: List[Dict[str, str]]) -> str:
    analysis = {
        "language": "unknown",
        "framework": None,
        "databases": [],
        "has_dockerfile": False,
        "has_kubernetes": False,
        "has_terraform": False,
        "ports": [],
        "dependencies": [],
        "suggestions": [],
    }

    filenames = [f.get("name", "").lower() for f in files]

    analysis["has_dockerfile"] = any("dockerfile" in fn for fn in filenames)
    analysis["has_kubernetes"] = any(
        fn.endswith((".yaml", ".yml"))
        and any(kw in fn for kw in ["k8s", "kubernetes", "deployment", "service"])
        for fn in filenames
    )
    analysis["has_terraform"] = any(fn.endswith(".tf") for fn in filenames)

    for f in files:
        name = f.get("name", "").lower()
        content = f.get("content", "")

        if name == "requirements.txt":
            analysis["language"] = "python"
            if "django" in content.lower():
                analysis["framework"] = "django"
            elif "fastapi" in content.lower():
                analysis["framework"] = "fastapi"
            elif "flask" in content.lower():
                analysis["framework"] = "flask"

        elif name in ["pyproject.toml", "setup.py"]:
            analysis["language"] = "python"

        elif name == "package.json":
            analysis["language"] = "javascript"
            if "typescript" in content.lower():
                analysis["language"] = "typescript"
            if '"next"' in content:
                analysis["framework"] = "nextjs"
            elif '"express"' in content:
                analysis["framework"] = "express"
            elif '"@nestjs/core"' in content:
                analysis["framework"] = "nestjs"

        elif name == "go.mod":
            analysis["language"] = "go"

        if any(db in content.lower() for db in ["postgresql", "postgres", "pg_"]):
            if "postgresql" not in analysis["databases"]:
                analysis["databases"].append("postgresql")
        if any(db in content.lower() for db in ["mysql", "mariadb"]):
            if "mysql" not in analysis["databases"]:
                analysis["databases"].append("mysql")
        if "mongodb" in content.lower() or "mongo" in content.lower():
            if "mongodb" not in analysis["databases"]:
                analysis["databases"].append("mongodb")
        if "redis" in content.lower():
            if "redis" not in analysis["databases"]:
                analysis["databases"].append("redis")

        import re

        port_matches = re.findall(r"(?:PORT|port|EXPOSE)[:\s=]+(\d{4,5})", content)
        for port in port_matches:
            p = int(port)
            if 1000 < p < 65536 and p not in analysis["ports"]:
                analysis["ports"].append(p)

    if not analysis["has_dockerfile"]:
        analysis["suggestions"].append("ایجاد Dockerfile برای containerization")
    if not analysis["has_kubernetes"]:
        analysis["suggestions"].append("ایجاد مانیفست‌های Kubernetes برای استقرار")
    if analysis["databases"] and not analysis["has_terraform"]:
        analysis["suggestions"].append("ایجاد Terraform برای زیرساخت دیتابیس")

    return json.dumps(analysis, ensure_ascii=False, indent=2)


def create_deep_agent_graph(
    model_provider: str = "anthropic",
    model_name: str = "claude-sonnet-4-20250514",
) -> StateGraph:
    if model_provider == "anthropic":
        llm = ChatAnthropic(
            model=model_name,
            temperature=0.1,
            max_tokens=8192,
            anthropic_api_key=settings.LLM_SETTINGS.get("ANTHROPIC_API_KEY"),
        )
    else:
        llm = ChatOpenAI(
            model=model_name,
            temperature=0.1,
            max_tokens=8192,
            openai_api_key=settings.LLM_SETTINGS.get("OPENAI_API_KEY"),
        )

    try:
        from agents.langchain.project_tools import get_project_tools

        project_tools = get_project_tools()
    except ImportError:
        project_tools = [
            generate_dockerfile,
            generate_kubernetes,
            generate_terraform,
            analyze_project_structure,
        ]

    infra_tools = create_all_tools()
    all_tools = project_tools + infra_tools

    seen_names = set()
    unique_tools = []
    for tool in all_tools:
        if tool.name not in seen_names:
            seen_names.add(tool.name)
            unique_tools.append(tool)
    all_tools = unique_tools

    llm_with_tools = llm.bind_tools(all_tools)

    system_prompt = """شما عامل هوشمند کیوب‌توفو هستید - یک متخصص زیرساخت به عنوان کد (IaC).

## وظایف شما
1. تحلیل پروژه‌های نرم‌افزاری و شناسایی نیازهای زیرساختی
2. تولید Dockerfile بهینه برای هر زبان و فریم‌ورک
3. ایجاد مانیفست‌های Kubernetes با بهترین روش‌ها
4. پیکربندی Terraform برای زیرساخت‌های ابری
5. بررسی امنیتی و پیشنهادات بهبود

## قواعد
- همیشه از ابزارهای موجود استفاده کنید
- کد قابل استفاده و بهینه تولید کنید
- توضیحات فارسی ارائه دهید
- امنیت را در اولویت قرار دهید
- برای عملیات حساس تایید بگیرید

## زمینه پروژه
{project_context}

You are KubeTofu AI Agent - an Infrastructure as Code expert. Generate optimized, production-ready code."""

    def analyze_node(state: AgentState) -> AgentState:
        project = state.get("project", {})
        messages = state["messages"]

        context_parts = []
        if project:
            if project.get("project_name"):
                context_parts.append(f"پروژه: {project['project_name']}")
            if project.get("language"):
                context_parts.append(f"زبان: {project['language']}")
            if project.get("framework"):
                context_parts.append(f"فریم‌ورک: {project['framework']}")
            if project.get("databases"):
                context_parts.append(f"دیتابیس‌ها: {', '.join(project['databases'])}")

        project_context = (
            "\n".join(context_parts) if context_parts else "پروژه‌ای انتخاب نشده"
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt.format(project_context=project_context)),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        chain = prompt | llm_with_tools
        response = chain.invoke({"messages": messages})

        return {
            "messages": [response],
            "current_step": state.get("current_step", 0) + 1,
        }

    def tool_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        last_message = messages[-1]

        outputs = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            tool = next((t for t in all_tools if t.name == tool_name), None)
            if tool:
                try:
                    result = tool.invoke(tool_args)

                    if tool_name in [
                        "generate_dockerfile",
                        "generate_kubernetes",
                        "generate_terraform",
                    ]:
                        artifacts = state.get("artifacts", {})
                        artifact_name = {
                            "generate_dockerfile": "Dockerfile",
                            "generate_kubernetes": "kubernetes.yaml",
                            "generate_terraform": "main.tf",
                        }.get(tool_name, f"{tool_name}_output.txt")
                        artifacts[artifact_name] = result
                        state["artifacts"] = artifacts

                except Exception as e:
                    result = f"Error: {str(e)}"
            else:
                result = f"Tool {tool_name} not found"

            outputs.append(
                ToolMessage(
                    content=str(result),
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                )
            )

        return {"messages": outputs}

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        messages = state["messages"]
        last_message = messages[-1]

        if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
            return "end"

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", analyze_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )
    workflow.add_edge("tools", "agent")

    return workflow


class DeepAgentLangGraph:
    def __init__(
        self,
        session_id: str,
        model_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-20250514",
    ):
        self.session_id = session_id
        self.model_provider = model_provider
        self.model_name = model_name

        workflow = create_deep_agent_graph(model_provider, model_name)

        self.memory = MemorySaver()
        self.graph = workflow.compile(checkpointer=self.memory)

    async def run(
        self,
        message: str,
        project: Optional[ProjectContext] = None,
    ) -> Dict[str, Any]:
        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "project": project,
            "plan": None,
            "current_step": 0,
            "total_steps": 0,
            "artifacts": {},
            "validation_errors": [],
            "iteration_count": 0,
            "max_iterations": 10,
            "requires_approval": False,
            "approval_request": None,
            "is_approved": False,
            "session_id": self.session_id,
            "agent_name": "KubeTofuAgent",
            "start_time": datetime.utcnow().isoformat(),
        }

        config = {"configurable": {"thread_id": self.session_id}}

        result = await self.graph.ainvoke(initial_state, config)

        messages = result.get("messages", [])
        response = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                response = msg.content
                break

        return {
            "response": response,
            "artifacts": result.get("artifacts", {}),
            "session_id": self.session_id,
        }

    async def stream(
        self,
        message: str,
        project: Optional[ProjectContext] = None,
    ):
        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "project": project,
            "plan": None,
            "current_step": 0,
            "total_steps": 0,
            "artifacts": {},
            "validation_errors": [],
            "iteration_count": 0,
            "max_iterations": 10,
            "requires_approval": False,
            "approval_request": None,
            "is_approved": False,
            "session_id": self.session_id,
            "agent_name": "KubeTofuAgent",
            "start_time": datetime.utcnow().isoformat(),
        }

        config = {"configurable": {"thread_id": self.session_id}}

        async for event in self.graph.astream_events(
            initial_state, config, version="v1"
        ):
            yield event
