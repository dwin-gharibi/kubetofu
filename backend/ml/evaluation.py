import logging
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    GENERATION = "generation"
    DEPLOYABILITY = "deployability"
    QUALITY = "quality"


@dataclass
class MetricResult:
    name: str
    value: float
    metric_type: MetricType
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EvaluationReport:
    experiment_name: str
    metrics: List[MetricResult]
    overall_score: float
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "metrics": [
                {"name": m.name, "value": m.value, "type": m.metric_type.value}
                for m in self.metrics
            ],
            "overall_score": self.overall_score,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_latex_table(self) -> str:
        lines = [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Evaluation Results}",
            "\\label{tab:evaluation}",
            "\\begin{tabular}{lcc}",
            "\\toprule",
            "Metric & Value & Type \\\\",
            "\\midrule",
        ]

        for m in self.metrics:
            lines.append(f"{m.name} & {m.value:.4f} & {m.metric_type.value} \\\\")

        lines.extend(
            [
                "\\midrule",
                f"\\textbf{{Overall Score}} & \\textbf{{{self.overall_score:.4f}}} & - \\\\",
                "\\bottomrule",
                "\\end{tabular}",
                "\\end{table}",
            ]
        )

        return "\n".join(lines)


class MetricCalculator:
    @staticmethod
    def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(y_true == y_pred))

    @staticmethod
    def precision_recall_f1(
        y_true: np.ndarray, y_pred: np.ndarray, average: str = "weighted"
    ) -> Tuple[float, float, float]:
        from sklearn.metrics import precision_score, recall_score, f1_score

        precision = precision_score(y_true, y_pred, average=average, zero_division=0)
        recall = recall_score(y_true, y_pred, average=average, zero_division=0)
        f1 = f1_score(y_true, y_pred, average=average, zero_division=0)

        return float(precision), float(recall), float(f1)

    @staticmethod
    def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
        from sklearn.metrics import confusion_matrix

        return confusion_matrix(y_true, y_pred)

    @staticmethod
    def roc_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
        from sklearn.metrics import roc_auc_score

        try:
            return float(roc_auc_score(y_true, y_scores))
        except:
            return 0.0

    @staticmethod
    def mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean((y_true - y_pred) ** 2))

    @staticmethod
    def mean_absolute_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(np.abs(y_true - y_pred)))

    @staticmethod
    def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        from sklearn.metrics import r2_score

        return float(r2_score(y_true, y_pred))

    @staticmethod
    def silhouette_score(X: np.ndarray, labels: np.ndarray) -> float:
        from sklearn.metrics import silhouette_score

        if len(set(labels)) < 2:
            return 0.0
        return float(silhouette_score(X, labels))

    @staticmethod
    def bleu_score(reference: str, hypothesis: str, n_gram: int = 4) -> float:
        from collections import Counter

        ref_tokens = reference.split()
        hyp_tokens = hypothesis.split()

        if len(hyp_tokens) == 0:
            return 0.0

        precisions = []
        for n in range(1, min(n_gram + 1, len(hyp_tokens) + 1)):
            ref_ngrams = Counter(
                tuple(ref_tokens[i : i + n]) for i in range(len(ref_tokens) - n + 1)
            )
            hyp_ngrams = Counter(
                tuple(hyp_tokens[i : i + n]) for i in range(len(hyp_tokens) - n + 1)
            )

            common = sum((ref_ngrams & hyp_ngrams).values())
            total = sum(hyp_ngrams.values())

            precision = common / total if total > 0 else 0
            precisions.append(precision)

        if not precisions or 0 in precisions:
            return 0.0

        geo_mean = np.exp(np.mean(np.log(precisions)))
        bp = min(1, np.exp(1 - len(ref_tokens) / len(hyp_tokens)))

        return float(bp * geo_mean)

    @staticmethod
    def code_similarity(code1: str, code2: str) -> float:
        tokens1 = set(code1.split())
        tokens2 = set(code2.split())

        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union

    @staticmethod
    def deployability_score(
        results: List[Dict[str, Any]],
    ) -> Tuple[float, float, float]:
        first_attempts = [r.get("deployable_first", False) for r in results]
        pass_at_5 = [r.get("deployable_by_5", False) for r in results]
        pass_at_10 = [r.get("deployable_by_10", False) for r in results]

        first_rate = np.mean(first_attempts) if first_attempts else 0.0
        pass5_rate = np.mean(pass_at_5) if pass_at_5 else 0.0
        pass10_rate = np.mean(pass_at_10) if pass_at_10 else 0.0

        return float(first_rate), float(pass5_rate), float(pass10_rate)


