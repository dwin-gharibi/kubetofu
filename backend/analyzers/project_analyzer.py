import os
import re
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    JAVA = "java"
    RUST = "rust"
    RUBY = "ruby"
    PHP = "php"
    CSHARP = "csharp"
    UNKNOWN = "unknown"


class Framework(Enum):
    DJANGO = "django"
    FLASK = "flask"
    FASTAPI = "fastapi"
    CELERY = "celery"

    NEXTJS = "nextjs"
    REACT = "react"
    EXPRESS = "express"
    NESTJS = "nestjs"
    VUE = "vue"
    ANGULAR = "angular"

    GIN = "gin"
    ECHO = "echo"
    FIBER = "fiber"

    SPRING = "spring"
    SPRINGBOOT = "springboot"

    RAILS = "rails"
    SINATRA = "sinatra"

    NONE = "none"


class ServiceType(Enum):
    WEB_SERVER = "web_server"
    API_SERVER = "api_server"
    WORKER = "worker"
    SCHEDULER = "scheduler"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    STATIC_SITE = "static_site"
    UNKNOWN = "unknown"


@dataclass
class Dependency:
    name: str
    version: Optional[str] = None
    dev: bool = False

    def __hash__(self):
        return hash(self.name)


@dataclass
class EnvironmentVariable:
    name: str
    default: Optional[str] = None
    required: bool = True
    description: Optional[str] = None


@dataclass
class ExposedPort:
    port: int
    protocol: str = "tcp"
    description: Optional[str] = None


@dataclass
class DatabaseConnection:
    type: str
    env_var: Optional[str] = None
    default_port: int = 5432


@dataclass
class ProjectInfo:
    path: str
    name: str
    language: Language
    frameworks: List[Framework]
    service_type: ServiceType
    dependencies: List[Dependency]
    dev_dependencies: List[Dependency]
    env_vars: List[EnvironmentVariable]
    ports: List[ExposedPort]
    databases: List[DatabaseConnection]
    entry_point: Optional[str] = None
    build_command: Optional[str] = None
    start_command: Optional[str] = None
    test_command: Optional[str] = None
    has_tests: bool = False
    has_dockerfile: bool = False
    has_docker_compose: bool = False
    python_version: Optional[str] = None
    node_version: Optional[str] = None
    go_version: Optional[str] = None
    static_files_path: Optional[str] = None
    health_check_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "language": self.language.value,
            "frameworks": [f.value for f in self.frameworks],
            "service_type": self.service_type.value,
            "dependencies": [
                {"name": d.name, "version": d.version} for d in self.dependencies
            ],
            "env_vars": [
                {"name": e.name, "required": e.required, "default": e.default}
                for e in self.env_vars
            ],
            "ports": [{"port": p.port, "protocol": p.protocol} for p in self.ports],
            "databases": [
                {"type": d.type, "env_var": d.env_var} for d in self.databases
            ],
            "entry_point": self.entry_point,
            "build_command": self.build_command,
            "start_command": self.start_command,
            "has_dockerfile": self.has_dockerfile,
        }


class FrameworkDetector:
    PYTHON_FRAMEWORKS = {
        Framework.DJANGO: ["django", "Django"],
        Framework.FLASK: ["flask", "Flask"],
        Framework.FASTAPI: ["fastapi", "FastAPI"],
        Framework.CELERY: ["celery", "Celery"],
    }

    JS_FRAMEWORKS = {
        Framework.NEXTJS: ["next", "next.js"],
        Framework.REACT: ["react", "React"],
        Framework.EXPRESS: ["express"],
        Framework.NESTJS: ["@nestjs/core"],
        Framework.VUE: ["vue"],
        Framework.ANGULAR: ["@angular/core"],
    }

    GO_FRAMEWORKS = {
        Framework.GIN: ["github.com/gin-gonic/gin"],
        Framework.ECHO: ["github.com/labstack/echo"],
        Framework.FIBER: ["github.com/gofiber/fiber"],
    }

    @classmethod
    def detect(
        cls, language: Language, dependencies: List[Dependency], files: List[str]
    ) -> List[Framework]:
        frameworks = []
        dep_names = {d.name.lower() for d in dependencies}

        if language == Language.PYTHON:
            for framework, patterns in cls.PYTHON_FRAMEWORKS.items():
                if any(p.lower() in dep_names for p in patterns):
                    frameworks.append(framework)

        elif language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            for framework, patterns in cls.JS_FRAMEWORKS.items():
                if any(p.lower() in dep_names for p in patterns):
                    frameworks.append(framework)

            if "next.config.js" in files or "next.config.mjs" in files:
                if Framework.NEXTJS not in frameworks:
                    frameworks.append(Framework.NEXTJS)

        elif language == Language.GO:
            for framework, patterns in cls.GO_FRAMEWORKS.items():
                if any(p in dep_names for p in patterns):
                    frameworks.append(framework)

        return frameworks if frameworks else [Framework.NONE]


