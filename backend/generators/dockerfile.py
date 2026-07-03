import logging
import re
from typing import List, Tuple

from generators.base import (
    BaseGenerator,
    ErrorCategory,
    GenerationContext,
    GenerationResult,
    IaCType,
    ValidationError,
)

logger = logging.getLogger(__name__)


DOCKERFILE_BEST_PRACTICES = {
    "use_specific_tags": "Use specific image tags instead of 'latest'",
    "minimize_layers": "Combine RUN commands to minimize layers",
    "order_instructions": "Order instructions from least to most frequently changing",
    "use_multi_stage": "Use multi-stage builds to reduce image size",
    "non_root_user": "Run as non-root user for security",
    "use_healthcheck": "Add HEALTHCHECK instruction",
    "specify_workdir": "Specify WORKDIR instead of using cd",
    "use_copy_not_add": "Prefer COPY over ADD unless extracting archives",
    "pin_versions": "Pin package versions for reproducibility",
    "clean_cache": "Clean package manager caches in same layer",
}

BASE_IMAGES = {
    "python": "python:3.11-slim",
    "node": "node:20-alpine",
    "nodejs": "node:20-alpine",
    "java": "eclipse-temurin:21-jdk-alpine",
    "go": "golang:1.22-alpine",
    "rust": "rust:1.75-alpine",
    "ruby": "ruby:3.3-alpine",
    "php": "php:8.3-fpm-alpine",
    "dotnet": "mcr.microsoft.com/dotnet/sdk:8.0-alpine",
    "nginx": "nginx:alpine",
    "postgres": "postgres:16-alpine",
    "redis": "redis:7-alpine",
    "mongodb": "mongo:7",
}