class CrossValidator:
    def __init__(self, n_folds: int = 5, shuffle: bool = True, random_state: int = 42):
        self.n_folds = n_folds
        self.shuffle = shuffle
        self.random_state = random_state

    def validate(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        metric_fn: Callable[[np.ndarray, np.ndarray], float],
    ) -> Dict[str, Any]:
        from sklearn.model_selection import KFold

        kf = KFold(
            n_splits=self.n_folds, shuffle=self.shuffle, random_state=self.random_state
        )

        fold_scores = []
        fold_details = []

        for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model_clone = self._clone_model(model)
            model_clone.train(X_train, y_train)

            y_pred = self._get_predictions(model_clone, X_val)
            score = metric_fn(y_val, y_pred)

            fold_scores.append(score)
            fold_details.append(
                {
                    "fold": fold,
                    "train_size": len(train_idx),
                    "val_size": len(val_idx),
                    "score": score,
                }
            )

        return {
            "mean_score": float(np.mean(fold_scores)),
            "std_score": float(np.std(fold_scores)),
            "min_score": float(np.min(fold_scores)),
            "max_score": float(np.max(fold_scores)),
            "fold_scores": fold_scores,
            "fold_details": fold_details,
        }

    def _clone_model(self, model):
        import copy

        return copy.deepcopy(model)

    def _get_predictions(self, model, X: np.ndarray) -> np.ndarray:
        results = model.predict(X)
        if hasattr(results[0], "predicted_class"):
            return np.array([r.predicted_class for r in results])
        return np.array(results)


@dataclass
class BenchmarkScenario:
    id: str
    name: str
    description: str
    input_request: str
    expected_type: str
    expected_resources: List[str]
    difficulty: str
    tags: List[str] = field(default_factory=list)


