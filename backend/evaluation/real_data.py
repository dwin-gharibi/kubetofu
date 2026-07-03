import os
import re
import json
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Generator
from pathlib import Path
from datetime import datetime
from enum import Enum


class IaCType(Enum):
    TERRAFORM = "terraform"
    KUBERNETES = "kubernetes"
    DOCKERFILE = "dockerfile"
    DOCKER_COMPOSE = "docker_compose"
    ANSIBLE = "ansible"
    HELM = "helm"
    VAGRANT = "vagrant"
    UNKNOWN = "unknown"


@dataclass
class IaCSample:
    id: str
    content: str
    iac_type: IaCType
    source_path: str
    filename: str
    size_bytes: int
    line_count: int
    features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "iac_type": self.iac_type.value,
            "source_path": self.source_path,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "features": self.features,
            "metadata": self.metadata,
        }


@dataclass
class DatasetStats:
    total_samples: int
    samples_per_type: Dict[str, int]
    total_size_bytes: int
    avg_line_count: float
    collection_time: str
    source_dirs: List[str]


class IaCDataCollector:
    FILE_PATTERNS = {
        IaCType.TERRAFORM: [r"\.tf$", r"\.tf\.json$"],
        IaCType.KUBERNETES: [r"\.ya?ml$"],
        IaCType.DOCKERFILE: [r"^Dockerfile", r"^Dockerfile\."],
        IaCType.DOCKER_COMPOSE: [r"docker-compose.*\.ya?ml$", r"compose\.ya?ml$"],
        IaCType.ANSIBLE: [r"playbook.*\.ya?ml$", r"ansible.*\.ya?ml$"],
        IaCType.HELM: [r"values\.ya?ml$", r"Chart\.ya?ml$"],
        IaCType.VAGRANT: [r"^Vagrantfile$"],
    }

    CONTENT_PATTERNS = {
        IaCType.KUBERNETES: ["apiVersion:", "kind:"],
        IaCType.ANSIBLE: ["hosts:", "tasks:", "roles:"],
        IaCType.DOCKER_COMPOSE: ["services:", "version:"],
        IaCType.HELM: ["replicaCount:", "image:"],
    }

    def __init__(self, max_file_size: int = 100000):
        self.max_file_size = max_file_size
        self.samples: List[IaCSample] = []
        self.stats: Optional[DatasetStats] = None

    def collect_from_directory(
        self,
        directory: str,
        recursive: bool = True,
        max_samples: Optional[int] = None,
    ) -> List[IaCSample]:
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            raise ValueError(f"Directory not found: {directory}")

        collected = []

        for filepath in self._find_iac_files(directory, recursive):
            if max_samples and len(collected) >= max_samples:
                break

            sample = self._process_file(filepath)
            if sample:
                collected.append(sample)
                self.samples.append(sample)

        return collected

    def collect_from_multiple(
        self,
        directories: List[str],
        max_samples_per_dir: Optional[int] = None,
    ) -> List[IaCSample]:
        all_samples = []

        for directory in directories:
            try:
                samples = self.collect_from_directory(
                    directory,
                    max_samples=max_samples_per_dir,
                )
                all_samples.extend(samples)
            except Exception as e:
                print(f"Warning: Error collecting from {directory}: {e}")

        return all_samples

    def _find_iac_files(
        self,
        directory: str,
        recursive: bool,
    ) -> Generator[str, None, None]:
        skip_dirs = {
            "node_modules",
            "__pycache__",
            ".git",
            "venv",
            ".venv",
            "vendor",
            "target",
            ".terraform",
            ".cache",
        }

        if recursive:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for filename in files:
                    filepath = os.path.join(root, filename)
                    if self._is_iac_file(filename):
                        yield filepath
        else:
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath) and self._is_iac_file(filename):
                    yield filepath

    def _is_iac_file(self, filename: str) -> bool:
        for patterns in self.FILE_PATTERNS.values():
            for pattern in patterns:
                if re.search(pattern, filename, re.IGNORECASE):
                    return True
        return False

    def _detect_type(self, filename: str, content: str) -> IaCType:
        filename_lower = filename.lower()

        if filename_lower.endswith(".tf") or filename_lower.endswith(".tf.json"):
            return IaCType.TERRAFORM

        if filename_lower.startswith("dockerfile"):
            return IaCType.DOCKERFILE

        if filename_lower == "vagrantfile":
            return IaCType.VAGRANT

        if filename_lower.endswith((".yaml", ".yml")):
            if re.search(r"docker-compose|compose\.ya?ml", filename_lower):
                return IaCType.DOCKER_COMPOSE

            for iac_type, patterns in self.CONTENT_PATTERNS.items():
                if all(p in content for p in patterns[:2]):
                    return iac_type

            if "apiVersion:" in content:
                return IaCType.KUBERNETES

        return IaCType.UNKNOWN

    def _process_file(self, filepath: str) -> Optional[IaCSample]:
        try:
            size = os.path.getsize(filepath)
            if size > self.max_file_size or size == 0:
                return None

            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            filename = os.path.basename(filepath)
            iac_type = self._detect_type(filename, content)

            if iac_type == IaCType.UNKNOWN:
                return None

            features = self._extract_features(content, iac_type)

            sample_id = hashlib.md5(content.encode()).hexdigest()[:12]

            return IaCSample(
                id=sample_id,
                content=content,
                iac_type=iac_type,
                source_path=filepath,
                filename=filename,
                size_bytes=size,
                line_count=content.count("\n") + 1,
                features=features,
                metadata={
                    "collected_at": datetime.now().isoformat(),
                },
            )

        except Exception:
            return None

    def _extract_features(self, content: str, iac_type: IaCType) -> Dict[str, Any]:
        features = {
            "code_length": len(content),
            "line_count": content.count("\n") + 1,
            "brace_count": content.count("{") + content.count("}"),
            "colon_count": content.count(":"),
            "comment_lines": 0,
            "unique_tokens": 0,
        }

        lines = content.split("\n")

        if iac_type in [IaCType.TERRAFORM, IaCType.DOCKERFILE]:
            features["comment_lines"] = sum(
                1 for l in lines if l.strip().startswith("#")
            )
        elif iac_type in [IaCType.KUBERNETES, IaCType.ANSIBLE, IaCType.DOCKER_COMPOSE]:
            features["comment_lines"] = sum(
                1 for l in lines if l.strip().startswith("#")
            )

        tokens = set(re.findall(r"\b\w+\b", content.lower()))
        features["unique_tokens"] = len(tokens)

        if iac_type == IaCType.TERRAFORM:
            features["resource_count"] = len(re.findall(r'\bresource\s+"', content))
            features["variable_count"] = len(re.findall(r'\bvariable\s+"', content))
            features["module_count"] = len(re.findall(r'\bmodule\s+"', content))

        elif iac_type == IaCType.KUBERNETES:
            features["api_version"] = bool(re.search(r"apiVersion:", content))
            features["kind_count"] = len(re.findall(r"\bkind:", content))

        elif iac_type == IaCType.DOCKERFILE:
            features["from_count"] = len(re.findall(r"^FROM\s", content, re.MULTILINE))
            features["run_count"] = len(re.findall(r"^RUN\s", content, re.MULTILINE))
            features["copy_count"] = len(re.findall(r"^COPY\s", content, re.MULTILINE))

        return features

    def get_stats(self) -> DatasetStats:
        if not self.samples:
            return DatasetStats(
                total_samples=0,
                samples_per_type={},
                total_size_bytes=0,
                avg_line_count=0,
                collection_time=datetime.now().isoformat(),
                source_dirs=[],
            )

        samples_per_type = {}
        for sample in self.samples:
            t = sample.iac_type.value
            samples_per_type[t] = samples_per_type.get(t, 0) + 1

        total_size = sum(s.size_bytes for s in self.samples)
        avg_lines = sum(s.line_count for s in self.samples) / len(self.samples)
        source_dirs = list(set(os.path.dirname(s.source_path) for s in self.samples))

        return DatasetStats(
            total_samples=len(self.samples),
            samples_per_type=samples_per_type,
            total_size_bytes=total_size,
            avg_line_count=avg_lines,
            collection_time=datetime.now().isoformat(),
            source_dirs=source_dirs[:10],
        )

    def export_dataset(self, output_path: str, include_content: bool = False):
        data = {
            "stats": {
                "total_samples": len(self.samples),
                "samples_per_type": self.get_stats().samples_per_type,
            },
            "samples": [
                {
                    **s.to_dict(),
                    "content": s.content if include_content else None,
                }
                for s in self.samples
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_samples_for_training(self) -> Tuple[List[List[float]], List[int]]:
        type_to_idx = {t: i for i, t in enumerate(IaCType)}

        X = []
        y = []

        feature_keys = [
            "code_length",
            "line_count",
            "brace_count",
            "colon_count",
            "comment_lines",
            "unique_tokens",
        ]

        for sample in self.samples:
            if sample.iac_type == IaCType.UNKNOWN:
                continue

            features = [sample.features.get(k, 0) for k in feature_keys]
            X.append(features)
            y.append(type_to_idx[sample.iac_type])

        return X, y


class ProjectIaCCollector:
    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.collector = IaCDataCollector()
        self.existing_iac: List[IaCSample] = []
        self.gaps: List[str] = []

    def analyze(self) -> Dict[str, Any]:
        self.existing_iac = self.collector.collect_from_directory(
            self.project_path,
            recursive=True,
        )

        existing_types = set(s.iac_type for s in self.existing_iac)
        self.gaps = self._identify_gaps(existing_types)

        return {
            "project_path": self.project_path,
            "existing_iac": [s.to_dict() for s in self.existing_iac],
            "existing_types": [t.value for t in existing_types],
            "gaps": self.gaps,
            "recommendations": self._generate_recommendations(existing_types),
        }

    def _identify_gaps(self, existing_types: set) -> List[str]:
        gaps = []

        has_python = any(
            f.endswith(".py")
            for f in os.listdir(self.project_path)
            if os.path.isfile(os.path.join(self.project_path, f))
        )
        has_js = any(
            f.endswith((".js", ".ts"))
            for f in os.listdir(self.project_path)
            if os.path.isfile(os.path.join(self.project_path, f))
        )
        os.path.exists(os.path.join(self.project_path, "requirements.txt"))
        os.path.exists(os.path.join(self.project_path, "package.json"))

        if (has_python or has_js) and IaCType.DOCKERFILE not in existing_types:
            gaps.append("Missing Dockerfile for containerization")

        if (
            IaCType.DOCKERFILE in existing_types
            and IaCType.DOCKER_COMPOSE not in existing_types
        ):
            gaps.append("Missing docker-compose.yml for local development")

        if (
            IaCType.DOCKERFILE in existing_types
            and IaCType.KUBERNETES not in existing_types
        ):
            gaps.append("Missing Kubernetes manifests for container orchestration")

        return gaps

    def _generate_recommendations(self, existing_types: set) -> List[str]:
        recommendations = []

        if IaCType.DOCKERFILE in existing_types:
            for sample in self.existing_iac:
                if sample.iac_type == IaCType.DOCKERFILE:
                    if "USER" not in sample.content:
                        recommendations.append(
                            f"Add USER instruction to {sample.filename} for security"
                        )
                    if "HEALTHCHECK" not in sample.content:
                        recommendations.append(
                            f"Add HEALTHCHECK to {sample.filename} for container health monitoring"
                        )

        if IaCType.KUBERNETES in existing_types:
            for sample in self.existing_iac:
                if sample.iac_type == IaCType.KUBERNETES:
                    if "resources:" not in sample.content:
                        recommendations.append(
                            f"Add resource limits to {sample.filename}"
                        )
                    if "livenessProbe" not in sample.content:
                        recommendations.append(
                            f"Add liveness/readiness probes to {sample.filename}"
                        )

        return recommendations


def collect_kube_tofu_data() -> Dict[str, Any]:
    current = Path(__file__).parent.parent.parent
    collector = IaCDataCollector()

    samples = collector.collect_from_directory(str(current), max_samples=100)

    stats = collector.get_stats()

    return {
        "samples_collected": len(samples),
        "stats": {
            "total": stats.total_samples,
            "per_type": stats.samples_per_type,
            "avg_lines": round(stats.avg_line_count, 2),
        },
        "sample_files": [s.filename for s in samples[:10]],
    }


if __name__ == "__main__":
    print("Testing IaC Data Collection...")
    print()

    result = collect_kube_tofu_data()

    print(f"Samples collected: {result['samples_collected']}")
    print(f"Stats: {json.dumps(result['stats'], indent=2)}")
    print(f"Sample files: {result['sample_files']}")