class DockerfileGenerator(BaseGenerator):
    iac_type = IaCType.DOCKERFILE

    def _setup_validators(self) -> None:
        self.validators = [
            self._validate_security,
            self._validate_best_practices,
        ]

    def generate(self, context: GenerationContext) -> GenerationResult:
        import time

        start_time = time.time()

        language = self._detect_language(context)
        base_image = self._select_base_image(language, context)
        use_multi_stage = self._should_use_multi_stage(context)

        if use_multi_stage:
            dockerfile = self._generate_multi_stage(base_image, language, context)
        else:
            dockerfile = self._generate_simple(base_image, language, context)

        result = GenerationResult.create(
            iac_type=self.iac_type,
            code=dockerfile,
            generation_time=time.time() - start_time,
        )

        result.files = {
            "Dockerfile": dockerfile,
            ".dockerignore": self._generate_dockerignore(language),
        }

        return result

    def validate_syntax(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []
        lines = code.strip().split("\n")

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

        has_from = False
        line_num = 0

        for line in lines:
            line_num += 1
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            while stripped.endswith("\\") and line_num < len(lines):
                line_num += 1
                stripped = stripped[:-1] + lines[line_num - 1].strip()

            parts = stripped.split(None, 1)
            if not parts:
                continue

            instruction = parts[0].upper()

            if instruction not in valid_instructions:
                if instruction not in ("AS",) and not instruction.startswith("--"):
                    errors.append(
                        ValidationError(
                            category=ErrorCategory.SYNTAX_INVALID_TOKEN,
                            message=f"Unknown instruction: {instruction}",
                            line=line_num,
                            suggestion=f"Valid instructions: {', '.join(sorted(valid_instructions))}",
                        )
                    )

            if instruction == "FROM":
                has_from = True

        if not has_from:
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="Dockerfile must start with FROM instruction",
                    suggestion="Add 'FROM <base-image>' at the beginning",
                )
            )

        return len(errors) == 0, errors

    def validate_semantics(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []
        lines = code.strip().split("\n")

        exposed_ports = []
        defined_args = set()

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            parts = stripped.split(None, 1)
            if not parts:
                continue

            instruction = parts[0].upper()
            args = parts[1] if len(parts) > 1 else ""

            if instruction == "EXPOSE":
                for port in args.split():
                    port_num = port.split("/")[0]
                    if port_num.isdigit():
                        port_int = int(port_num)
                        if port_int < 1 or port_int > 65535:
                            errors.append(
                                ValidationError(
                                    category=ErrorCategory.CONFIG_INVALID_VALUE,
                                    message=f"Invalid port number: {port_num}",
                                    line=i,
                                )
                            )
                        exposed_ports.append(port_int)

            if instruction == "ARG":
                arg_name = args.split("=")[0].strip()
                defined_args.add(arg_name)

            for match in re.findall(r"\$\{?([A-Z_][A-Z0-9_]*)\}?", args):
                if match not in defined_args:
                    pass

            if instruction == "FROM" and "$" in args:
                for match in re.findall(r"\$\{?([A-Z_][A-Z0-9_]*)\}?", args):
                    if match not in defined_args:
                        errors.append(
                            ValidationError(
                                category=ErrorCategory.SEMANTIC_UNDEFINED_REFERENCE,
                                message=f"ARG '{match}' used in FROM but not defined before",
                                line=i,
                                suggestion=f"Add 'ARG {match}' before this FROM instruction",
                            )
                        )

        return len(errors) == 0, errors

    def _validate_security(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "USER" not in code.upper():
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="No USER instruction found - container will run as root",
                    severity="warning",
                    suggestion="Add 'USER nonroot' or similar to run as non-root user",
                )
            )

        if re.search(r"FROM\s+\S+:latest", code, re.IGNORECASE):
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_INVALID_VALUE,
                    message="Using 'latest' tag is not recommended",
                    severity="warning",
                    suggestion="Use specific version tags for reproducibility",
                )
            )

        secret_patterns = ["PASSWORD", "SECRET", "API_KEY", "TOKEN", "PRIVATE"]
        for pattern in secret_patterns:
            if re.search(rf"ENV\s+[^=]*{pattern}[^=]*=", code, re.IGNORECASE):
                errors.append(
                    ValidationError(
                        category=ErrorCategory.CONFIG_INVALID_VALUE,
                        message=f"Potential secret in ENV instruction ({pattern})",
                        severity="warning",
                        suggestion="Use build arguments or secrets management instead",
                    )
                )

        return len(errors) == 0, errors

    def _validate_best_practices(self, code: str) -> Tuple[bool, List[ValidationError]]:
        errors = []

        if "HEALTHCHECK" not in code.upper():
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_MISSING_REQUIRED,
                    message="No HEALTHCHECK instruction found",
                    severity="info",
                    suggestion="Add HEALTHCHECK for container orchestration",
                )
            )

        if re.search(r"^ADD\s+(?!https?://)", code, re.MULTILINE | re.IGNORECASE):
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_DEPRECATED,
                    message="ADD used for local files - prefer COPY",
                    severity="info",
                    suggestion="Use COPY for local files, ADD for URL/archive extraction",
                )
            )

        apt_runs = len(re.findall(r"RUN\s+apt-get", code, re.IGNORECASE))
        if apt_runs > 1:
            errors.append(
                ValidationError(
                    category=ErrorCategory.CONFIG_INVALID_VALUE,
                    message="Multiple RUN apt-get commands create extra layers",
                    severity="info",
                    suggestion="Combine apt-get commands with && to reduce layers",
                )
            )

        return True, errors

    def _detect_language(self, context: GenerationContext) -> str:
        request = context.natural_language_request.lower()

        for lang in BASE_IMAGES.keys():
            if lang in request:
                return lang

        for service in context.services:
            service_lower = service.lower()
            for lang in BASE_IMAGES.keys():
                if lang in service_lower:
                    return lang

        return "python"

    def _select_base_image(self, language: str, context: GenerationContext) -> str:
        return BASE_IMAGES.get(language, "alpine:3.19")

    def _should_use_multi_stage(self, context: GenerationContext) -> bool:
        compiled_langs = {"go", "rust", "java", "dotnet"}
        language = self._detect_language(context)
        return language in compiled_langs

    def _generate_multi_stage(
        self, base_image: str, language: str, context: GenerationContext
    ) -> str:
        templates = {
            "go": self._go_multi_stage,
            "rust": self._rust_multi_stage,
            "java": self._java_multi_stage,
            "dotnet": self._dotnet_multi_stage,
        }

        generator = templates.get(language, self._generic_multi_stage)
        return generator(base_image, context)

    def _generate_simple(
        self, base_image: str, language: str, context: GenerationContext
    ) -> str:
        templates = {
            "python": self._python_dockerfile,
            "node": self._node_dockerfile,
            "nodejs": self._node_dockerfile,
        }

        generator = templates.get(language, self._generic_dockerfile)
        return generator(base_image, context)

    def _python_dockerfile(self, base_image: str, context: GenerationContext) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