class BenchmarkRunner:
    def __init__(self):
        self.scenarios: List[BenchmarkScenario] = []
        self.results: List[Dict[str, Any]] = []
        self._load_default_scenarios()

    def _load_default_scenarios(self) -> None:
        self.scenarios = [
            BenchmarkScenario(
                id="tf-001",
                name="Simple VM Deployment",
                description="Deploy a single virtual machine with SSH access",
                input_request="Deploy a virtual machine with 2 CPU cores and 4GB RAM on ArvanCloud with SSH access",
                expected_type="terraform",
                expected_resources=[
                    "arvancloud_iaas_abrak",
                    "arvancloud_iaas_security_group",
                ],
                difficulty="easy",
                tags=["compute", "arvancloud"],
            ),
            BenchmarkScenario(
                id="tf-002",
                name="VPC with Subnets",
                description="Create a VPC with public and private subnets",
                input_request="Create a network with 10.0.0.0/16 CIDR and two subnets for web and database tiers",
                expected_type="terraform",
                expected_resources=[
                    "arvancloud_iaas_network",
                    "arvancloud_iaas_subnet",
                ],
                difficulty="medium",
                tags=["network", "arvancloud"],
            ),
            BenchmarkScenario(
                id="tf-003",
                name="Load Balanced Web App",
                description="Deploy load-balanced web application",
                input_request="Deploy 3 web servers behind a load balancer with auto-scaling",
                expected_type="terraform",
                expected_resources=[
                    "arvancloud_iaas_abrak",
                    "arvancloud_iaas_loadbalancer",
                ],
                difficulty="hard",
                tags=["compute", "networking", "arvancloud"],
            ),
            BenchmarkScenario(
                id="k8s-001",
                name="Simple Deployment",
                description="Deploy a stateless application",
                input_request="Deploy nginx with 3 replicas on Kubernetes",
                expected_type="kubernetes",
                expected_resources=["Deployment", "Service"],
                difficulty="easy",
                tags=["deployment", "kubernetes"],
            ),
            BenchmarkScenario(
                id="k8s-002",
                name="StatefulSet with PVC",
                description="Deploy a stateful application with persistent storage",
                input_request="Deploy PostgreSQL database with persistent volume claim",
                expected_type="kubernetes",
                expected_resources=["StatefulSet", "PersistentVolumeClaim", "Service"],
                difficulty="medium",
                tags=["stateful", "storage", "kubernetes"],
            ),
            BenchmarkScenario(
                id="k8s-003",
                name="Microservices Architecture",
                description="Deploy a complete microservices application",
                input_request="Deploy a microservices app with frontend, API, worker, and database components",
                expected_type="kubernetes",
                expected_resources=["Deployment", "Service", "Ingress", "ConfigMap"],
                difficulty="hard",
                tags=["microservices", "kubernetes"],
            ),
            BenchmarkScenario(
                id="docker-001",
                name="Python Web App",
                description="Create Dockerfile for Python Flask application",
                input_request="Create a Dockerfile for a Python Flask web application",
                expected_type="dockerfile",
                expected_resources=["FROM", "WORKDIR", "COPY", "RUN", "CMD"],
                difficulty="easy",
                tags=["python", "web", "docker"],
            ),
            BenchmarkScenario(
                id="docker-002",
                name="Multi-stage Build",
                description="Create optimized multi-stage Dockerfile",
                input_request="Create an optimized Dockerfile for a Go application with multi-stage build",
                expected_type="dockerfile",
                expected_resources=[
                    "FROM ... AS builder",
                    "FROM scratch",
                    "COPY --from",
                ],
                difficulty="medium",
                tags=["go", "optimization", "docker"],
            ),
            BenchmarkScenario(
                id="compose-001",
                name="Full Stack Application",
                description="Docker Compose for full-stack application",
                input_request="Create docker-compose for a web app with Postgres, Redis, and nginx",
                expected_type="docker_compose",
                expected_resources=["services", "volumes", "networks"],
                difficulty="medium",
                tags=["fullstack", "compose"],
            ),
            BenchmarkScenario(
                id="helm-001",
                name="Basic Helm Chart",
                description="Create a basic Helm chart",
                input_request="Create a Helm chart for a web application with configurable replicas and resources",
                expected_type="helm",
                expected_resources=[
                    "Chart.yaml",
                    "values.yaml",
                    "templates/deployment.yaml",
                ],
                difficulty="medium",
                tags=["helm", "kubernetes"],
            ),
            BenchmarkScenario(
                id="ansible-001",
                name="Web Server Setup",
                description="Ansible playbook for web server",
                input_request="Create an Ansible playbook to install and configure nginx",
                expected_type="ansible",
                expected_resources=["hosts", "tasks", "handlers"],
                difficulty="easy",
                tags=["nginx", "ansible"],
            ),
        ]

    def run_benchmark(
        self, generator, scenarios: Optional[List[str]] = None, max_iterations: int = 10
    ) -> EvaluationReport:
        import time

        start_time = time.time()

        selected = self.scenarios
        if scenarios:
            selected = [s for s in self.scenarios if s.id in scenarios]

        results = []
        metrics_list = []

        for scenario in selected:
            logger.info(f"Running scenario: {scenario.id} - {scenario.name}")

            result = self._run_single_scenario(generator, scenario, max_iterations)
            results.append(result)

            if result.get("deployable_first"):
                metrics_list.append(
                    MetricResult(
                        name=f"{scenario.id}_first_attempt",
                        value=1.0,
                        metric_type=MetricType.DEPLOYABILITY,
                    )
                )

            if result.get("quality_score"):
                metrics_list.append(
                    MetricResult(
                        name=f"{scenario.id}_quality",
                        value=result["quality_score"],
                        metric_type=MetricType.QUALITY,
                    )
                )

        first_rate, pass5, pass10 = MetricCalculator.deployability_score(results)

        metrics_list.extend(
            [
                MetricResult(
                    name="deployability_first_attempt",
                    value=first_rate,
                    metric_type=MetricType.DEPLOYABILITY,
                ),
                MetricResult(
                    name="deployability_pass@5",
                    value=pass5,
                    metric_type=MetricType.DEPLOYABILITY,
                ),
                MetricResult(
                    name="deployability_pass@10",
                    value=pass10,
                    metric_type=MetricType.DEPLOYABILITY,
                ),
            ]
        )

        overall = np.mean(
            [
                first_rate * 0.3,
                pass5 * 0.3,
                pass10 * 0.2,
                np.mean([r.get("quality_score", 0) for r in results]) * 0.2,
            ]
        )

        self.results = results

        return EvaluationReport(
            experiment_name="IaC Generation Benchmark",
            metrics=metrics_list,
            overall_score=float(overall),
            execution_time=time.time() - start_time,
            metadata={
                "n_scenarios": len(selected),
                "max_iterations": max_iterations,
                "scenario_ids": [s.id for s in selected],
            },
        )

    def _run_single_scenario(
        self, generator, scenario: BenchmarkScenario, max_iterations: int
    ) -> Dict[str, Any]:
        from generators.base import GenerationContext, IaCType

        type_map = {
            "terraform": IaCType.TERRAFORM,
            "kubernetes": IaCType.KUBERNETES,
            "dockerfile": IaCType.DOCKERFILE,
            "docker_compose": IaCType.DOCKER_COMPOSE,
            "helm": IaCType.HELM,
            "ansible": IaCType.ANSIBLE,
        }

        context = GenerationContext(
            natural_language_request=scenario.input_request,
            target_type=type_map.get(scenario.expected_type, IaCType.TERRAFORM),
        )

        deployable_at = None

        for iteration in range(1, max_iterations + 1):
            try:
                result = generator.generate(context)

                is_valid, errors = generator.validate(result.code)

                if is_valid and deployable_at is None:
                    deployable_at = iteration

                if not is_valid and errors:
                    context.feedback = "; ".join([e.message for e in errors[:3]])
                    context.add_attempt(result.code, errors)

                if is_valid:
                    break

            except Exception as e:
                logger.error(f"Scenario {scenario.id} error: {e}")

        resources_found = sum(
            1 for r in scenario.expected_resources if r.lower() in result.code.lower()
        )
        resource_coverage = resources_found / len(scenario.expected_resources)

        return {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "difficulty": scenario.difficulty,
            "deployable_first": deployable_at == 1,
            "deployable_by_5": deployable_at is not None and deployable_at <= 5,
            "deployable_by_10": deployable_at is not None and deployable_at <= 10,
            "iterations_to_deploy": deployable_at,
            "resource_coverage": resource_coverage,
            "quality_score": result.overall_quality
            if hasattr(result, "overall_quality")
            else 0,
        }

    def generate_report(self, format: str = "markdown") -> str:
        if not self.results:
            return "No results available"

        if format == "latex":
            return self._generate_latex_report()
        else:
            return self._generate_markdown_report()

    def _generate_markdown_report(self) -> str:
        lines = [
            "# Kube-Tofu Benchmark Report",
            "",
            "## Summary",
            "",
            f"- Total Scenarios: {len(self.results)}",
            f"- First Attempt Success: {np.mean([r['deployable_first'] for r in self.results]) * 100:.1f}%",
            f"- Pass@5: {np.mean([r['deployable_by_5'] for r in self.results]) * 100:.1f}%",
            f"- Pass@10: {np.mean([r['deployable_by_10'] for r in self.results]) * 100:.1f}%",
            "",
            "## Detailed Results",
            "",
            "| Scenario | Difficulty | First | Pass@5 | Pass@10 | Iterations |",
            "|----------|------------|-------|--------|---------|------------|",
        ]

        for r in self.results:
            lines.append(
                f"| {r['scenario_id']} | {r['difficulty']} | "
                f"{'✓' if r['deployable_first'] else '✗'} | "
                f"{'✓' if r['deployable_by_5'] else '✗'} | "
                f"{'✓' if r['deployable_by_10'] else '✗'} | "
                f"{r['iterations_to_deploy'] or 'N/A'} |"
            )

        return "\n".join(lines)

    def _generate_latex_report(self) -> str:
        lines = [
            "\\begin{table*}[htbp]",
            "\\centering",
            "\\caption{Benchmark Results for Kube-Tofu IaC Generation}",
            "\\label{tab:benchmark}",
            "\\begin{tabular}{llccccc}",
            "\\toprule",
            "ID & Scenario & Difficulty & First Attempt & Pass@5 & Pass@10 & Iterations \\\\",
            "\\midrule",
        ]

        for r in self.results:
            lines.append(
                f"{r['scenario_id']} & {r['scenario_name'][:20]} & {r['difficulty']} & "
                f"{'\\checkmark' if r['deployable_first'] else '$\\times$'} & "
                f"{'\\checkmark' if r['deployable_by_5'] else '$\\times$'} & "
                f"{'\\checkmark' if r['deployable_by_10'] else '$\\times$'} & "
                f"{r['iterations_to_deploy'] or '--'} \\\\"
            )

        first_rate = np.mean([r["deployable_first"] for r in self.results]) * 100
        pass5_rate = np.mean([r["deployable_by_5"] for r in self.results]) * 100
        pass10_rate = np.mean([r["deployable_by_10"] for r in self.results]) * 100

        lines.extend(
            [
                "\\midrule",
                f"\\multicolumn{{3}}{{l}}{{\\textbf{{Average}}}} & "
                f"\\textbf{{{first_rate:.1f}\\%}} & "
                f"\\textbf{{{pass5_rate:.1f}\\%}} & "
                f"\\textbf{{{pass10_rate:.1f}\\%}} & -- \\\\",
                "\\bottomrule",
                "\\end{tabular}",
                "\\end{table*}",
            ]
        )

        return "\n".join(lines)


