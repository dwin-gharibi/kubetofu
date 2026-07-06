import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class IaCFormat(Enum):
    DOCKERFILE = "dockerfile"
    DOCKER_COMPOSE = "docker_compose"
    KUBERNETES = "kubernetes"
    HELM = "helm"
    TERRAFORM = "terraform"
    ANSIBLE = "ansible"
    VAGRANT = "vagrant"
    AUTO = "auto"


@dataclass
class GenerationResult:
    success: bool
    code: str
    format: str
    filename: str
    iterations: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEntry:
    id: str
    timestamp: str
    type: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentMemory:
    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self.entries: List[MemoryEntry] = []
        self.project_contexts: Dict[str, Dict] = {}
        self.generation_history: List[Dict] = []

    def add(self, entry_type: str, content: str, metadata: Optional[Dict] = None):
        entry = MemoryEntry(
            id=self._generate_id(content),
            timestamp=datetime.now().isoformat(),
            type=entry_type,
            content=content,
            metadata=metadata or {},
        )
        self.entries.append(entry)

        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def add_project_context(self, project_path: str, context: Dict):
        self.project_contexts[project_path] = context

    def add_generation(self, request: str, result: GenerationResult):
        self.generation_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "request": request,
                "success": result.success,
                "format": result.format,
                "iterations": result.iterations,
                "quality_score": result.quality_score,
            }
        )

    def get_relevant_context(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        query_words = set(query.lower().split())

        scored_entries = []
        for entry in self.entries:
            entry_words = set(entry.content.lower().split())
            overlap = len(query_words & entry_words)
            if overlap > 0:
                scored_entries.append((overlap, entry))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored_entries[:limit]]

    def get_conversation_history(self, limit: int = 10) -> List[MemoryEntry]:
        conversation_types = ["request", "response"]
        history = [e for e in self.entries if e.type in conversation_types]
        return history[-limit:]

    def clear(self):
        self.entries = []
        self.project_contexts = {}
        self.generation_history = []

    def _generate_id(self, content: str) -> str:
        return hashlib.md5(
            f"{content}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]


class DeepIaCAgent:
    FORMAT_PATTERNS = {
        IaCFormat.DOCKERFILE: ["docker", "container", "image", "dockerfile"],
        IaCFormat.DOCKER_COMPOSE: [
            "compose",
            "multi-container",
            "docker-compose",
            "services",
        ],
        IaCFormat.KUBERNETES: [
            "kubernetes",
            "k8s",
            "deployment",
            "pod",
            "service",
            "ingress",
        ],
        IaCFormat.HELM: ["helm", "chart", "values"],
        IaCFormat.TERRAFORM: [
            "terraform",
            "infrastructure",
            "aws",
            "cloud",
            "provider",
            "arvancloud",
        ],
        IaCFormat.ANSIBLE: ["ansible", "playbook", "configuration management"],
        IaCFormat.VAGRANT: [
            "vagrant",
            "vm",
            "virtual machine",
            "development environment",
        ],
    }

    FORMAT_FILENAMES = {
        IaCFormat.DOCKERFILE: "Dockerfile",
        IaCFormat.DOCKER_COMPOSE: "docker-compose.yml",
        IaCFormat.KUBERNETES: "deployment.yaml",
        IaCFormat.HELM: "values.yaml",
        IaCFormat.TERRAFORM: "main.tf",
        IaCFormat.ANSIBLE: "playbook.yml",
        IaCFormat.VAGRANT: "Vagrantfile",
    }

    def __init__(
        self,
        model: str = "gpt-4",
        max_iterations: int = 5,
        memory: Optional[AgentMemory] = None,
        verbose: bool = False,
    ):
        self.model = model
        self.max_iterations = max_iterations
        self.memory = memory or AgentMemory()
        self.verbose = verbose

        self._llm = None
        self._init_llm()

    def _init_llm(self):
        try:
            from agents.core.llm import LLMProvider

            self._llm = LLMProvider(model=self.model)
        except ImportError:
            self._llm = None

    def generate(
        self,
        request: str,
        format_hint: Optional[str] = None,
        project_context: Optional[Dict] = None,
    ) -> GenerationResult:
        self.memory.add("request", request, {"format_hint": format_hint})

        if format_hint:
            iac_format = IaCFormat(format_hint)
        else:
            iac_format = self._detect_format(request)

        if self.verbose:
            print(f"   Detected format: {iac_format.value}")

        context = self._build_context(request, project_context)

        best_result = None
        feedback = None

        for iteration in range(1, self.max_iterations + 1):
            if self.verbose:
                print(f"   Iteration {iteration}/{self.max_iterations}...")

            code = self._generate_code(request, iac_format, context, feedback)
            validation = self._validate_code(code, iac_format)

            if validation["valid"]:
                result = GenerationResult(
                    success=True,
                    code=code,
                    format=iac_format.value,
                    filename=self.FORMAT_FILENAMES.get(iac_format, "output.txt"),
                    iterations=iteration,
                    quality_score=validation.get("quality_score", 0.8),
                )

                self.memory.add(
                    "response",
                    code,
                    {
                        "format": iac_format.value,
                        "iterations": iteration,
                    },
                )
                self.memory.add_generation(request, result)

                return result
            else:
                feedback = validation.get("errors", [])
                best_result = GenerationResult(
                    success=False,
                    code=code,
                    format=iac_format.value,
                    filename=self.FORMAT_FILENAMES.get(iac_format, "output.txt"),
                    iterations=iteration,
                    errors=feedback,
                )

        return best_result or GenerationResult(
            success=False,
            code="",
            format=iac_format.value,
            filename="output.txt",
            iterations=self.max_iterations,
            errors=["Failed to generate valid code"],
        )

    def chat(
        self,
        message: str,
        project_context: Optional[Dict] = None,
    ) -> str:
        self.memory.add("request", message)

        if self._is_generation_request(message):
            result = self.generate(message, project_context=project_context)

            if result.success:
                response = f"I've generated the {result.format} configuration:\n\n```\n{result.code}\n```\n\nThe file has been saved as `{result.filename}`."
            else:
                response = f"I attempted to generate the configuration but encountered issues:\n{', '.join(result.errors)}\n\nHere's my best attempt:\n\n```\n{result.code}\n```"
        else:
            response = self._generate_chat_response(message, project_context)

        self.memory.add("response", response)

        return response

    def _detect_format(self, request: str) -> IaCFormat:
        request_lower = request.lower()

        scores = {}
        for format_type, patterns in self.FORMAT_PATTERNS.items():
            score = sum(1 for p in patterns if p in request_lower)
            if score > 0:
                scores[format_type] = score

        if scores:
            return max(scores, key=scores.get)

        return IaCFormat.KUBERNETES

    def _build_context(
        self,
        request: str,
        project_context: Optional[Dict],
    ) -> Dict[str, Any]:
        context = {
            "request": request,
            "timestamp": datetime.now().isoformat(),
        }

        if project_context:
            context["project"] = project_context.get("project_info", {})
            context["files"] = project_context.get("files", {})

        relevant = self.memory.get_relevant_context(request)
        if relevant:
            context["memory"] = [
                {"type": e.type, "content": e.content[:500]} for e in relevant
            ]

        return context

    def _generate_code(
        self,
        request: str,
        iac_format: IaCFormat,
        context: Dict,
        feedback: Optional[List[str]] = None,
    ) -> str:
        if self._llm:
            return self._generate_with_llm(request, iac_format, context, feedback)

        return self._generate_from_template(request, iac_format, context)

    def _generate_with_llm(
        self,
        request: str,
        iac_format: IaCFormat,
        context: Dict,
        feedback: Optional[List[str]] = None,
    ) -> str:
        prompt = self._build_prompt(request, iac_format, context, feedback)

        try:
            response = self._llm.generate(prompt)

            code = self._extract_code(response, iac_format)
            return code
        except Exception as e:
            if self.verbose:
                print(f"   LLM error: {e}")
            return self._generate_from_template(request, iac_format, context)

    def _build_prompt(
        self,
        request: str,
        iac_format: IaCFormat,
        context: Dict,
        feedback: Optional[List[str]] = None,
    ) -> str:
        prompt = f"""You are an expert Infrastructure-as-Code engineer. Generate {iac_format.value} configuration for the following request.

Request: {request}

"""

        if "project" in context:
            project = context["project"]
            prompt += f"""Project Context:
- Language: {project.get("language", "unknown")}
- Frameworks: {", ".join(project.get("frameworks", []))}
- Dependencies: {len(project.get("dependencies", []))} packages
- Ports: {", ".join(str(p.get("port")) for p in project.get("ports", []))}

"""

        if "files" in context:
            files = context["files"]
            if files:
                prompt += "Relevant project files:\n"
                for filename, content in list(files.items())[:5]:
                    if len(content) < 1000:
                        prompt += f"\n--- {filename} ---\n{content}\n"
                prompt += "\n"

        if feedback:
            prompt += f"""Previous attempt had these errors:
{chr(10).join(f"- {e}" for e in feedback)}

Please fix these issues in your generation.

"""

        prompt += f"""Generate ONLY the {iac_format.value} code. Do not include explanations.
The code should be production-ready with:
- Proper security configurations
- Health checks where applicable
- Resource limits where applicable
- Best practices for {iac_format.value}

Output:"""

        return prompt

    def _extract_code(self, response: str, iac_format: IaCFormat) -> str:
        code_block_pattern = r"```(?:\w+)?\n(.*?)```"
        matches = re.findall(code_block_pattern, response, re.DOTALL)

        if matches:
            return matches[0].strip()

        return response.strip()

    def _generate_from_template(
        self,
        request: str,
        iac_format: IaCFormat,
        context: Dict,
    ) -> str:
        project = context.get("project", {})

        if iac_format == IaCFormat.DOCKERFILE:
            return self._template_dockerfile(request, project)
        elif iac_format == IaCFormat.DOCKER_COMPOSE:
            return self._template_docker_compose(request, project)
        elif iac_format == IaCFormat.KUBERNETES:
            return self._template_kubernetes(request, project)
        elif iac_format == IaCFormat.TERRAFORM:
            return self._template_terraform(request, project)
        elif iac_format == IaCFormat.ANSIBLE:
            return self._template_ansible(request, project)
        else:
            return f"# @TODO: Template for {iac_format.value} not yet implemented\n# Request: {request}"

    def _template_dockerfile(self, request: str, project: Dict) -> str:
        language = project.get("language", "python")
        port = project.get("ports", [{"port": 8000}])[0].get("port", 8000)

        if language == "python":
            return f"""# Auto-generated Dockerfile
# Request: {request}

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE {port}

CMD ["python", "main.py"]
"""
        elif language in ["javascript", "typescript"]:
            return f"""# Auto-generated Dockerfile
# Request: {request}

FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
USER nodejs

EXPOSE {port}

CMD ["npm", "start"]
"""
        else:
            return f"""# Auto-generated Dockerfile
# Request: {request}

FROM ubuntu:22.04

WORKDIR /app
COPY . .

EXPOSE {port}

CMD ["bash"]
"""

    def _template_docker_compose(self, request: str, project: Dict) -> str:
        name = project.get("name", "app")
        port = project.get("ports", [{"port": 8000}])[0].get("port", 8000)
        databases = project.get("databases", [])

        compose = f'''# Auto-generated docker-compose.yml
# Request: {request}

version: "3.8"

services:
  {name}:
    build: .
    ports:
      - "{port}:{port}"
    environment:
      - PORT={port}
    restart: unless-stopped
'''

        if any(d.get("type") == "postgresql" for d in databases):
            compose += """
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:
"""

        return compose

    def _template_kubernetes(self, request: str, project: Dict) -> str:
        name = project.get("name", "app")
        port = project.get("ports", [{"port": 8000}])[0].get("port", 8000)

        return f"""# Auto-generated Kubernetes manifest
# Request: {request}

apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: {name}:latest
        ports:
        - containerPort: {port}
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
  - port: {port}
    targetPort: {port}
"""

    def _template_terraform(self, request: str, project: Dict) -> str:
        return f"""# Auto-generated Terraform configuration
# Request: {request}

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.region
}}

variable "region" {{
  default = "us-west-2"
}}

# @TODO: Add resources based on request
# Request was: {request}
"""

    def _template_ansible(self, request: str, project: Dict) -> str:
        return f"""# Auto-generated Ansible playbook
# Request: {request}

---
- name: Deploy application
  hosts: all
  become: yes
  
  tasks:
    - name: Update packages
      apt:
        update_cache: yes
        upgrade: yes
    
    # @TODO: Add tasks based on request
    # Request was: {request}
"""

    def _validate_code(self, code: str, iac_format: IaCFormat) -> Dict:
        try:
            from evaluation.validators import validate_iac

            format_map = {
                IaCFormat.DOCKERFILE: "dockerfile",
                IaCFormat.DOCKER_COMPOSE: "docker_compose",
                IaCFormat.KUBERNETES: "kubernetes",
                IaCFormat.TERRAFORM: "terraform",
                IaCFormat.ANSIBLE: "ansible",
                IaCFormat.HELM: "helm",
                IaCFormat.VAGRANT: "vagrant",
            }

            result = validate_iac(code, format_map.get(iac_format, "unknown"))

            return {
                "valid": result.valid,
                "errors": [e.message for e in result.errors],
                "warnings": [w.message for w in result.warnings],
                "quality_score": 0.8 if result.valid else 0.3,
            }
        except ImportError:
            return self._basic_validate(code, iac_format)

    def _basic_validate(self, code: str, iac_format: IaCFormat) -> Dict:
        if not code or len(code.strip()) < 10:
            return {"valid": False, "errors": ["Generated code is empty or too short"]}

        if iac_format == IaCFormat.DOCKERFILE:
            if "FROM" not in code:
                return {
                    "valid": False,
                    "errors": ["Dockerfile missing FROM instruction"],
                }

        elif iac_format == IaCFormat.KUBERNETES:
            if "apiVersion" not in code or "kind" not in code:
                return {
                    "valid": False,
                    "errors": ["Kubernetes manifest missing apiVersion or kind"],
                }

        elif iac_format == IaCFormat.TERRAFORM:
            if code.count("{") != code.count("}"):
                return {"valid": False, "errors": ["Unbalanced braces in Terraform"]}

        return {"valid": True, "errors": [], "quality_score": 0.7}

    def _is_generation_request(self, message: str) -> bool:
        generation_keywords = [
            "create",
            "generate",
            "make",
            "write",
            "build",
            "deploy",
            "setup",
            "configure",
            "add",
            "implement",
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in generation_keywords)

    def _generate_chat_response(
        self,
        message: str,
        project_context: Optional[Dict],
    ) -> str:
        message_lower = message.lower()

        if "help" in message_lower or "what can you" in message_lower:
            return """I'm Kube-Tofu, a deep agentic IaC assistant. I can help you with:

1. **Generate IaC**: "Create a Dockerfile for a Python Flask app"
2. **Analyze projects**: "What does this project need to deploy?"
3. **Explain concepts**: "How does Kubernetes deployment work?"
4. **Optimize configs**: "How can I improve this Dockerfile?"
5. **Debug issues**: "Why is my pod not starting?"

Just describe what you need, and I'll help you create the appropriate infrastructure code."""

        if project_context and ("project" in message_lower or "what" in message_lower):
            project = project_context.get("project_info", {})
            return f"""Based on your project context:

- **Language**: {project.get("language", "Unknown")}
- **Frameworks**: {", ".join(project.get("frameworks", ["None detected"]))}
- **Dependencies**: {len(project.get("dependencies", []))} packages
- **Detected databases**: {", ".join(d.get("type", "unknown") for d in project.get("databases", [])) or "None"}

Would you like me to generate deployment configurations for this project?"""

        return """I understand you're asking about infrastructure. Could you be more specific about what you'd like to create or configure?

For example:
- "Create a Dockerfile for my Python app"
- "Generate Kubernetes manifests for a web service"
- "Create Terraform for AWS infrastructure"

I can also analyze your project directory if you provide the path with `context /path/to/project`."""