class DependencyExtractor:
    @staticmethod
    def extract_from_requirements_txt(
        content: str,
    ) -> Tuple[List[Dependency], List[Dependency]]:
        deps = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            match = re.match(r"^([a-zA-Z0-9_-]+)([<>=!]+)?(.+)?$", line)
            if match:
                name = match.group(1)
                version = match.group(3) if match.group(3) else None
                deps.append(Dependency(name=name, version=version))

        return deps, []

    @staticmethod
    def extract_from_package_json(
        content: str,
    ) -> Tuple[List[Dependency], List[Dependency]]:
        deps = []
        dev_deps = []

        try:
            data = json.loads(content)

            for name, version in data.get("dependencies", {}).items():
                deps.append(Dependency(name=name, version=version))

            for name, version in data.get("devDependencies", {}).items():
                dev_deps.append(Dependency(name=name, version=version, dev=True))

        except json.JSONDecodeError:
            pass

        return deps, dev_deps

    @staticmethod
    def extract_from_go_mod(content: str) -> Tuple[List[Dependency], List[Dependency]]:
        deps = []

        in_require = False
        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("require ("):
                in_require = True
                continue
            elif line == ")":
                in_require = False
                continue

            if in_require or line.startswith("require "):
                parts = line.replace("require ", "").split()
                if len(parts) >= 2:
                    deps.append(Dependency(name=parts[0], version=parts[1]))

        return deps, []

    @staticmethod
    def extract_from_pyproject_toml(
        content: str,
    ) -> Tuple[List[Dependency], List[Dependency]]:
        deps = []
        dev_deps = []

        in_deps = False
        in_dev_deps = False

        for line in content.split("\n"):
            line = line.strip()

            if "[project.dependencies]" in line or "[tool.poetry.dependencies]" in line:
                in_deps = True
                in_dev_deps = False
                continue
            elif (
                "[project.optional-dependencies]" in line
                or "[tool.poetry.dev-dependencies]" in line
            ):
                in_deps = False
                in_dev_deps = True
                continue
            elif line.startswith("["):
                in_deps = False
                in_dev_deps = False
                continue

            if in_deps or in_dev_deps:
                match = re.match(r"^([a-zA-Z0-9_-]+)\s*=", line)
                if match:
                    name = match.group(1)
                    if name != "python":
                        dep = Dependency(name=name, dev=in_dev_deps)
                        if in_dev_deps:
                            dev_deps.append(dep)
                        else:
                            deps.append(dep)

        return deps, dev_deps