class EvaluationFramework:
    def __init__(self):
        self.metric_calculator = MetricCalculator()
        self.cross_validator = CrossValidator()
        self.benchmark_runner = BenchmarkRunner()

    def evaluate_classifier(
        self, model, X: np.ndarray, y: np.ndarray
    ) -> EvaluationReport:
        import time

        start_time = time.time()

        cv_results = self.cross_validator.validate(
            model,
            X,
            y,
            lambda y_true, y_pred: self.metric_calculator.accuracy(y_true, y_pred),
        )

        model.train(X, y)
        predictions = model.predict(X)
        y_pred = np.array([p.predicted_class for p in predictions])

        precision, recall, f1 = self.metric_calculator.precision_recall_f1(y, y_pred)

        metrics = [
            MetricResult(
                "accuracy", cv_results["mean_score"], MetricType.CLASSIFICATION
            ),
            MetricResult(
                "accuracy_std", cv_results["std_score"], MetricType.CLASSIFICATION
            ),
            MetricResult("precision", precision, MetricType.CLASSIFICATION),
            MetricResult("recall", recall, MetricType.CLASSIFICATION),
            MetricResult("f1_score", f1, MetricType.CLASSIFICATION),
        ]

        return EvaluationReport(
            experiment_name="Classifier Evaluation",
            metrics=metrics,
            overall_score=f1,
            execution_time=time.time() - start_time,
            metadata={"cv_folds": self.cross_validator.n_folds},
        )

    def evaluate_generator(
        self, generator, scenarios: Optional[List[str]] = None
    ) -> EvaluationReport:
        return self.benchmark_runner.run_benchmark(generator, scenarios)

    def full_evaluation(
        self,
        classifiers: Dict[str, Any],
        generators: Dict[str, Any],
        X: np.ndarray,
        y: np.ndarray,
    ) -> Dict[str, EvaluationReport]:
        reports = {}

        for name, clf in classifiers.items():
            logger.info(f"Evaluating classifier: {name}")
            reports[f"clf_{name}"] = self.evaluate_classifier(clf, X, y)

        for name, gen in generators.items():
            logger.info(f"Evaluating generator: {name}")
            reports[f"gen_{name}"] = self.evaluate_generator(gen)

        return reports