FROM {base_image} AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM {base_image}

WORKDIR /app

RUN useradd -m -u 1000 appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

    def _node_dockerfile(self, base_image: str, context: GenerationContext) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

FROM {base_image} AS builder

WORKDIR /app

COPY package*.json ./

RUN npm ci --only=production

FROM {base_image}

WORKDIR /app

RUN addgroup -g 1001 -S nodejs && \\
    adduser -S appuser -u 1001 -G nodejs

COPY --from=builder /app/node_modules ./node_modules

COPY --chown=appuser:nodejs . .

ENV NODE_ENV=production
ENV PORT=3000

USER appuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "server.js"]
"""

    def _go_multi_stage(self, base_image: str, context: GenerationContext) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

FROM {base_image} AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/main .

FROM scratch

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /app/main /main

USER 65534:65534

EXPOSE 8080

ENTRYPOINT ["/main"]
"""

    def _rust_multi_stage(self, base_image: str, context: GenerationContext) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

FROM {base_image} AS builder

WORKDIR /app

RUN cargo new --bin app
WORKDIR /app/app

COPY Cargo.toml Cargo.lock ./

RUN cargo build --release && rm src/*.rs target/release/app*

COPY src ./src

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

COPY --from=builder /app/app/target/release/app /usr/local/bin/app

RUN chown appuser:appuser /usr/local/bin/app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["app"]
"""

    def _java_multi_stage(self, base_image: str, context: GenerationContext) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

FROM {base_image} AS builder

WORKDIR /app

COPY pom.xml mvnw ./
COPY .mvn .mvn

RUN ./mvnw dependency:go-offline

COPY src src

RUN ./mvnw package -DskipTests

FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

RUN addgroup -g 1001 -S javauser && \\
    adduser -S javauser -u 1001 -G javauser

COPY --from=builder /app/target/*.jar app.jar

RUN chown -R javauser:javauser /app

USER javauser

ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
"""

    def _dotnet_multi_stage(self, base_image: str, context: GenerationContext) -> str:
        return f"""# Auto-generated by Kube-Tofu
# {context.natural_language_request}

FROM {base_image} AS builder

WORKDIR /app

COPY *.csproj ./
RUN dotnet restore

COPY . .

RUN dotnet publish -c Release -o out

FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine

WORKDIR /app

RUN addgroup -g 1001 -S dotnetuser && \\
    adduser -S dotnetuser -u 1001 -G dotnetuser

COPY --from=builder /app/out .

RUN chown -R dotnetuser:dotnetuser /app

USER dotnetuser

ENV ASPNETCORE_URLS=http://+:8080
ENV DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

ENTRYPOINT ["dotnet", "App.dll"]
"""

    def _generic_dockerfile(self, base_image: str, context: GenerationContext) -> str:
        return f"""# Auto-generated by Kube-Tofu

FROM {base_image}

WORKDIR /app

RUN apk add --no-cache \\
    curl \\
    ca-certificates

COPY . .

RUN addgroup -g 1001 -S appgroup && \\
    adduser -S appuser -u 1001 -G appgroup && \\
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["./app"]
"""

    def _generic_multi_stage(self, base_image: str, context: GenerationContext) -> str:
        return self._generic_dockerfile(base_image, context)

    def _generate_dockerignore(self, language: str) -> str:
        common = """# Auto-generated by Kube-Tofu
.git
.gitignore

.idea
.vscode
*.swp
*.swo

*.md
docs/

.github
.gitlab-ci.yml
Jenkinsfile

Dockerfile*
docker-compose*
.docker

tests/
test/
*_test.*
*.test.*
coverage/
.coverage

.env*
*.env
"""

        language_specific = {
            "python": """
__pycache__
*.py[cod]
*$py.class
.Python
venv/
.venv/
*.egg-info/
.pytest_cache/
.mypy_cache/
""",
            "node": """
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
""",
            "go": """
vendor/
*.exe
*.exe~
*.dll
*.so
*.dylib
""",
            "rust": """
target/
Cargo.lock
""",
            "java": """
target/
*.class
*.jar
*.war
.gradle/
build/
""",
        }

        return common + language_specific.get(language, "")