class ProjectAnalyzer:
    DEFAULT_PORTS = {
        Framework.DJANGO: 8000,
        Framework.FLASK: 5000,
        Framework.FASTAPI: 8000,
        Framework.EXPRESS: 3000,
        Framework.NEXTJS: 3000,
        Framework.REACT: 3000,
        Framework.NESTJS: 3000,
        Framework.GIN: 8080,
        Framework.SPRINGBOOT: 8080,
        Framework.RAILS: 3000,
    }

    HEALTH_PATHS = {
        Framework.DJANGO: "/health/",
        Framework.FLASK: "/health",
        Framework.FASTAPI: "/health",
        Framework.EXPRESS: "/health",
        Framework.NEXTJS: "/api/health",
        Framework.SPRINGBOOT: "/actuator/health",
    }

    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.files: List[str] = []
        self.file_contents: Dict[str, str] = {}

    def analyze(self) -> ProjectInfo:
        self._scan_files()
        language = self._detect_language()
        deps, dev_deps = self._extract_dependencies()

        frameworks = FrameworkDetector.detect(language, deps, self.files)
        service_type = self._detect_service_type(frameworks, deps)
        env_vars = self._extract_env_vars()
        ports = self._detect_ports(frameworks, deps)

        databases = self._detect_databases(deps, env_vars)
        entry_point, build_cmd, start_cmd, test_cmd = self._detect_commands(
            language, frameworks
        )
        python_version = self._detect_python_version()
        node_version = self._detect_node_version()
        go_version = self._detect_go_version()

        health_path = None
        for framework in frameworks:
            if framework in self.HEALTH_PATHS:
                health_path = self.HEALTH_PATHS[framework]
                break

        return ProjectInfo(
            path=self.project_path,
            name=os.path.basename(self.project_path),
            language=language,
            frameworks=frameworks,
            service_type=service_type,
            dependencies=deps,
            dev_dependencies=dev_deps,
            env_vars=env_vars,
            ports=ports,
            databases=databases,
            entry_point=entry_point,
            build_command=build_cmd,
            start_command=start_cmd,
            test_command=test_cmd,
            has_tests=self._has_tests(),
            has_dockerfile="Dockerfile" in self.files or "dockerfile" in self.files,
            has_docker_compose=any("docker-compose" in f for f in self.files),
            python_version=python_version,
            node_version=node_version,
            go_version=go_version,
            health_check_path=health_path,
        )

    def _scan_files(self, max_depth: int = 5):
        important_files = [
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
            "Pipfile",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "go.mod",
            "go.sum",
            "Cargo.toml",
            "Gemfile",
            "composer.json",
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            ".env",
            ".env.example",
            ".env.sample",
            "Makefile",
            "Procfile",
            "next.config.js",
            "next.config.mjs",
            "manage.py",
            "app.py",
            "main.py",
            "server.py",
            "index.js",
            "index.ts",
            "tsconfig.json",
            "webpack.config.js",
            ".python-version",
            ".nvmrc",
            ".node-version",
            ".tool-versions",
        ]

        for root, dirs, files in os.walk(self.project_path):
            depth = root.replace(self.project_path, "").count(os.sep)
            if depth >= max_depth:
                dirs.clear()
                continue

            dirs[:] = [
                d
                for d in dirs
                if d
                not in [
                    "node_modules",
                    "__pycache__",
                    ".git",
                    ".venv",
                    "venv",
                    "env",
                    ".env",
                    "dist",
                    "build",
                    ".next",
                    ".nuxt",
                    "vendor",
                    "target",
                    ".idea",
                    ".vscode",
                ]
            ]

            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), self.project_path)
                self.files.append(rel_path)

                if file in important_files or file.endswith((".env", ".env.example")):
                    try:
                        with open(
                            os.path.join(root, file),
                            "r",
                            encoding="utf-8",
                            errors="ignore",
                        ) as f:
                            self.file_contents[rel_path] = f.read()
                    except Exception:
                        pass

    def _detect_language(self) -> Language:
        if any(
            f in self.files
            for f in ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"]
        ):
            return Language.PYTHON

        if any(f in self.files for f in ["package.json"]):
            if "tsconfig.json" in self.files:
                return Language.TYPESCRIPT
            return Language.JAVASCRIPT

        if "go.mod" in self.files:
            return Language.GO

        if any(f in self.files for f in ["pom.xml", "build.gradle"]):
            return Language.JAVA

        if "Cargo.toml" in self.files:
            return Language.RUST

        if "Gemfile" in self.files:
            return Language.RUBY

        if "composer.json" in self.files:
            return Language.PHP

        extensions = {}
        for f in self.files:
            ext = os.path.splitext(f)[1].lower()
            extensions[ext] = extensions.get(ext, 0) + 1

        ext_to_lang = {
            ".py": Language.PYTHON,
            ".js": Language.JAVASCRIPT,
            ".ts": Language.TYPESCRIPT,
            ".go": Language.GO,
            ".java": Language.JAVA,
            ".rs": Language.RUST,
            ".rb": Language.RUBY,
            ".php": Language.PHP,
            ".cs": Language.CSHARP,
        }

        best_lang = Language.UNKNOWN
        best_count = 0
        for ext, lang in ext_to_lang.items():
            if extensions.get(ext, 0) > best_count:
                best_count = extensions[ext]
                best_lang = lang

        return best_lang

    def _extract_dependencies(self) -> Tuple[List[Dependency], List[Dependency]]:
        deps = []
        dev_deps = []

        if "requirements.txt" in self.file_contents:
            d, dd = DependencyExtractor.extract_from_requirements_txt(
                self.file_contents["requirements.txt"]
            )
            deps.extend(d)
            dev_deps.extend(dd)

        if "pyproject.toml" in self.file_contents:
            d, dd = DependencyExtractor.extract_from_pyproject_toml(
                self.file_contents["pyproject.toml"]
            )
            deps.extend(d)
            dev_deps.extend(dd)

        if "package.json" in self.file_contents:
            d, dd = DependencyExtractor.extract_from_package_json(
                self.file_contents["package.json"]
            )
            deps.extend(d)
            dev_deps.extend(dd)

        if "go.mod" in self.file_contents:
            d, dd = DependencyExtractor.extract_from_go_mod(
                self.file_contents["go.mod"]
            )
            deps.extend(d)
            dev_deps.extend(dd)

        return deps, dev_deps

    def _detect_service_type(
        self, frameworks: List[Framework], deps: List[Dependency]
    ) -> ServiceType:
        dep_names = {d.name.lower() for d in deps}

        if "celery" in dep_names or Framework.CELERY in frameworks:
            return ServiceType.WORKER

        web_frameworks = [
            Framework.DJANGO,
            Framework.FLASK,
            Framework.FASTAPI,
            Framework.EXPRESS,
            Framework.NEXTJS,
            Framework.NESTJS,
            Framework.GIN,
            Framework.SPRINGBOOT,
            Framework.RAILS,
        ]
        if any(f in frameworks for f in web_frameworks):
            if Framework.NEXTJS in frameworks or Framework.REACT in frameworks:
                return ServiceType.WEB_SERVER
            return ServiceType.API_SERVER

        if any(f in self.files for f in ["index.html", "public/index.html"]):
            return ServiceType.STATIC_SITE

        return ServiceType.UNKNOWN

    def _extract_env_vars(self) -> List[EnvironmentVariable]:
        env_vars = []
        seen = set()

        for env_file in [".env.example", ".env.sample", ".env"]:
            if env_file in self.file_contents:
                for line in self.file_contents[env_file].split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" in line:
                        parts = line.split("=", 1)
                        name = parts[0].strip()
                        default = parts[1].strip() if len(parts) > 1 else None

                        if (
                            default
                            and default.startswith('"')
                            and default.endswith('"')
                        ):
                            default = default[1:-1]

                        if name not in seen:
                            seen.add(name)
                            env_vars.append(
                                EnvironmentVariable(
                                    name=name,
                                    default=default if default else None,
                                    required=default is None or default == "",
                                )
                            )

        patterns = [
            r'os\.environ\[[\'"]([\w_]+)[\'"]\]',
            r'os\.getenv\([\'"]([\w_]+)[\'"]',
            r"process\.env\.([\w_]+)",
            r'process\.env\[[\'"]([\w_]+)[\'"]\]',
            r'env\([\'"]([\w_]+)[\'"]',
        ]

        for content in self.file_contents.values():
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    name = match.group(1)
                    if name not in seen and not name.startswith("_"):
                        seen.add(name)
                        env_vars.append(EnvironmentVariable(name=name, required=True))

        return env_vars

    def _detect_ports(
        self, frameworks: List[Framework], deps: List[Dependency]
    ) -> List[ExposedPort]:
        ports = []
        seen = set()

        for framework in frameworks:
            if framework in self.DEFAULT_PORTS:
                port = self.DEFAULT_PORTS[framework]
                if port not in seen:
                    seen.add(port)
                    ports.append(
                        ExposedPort(port=port, description=f"{framework.value} default")
                    )

        port_patterns = [
            r"\.listen\((\d{4,5})",
            r'port["\']?\s*[:=]\s*(\d{4,5})',
            r'PORT["\']?\s*[:=]\s*(\d{4,5})',
            r"run\([^)]*port\s*=\s*(\d{4,5})",
        ]

        for content in self.file_contents.values():
            for pattern in port_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    try:
                        port = int(match.group(1))
                        if 1024 <= port <= 65535 and port not in seen:
                            seen.add(port)
                            ports.append(ExposedPort(port=port))
                    except ValueError:
                        pass

        if not ports:
            ports.append(ExposedPort(port=8080, description="default"))

        return ports

    def _detect_databases(
        self, deps: List[Dependency], env_vars: List[EnvironmentVariable]
    ) -> List[DatabaseConnection]:
        databases = []
        dep_names = {d.name.lower() for d in deps}
        env_names = {e.name.lower() for e in env_vars}

        if any(
            x in dep_names
            for x in ["psycopg2", "psycopg2-binary", "pg", "postgres", "asyncpg"]
        ):
            databases.append(
                DatabaseConnection(
                    type="postgresql", env_var="DATABASE_URL", default_port=5432
                )
            )
        elif any("postgres" in e or "pg_" in e for e in env_names):
            databases.append(
                DatabaseConnection(
                    type="postgresql", env_var="DATABASE_URL", default_port=5432
                )
            )

        if any(x in dep_names for x in ["mysql", "mysqlclient", "pymysql", "mysql2"]):
            databases.append(
                DatabaseConnection(
                    type="mysql", env_var="DATABASE_URL", default_port=3306
                )
            )

        if any(
            x in dep_names for x in ["pymongo", "mongoengine", "mongoose", "mongodb"]
        ):
            databases.append(
                DatabaseConnection(
                    type="mongodb", env_var="MONGODB_URI", default_port=27017
                )
            )

        if any(x in dep_names for x in ["redis", "ioredis", "redis-py"]):
            databases.append(
                DatabaseConnection(type="redis", env_var="REDIS_URL", default_port=6379)
            )

        return databases

    def _detect_commands(
        self, language: Language, frameworks: List[Framework]
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        entry_point = None
        build_cmd = None
        start_cmd = None
        test_cmd = None

        if language == Language.PYTHON:
            if "manage.py" in self.files:
                entry_point = "manage.py"
                if Framework.DJANGO in frameworks:
                    start_cmd = "python manage.py runserver 0.0.0.0:8000"
            elif "app.py" in self.files:
                entry_point = "app.py"
                start_cmd = "python app.py"
            elif "main.py" in self.files:
                entry_point = "main.py"
                start_cmd = "python main.py"

            if Framework.FASTAPI in frameworks:
                start_cmd = f"uvicorn {entry_point.replace('.py', '')}:app --host 0.0.0.0 --port 8000"
            elif Framework.FLASK in frameworks:
                start_cmd = (
                    f"gunicorn {entry_point.replace('.py', '')}:app --bind 0.0.0.0:5000"
                )

            build_cmd = "pip install -r requirements.txt"
            test_cmd = (
                "pytest"
                if "pytest" in [d.name for d in self._extract_dependencies()[0]]
                else "python -m unittest"
            )

        elif language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            if "package.json" in self.file_contents:
                try:
                    pkg = json.loads(self.file_contents["package.json"])
                    scripts = pkg.get("scripts", {})

                    build_cmd = (
                        f"npm run {scripts.get('build', 'build')}"
                        if "build" in scripts
                        else "npm run build"
                    )
                    start_cmd = (
                        f"npm run {scripts.get('start', 'start')}"
                        if "start" in scripts
                        else "npm start"
                    )
                    test_cmd = (
                        f"npm run {scripts.get('test', 'test')}"
                        if "test" in scripts
                        else "npm test"
                    )

                    if Framework.NEXTJS in frameworks:
                        build_cmd = "npm run build"
                        start_cmd = "npm start"
                except json.JSONDecodeError:
                    pass

        elif language == Language.GO:
            entry_point = "main.go"
            build_cmd = "go build -o app ."
            start_cmd = "./app"
            test_cmd = "go test ./..."

        return entry_point, build_cmd, start_cmd, test_cmd

    def _detect_python_version(self) -> Optional[str]:
        if ".python-version" in self.file_contents:
            return self.file_contents[".python-version"].strip()

        if "pyproject.toml" in self.file_contents:
            match = re.search(
                r'python\s*=\s*["\']([^"\']+)["\']',
                self.file_contents["pyproject.toml"],
            )
            if match:
                return match.group(1)

        return "3.11"

    def _detect_node_version(self) -> Optional[str]:
        if ".nvmrc" in self.file_contents:
            return self.file_contents[".nvmrc"].strip()

        if ".node-version" in self.file_contents:
            return self.file_contents[".node-version"].strip()

        if "package.json" in self.file_contents:
            try:
                pkg = json.loads(self.file_contents["package.json"])
                engines = pkg.get("engines", {})
                if "node" in engines:
                    return engines["node"]
            except json.JSONDecodeError:
                pass

        return "18"

    def _detect_go_version(self) -> Optional[str]:
        if "go.mod" in self.file_contents:
            match = re.search(
                r"^go\s+(\d+\.\d+)", self.file_contents["go.mod"], re.MULTILINE
            )
            if match:
                return match.group(1)

        return "1.21"

    def _has_tests(self) -> bool:
        test_indicators = [
            "tests/",
            "test/",
            "__tests__/",
            "spec/",
            "test_",
            "_test.py",
            "_test.go",
            ".test.js",
            ".test.ts",
            ".spec.js",
            ".spec.ts",
        ]

        for f in self.files:
            if any(ind in f.lower() for ind in test_indicators):
                return True

        return False
