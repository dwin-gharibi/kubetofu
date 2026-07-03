import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import random


class StudyType(Enum):
    USABILITY = "usability"
    TASK_COMPLETION = "task_completion"
    COMPARATIVE = "comparative"
    LONGITUDINAL = "longitudinal"
    SURVEY = "survey"
    AB_TEST = "ab_test"


class ExpertiseLevel(Enum):
    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class TaskDifficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class Participant:
    id: str
    expertise_level: ExpertiseLevel
    years_experience: int
    familiar_tools: List[str]
    demographics: Dict[str, Any] = field(default_factory=dict)
    group: Optional[str] = None
    consent_given: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StudyTask:
    id: str
    name: str
    description: str
    difficulty: TaskDifficulty
    expected_time_minutes: int
    requirements: List[str]
    success_criteria: List[str]
    iac_type: str
    reference_solution: Optional[str] = None


@dataclass
class TaskAttempt:
    task_id: str
    participant_id: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    completed: bool = False
    iterations: int = 0
    errors_encountered: List[str] = field(default_factory=list)
    generated_code: Optional[str] = None
    quality_score: float = 0.0
    tool_used: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SurveyResponse:
    participant_id: str
    survey_id: str
    responses: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class UsabilityMetrics:
    participant_id: str
    sus_score: float
    individual_scores: List[int]
    net_promoter_score: int
    task_load_index: Dict[str, float]
    custom_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ComparativeResult:
    participant_id: str
    task_id: str
    tool_a: str
    tool_b: str
    tool_a_time: float
    tool_b_time: float
    tool_a_success: bool
    tool_b_success: bool
    preference: str
    preference_reason: str


class UserStudyManager:
    def __init__(self, study_name: str, study_type: StudyType):
        self.study_name = study_name
        self.study_type = study_type
        self.participants: Dict[str, Participant] = {}
        self.tasks: Dict[str, StudyTask] = {}
        self.attempts: List[TaskAttempt] = []
        self.survey_responses: List[SurveyResponse] = []
        self.usability_metrics: List[UsabilityMetrics] = []
        self.comparative_results: List[ComparativeResult] = []
        self.created_at = datetime.now().isoformat()

    def add_participant(self, participant: Participant) -> str:
        self.participants[participant.id] = participant
        return participant.id

    def add_task(self, task: StudyTask):
        self.tasks[task.id] = task

    def start_task(
        self, task_id: str, participant_id: str, tool: str = "kube-tofu"
    ) -> TaskAttempt:
        attempt = TaskAttempt(
            task_id=task_id,
            participant_id=participant_id,
            start_time=datetime.now().isoformat(),
            tool_used=tool,
        )
        self.attempts.append(attempt)
        return attempt

    def complete_task(
        self,
        attempt: TaskAttempt,
        success: bool,
        generated_code: str,
        iterations: int = 1,
        errors: List[str] = None,
    ):
        attempt.end_time = datetime.now().isoformat()
        attempt.completed = success
        attempt.generated_code = generated_code
        attempt.iterations = iterations
        attempt.errors_encountered = errors or []

        start = datetime.fromisoformat(attempt.start_time)
        end = datetime.fromisoformat(attempt.end_time)
        attempt.duration_seconds = (end - start).total_seconds()

        if success and generated_code:
            attempt.quality_score = self._calculate_quality(attempt)

    def _calculate_quality(self, attempt: TaskAttempt) -> float:
        task = self.tasks.get(attempt.task_id)
        if not task:
            return 0.0

        score = 1.0

        if attempt.iterations > 1:
            score -= 0.1 * min(attempt.iterations - 1, 5)

        score -= 0.05 * min(len(attempt.errors_encountered), 5)

        expected_seconds = task.expected_time_minutes * 60
        if attempt.duration_seconds > expected_seconds:
            time_penalty = (
                attempt.duration_seconds - expected_seconds
            ) / expected_seconds
            score -= min(time_penalty * 0.2, 0.3)

        return max(0.0, min(1.0, score))

    def record_sus_survey(
        self,
        participant_id: str,
        responses: List[int],
    ) -> UsabilityMetrics:
        if len(responses) != 10:
            raise ValueError("SUS requires exactly 10 responses")

        adjusted = []
        for i, score in enumerate(responses):
            if i % 2 == 0:
                adjusted.append(score - 1)
            else:
                adjusted.append(5 - score)

        sus_score = sum(adjusted) * 2.5

        metrics = UsabilityMetrics(
            participant_id=participant_id,
            sus_score=sus_score,
            individual_scores=responses,
            net_promoter_score=0,
            task_load_index={},
        )

        self.usability_metrics.append(metrics)
        return metrics

    def record_nasa_tlx(
        self,
        participant_id: str,
        mental_demand: int,
        physical_demand: int,
        temporal_demand: int,
        performance: int,
        effort: int,
        frustration: int,
    ) -> Dict[str, float]:
        tlx = {
            "mental_demand": mental_demand,
            "physical_demand": physical_demand,
            "temporal_demand": temporal_demand,
            "performance": 20 - performance,
            "effort": effort,
            "frustration": frustration,
        }

        for metrics in self.usability_metrics:
            if metrics.participant_id == participant_id:
                metrics.task_load_index = tlx
                return tlx

        metrics = UsabilityMetrics(
            participant_id=participant_id,
            sus_score=0,
            individual_scores=[],
            net_promoter_score=0,
            task_load_index=tlx,
        )
        self.usability_metrics.append(metrics)
        return tlx

    def record_comparative_result(
        self,
        participant_id: str,
        task_id: str,
        tool_a: str,
        tool_b: str,
        tool_a_time: float,
        tool_b_time: float,
        tool_a_success: bool,
        tool_b_success: bool,
        preference: str,
        preference_reason: str,
    ):
        result = ComparativeResult(
            participant_id=participant_id,
            task_id=task_id,
            tool_a=tool_a,
            tool_b=tool_b,
            tool_a_time=tool_a_time,
            tool_b_time=tool_b_time,
            tool_a_success=tool_a_success,
            tool_b_success=tool_b_success,
            preference=preference,
            preference_reason=preference_reason,
        )
        self.comparative_results.append(result)

    def analyze_results(self) -> Dict[str, Any]:
        analysis = {
            "study_name": self.study_name,
            "study_type": self.study_type.value,
            "participants": len(self.participants),
            "total_attempts": len(self.attempts),
            "task_analysis": self._analyze_tasks(),
            "usability_analysis": self._analyze_usability(),
            "comparative_analysis": self._analyze_comparative(),
            "statistical_tests": self._run_statistical_tests(),
        }
        return analysis

    def _analyze_tasks(self) -> Dict[str, Any]:
        if not self.attempts:
            return {}

        completed = [a for a in self.attempts if a.completed]

        completion_rate = len(completed) / len(self.attempts) if self.attempts else 0

        durations = [a.duration_seconds for a in completed]
        avg_duration = statistics.mean(durations) if durations else 0

        iterations = [a.iterations for a in completed]
        avg_iterations = statistics.mean(iterations) if iterations else 0

        quality_scores = [a.quality_score for a in completed if a.quality_score > 0]
        avg_quality = statistics.mean(quality_scores) if quality_scores else 0

        per_task = {}
        for task_id in self.tasks:
            task_attempts = [a for a in self.attempts if a.task_id == task_id]
            task_completed = [a for a in task_attempts if a.completed]

            per_task[task_id] = {
                "attempts": len(task_attempts),
                "completed": len(task_completed),
                "completion_rate": len(task_completed) / len(task_attempts)
                if task_attempts
                else 0,
                "avg_duration": statistics.mean(
                    [a.duration_seconds for a in task_completed]
                )
                if task_completed
                else 0,
                "avg_iterations": statistics.mean(
                    [a.iterations for a in task_completed]
                )
                if task_completed
                else 0,
            }

        by_expertise = {}
        for level in ExpertiseLevel:
            participants_at_level = [
                p.id for p in self.participants.values() if p.expertise_level == level
            ]
            level_attempts = [
                a for a in self.attempts if a.participant_id in participants_at_level
            ]
            level_completed = [a for a in level_attempts if a.completed]

            by_expertise[level.value] = {
                "participants": len(participants_at_level),
                "attempts": len(level_attempts),
                "completion_rate": len(level_completed) / len(level_attempts)
                if level_attempts
                else 0,
            }

        return {
            "overall": {
                "completion_rate": completion_rate,
                "avg_duration_seconds": avg_duration,
                "avg_iterations": avg_iterations,
                "avg_quality_score": avg_quality,
            },
            "per_task": per_task,
            "by_expertise": by_expertise,
        }

    def _analyze_usability(self) -> Dict[str, Any]:
        if not self.usability_metrics:
            return {}

        sus_scores = [m.sus_score for m in self.usability_metrics if m.sus_score > 0]

        avg_sus = statistics.mean(sus_scores) if sus_scores else 0
        sus_grade = self._sus_grade(avg_sus)

        tlx_metrics = [
            m.task_load_index for m in self.usability_metrics if m.task_load_index
        ]

        avg_tlx = {}
        if tlx_metrics:
            for dim in [
                "mental_demand",
                "physical_demand",
                "temporal_demand",
                "performance",
                "effort",
                "frustration",
            ]:
                values = [t[dim] for t in tlx_metrics if dim in t]
                avg_tlx[dim] = statistics.mean(values) if values else 0

        return {
            "sus": {
                "average_score": avg_sus,
                "std_dev": statistics.stdev(sus_scores) if len(sus_scores) > 1 else 0,
                "grade": sus_grade,
                "interpretation": self._sus_interpretation(avg_sus),
            },
            "nasa_tlx": avg_tlx,
            "total_responses": len(self.usability_metrics),
        }

    def _sus_grade(self, score: float) -> str:
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 50:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _sus_interpretation(self, score: float) -> str:
        if score >= 85:
            return "Excellent - Users will likely recommend the system"
        elif score >= 70:
            return "Good - System is acceptable with minor improvements"
        elif score >= 50:
            return "OK - Marginal acceptability, improvements needed"
        else:
            return "Poor - Significant usability issues"

    def _analyze_comparative(self) -> Dict[str, Any]:
        if not self.comparative_results:
            return {}

        tools = set()
        for r in self.comparative_results:
            tools.add(r.tool_a)
            tools.add(r.tool_b)

        preferences = {}
        for tool in tools:
            preferred_count = sum(
                1
                for r in self.comparative_results
                if (r.tool_a == tool and r.preference == "a")
                or (r.tool_b == tool and r.preference == "b")
            )
            preferences[tool] = preferred_count / len(self.comparative_results)

        time_comparison = {}
        success_comparison = {}

        for tool in tools:
            times = []
            successes = []

            for r in self.comparative_results:
                if r.tool_a == tool:
                    times.append(r.tool_a_time)
                    successes.append(r.tool_a_success)
                elif r.tool_b == tool:
                    times.append(r.tool_b_time)
                    successes.append(r.tool_b_success)

            time_comparison[tool] = {
                "avg_time": statistics.mean(times) if times else 0,
                "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            }
            success_comparison[tool] = (
                sum(successes) / len(successes) if successes else 0
            )

        return {
            "tools_compared": list(tools),
            "preference_rates": preferences,
            "time_comparison": time_comparison,
            "success_rates": success_comparison,
        }

    def _run_statistical_tests(self) -> Dict[str, Any]:
        results = {}

        if len(self.comparative_results) >= 2:
            tool_a_times = [r.tool_a_time for r in self.comparative_results]
            tool_b_times = [r.tool_b_time for r in self.comparative_results]

            mean_diff = statistics.mean(
                [a - b for a, b in zip(tool_a_times, tool_b_times)]
            )
            std_diff = (
                statistics.stdev([a - b for a, b in zip(tool_a_times, tool_b_times)])
                if len(tool_a_times) > 1
                else 1
            )
            t_stat = (
                mean_diff / (std_diff / (len(tool_a_times) ** 0.5))
                if std_diff > 0
                else 0
            )

            results["paired_t_test"] = {
                "t_statistic": t_stat,
                "significant": abs(t_stat) > 2.0,
                "mean_difference": mean_diff,
            }

        if len(self.attempts) >= 2:
            completed = [a for a in self.attempts if a.completed]
            if completed:
                durations = [a.duration_seconds for a in completed]
                mean = statistics.mean(durations)
                std = statistics.stdev(durations) if len(durations) > 1 else 1

                expected = statistics.mean(
                    [
                        self.tasks[a.task_id].expected_time_minutes * 60
                        for a in completed
                        if a.task_id in self.tasks
                    ]
                )

                cohens_d = (mean - expected) / std if std > 0 else 0

                results["effect_size"] = {
                    "cohens_d": cohens_d,
                    "interpretation": self._interpret_effect_size(cohens_d),
                }

        return results

    def _interpret_effect_size(self, d: float) -> str:
        d = abs(d)
        if d < 0.2:
            return "Negligible"
        elif d < 0.5:
            return "Small"
        elif d < 0.8:
            return "Medium"
        else:
            return "Large"

    def generate_report(self) -> str:
        analysis = self.analyze_results()

        lines = []
        lines.append("=" * 70)
        lines.append(f"USER STUDY REPORT: {self.study_name}")
        lines.append(f"Study Type: {self.study_type.value}")
        lines.append("=" * 70)
        lines.append("")

        lines.append("PARTICIPANT SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Participants: {analysis['participants']}")

        by_exp = analysis.get("task_analysis", {}).get("by_expertise", {})
        for level, data in by_exp.items():
            lines.append(f"  {level}: {data['participants']} participants")
        lines.append("")

        lines.append("TASK COMPLETION ANALYSIS")
        lines.append("-" * 40)
        overall = analysis.get("task_analysis", {}).get("overall", {})
        lines.append(f"Total Attempts: {analysis['total_attempts']}")
        lines.append(f"Completion Rate: {overall.get('completion_rate', 0) * 100:.1f}%")
        lines.append(
            f"Avg Duration: {overall.get('avg_duration_seconds', 0) / 60:.1f} minutes"
        )
        lines.append(f"Avg Iterations: {overall.get('avg_iterations', 0):.1f}")
        lines.append(
            f"Avg Quality Score: {overall.get('avg_quality_score', 0) * 100:.1f}%"
        )
        lines.append("")

        usability = analysis.get("usability_analysis", {})
        if usability:
            lines.append("USABILITY METRICS")
            lines.append("-" * 40)
            sus = usability.get("sus", {})
            lines.append(
                f"SUS Score: {sus.get('average_score', 0):.1f} (Grade: {sus.get('grade', 'N/A')})"
            )
            lines.append(f"Interpretation: {sus.get('interpretation', 'N/A')}")

            tlx = usability.get("nasa_tlx", {})
            if tlx:
                lines.append("\nNASA-TLX Scores (1-20 scale):")
                for dim, score in tlx.items():
                    lines.append(f"  {dim.replace('_', ' ').title()}: {score:.1f}")
            lines.append("")

        comparative = analysis.get("comparative_analysis", {})
        if comparative:
            lines.append("COMPARATIVE ANALYSIS")
            lines.append("-" * 40)
            prefs = comparative.get("preference_rates", {})
            for tool, rate in prefs.items():
                lines.append(f"  {tool}: {rate * 100:.1f}% preference")
            lines.append("")

        stats = analysis.get("statistical_tests", {})
        if stats:
            lines.append("STATISTICAL ANALYSIS")
            lines.append("-" * 40)

            t_test = stats.get("paired_t_test", {})
            if t_test:
                sig = "Yes" if t_test.get("significant") else "No"
                lines.append(
                    f"Paired t-test: t={t_test.get('t_statistic', 0):.2f}, Significant: {sig}"
                )

            effect = stats.get("effect_size", {})
            if effect:
                lines.append(
                    f"Effect Size (Cohen's d): {effect.get('cohens_d', 0):.2f} ({effect.get('interpretation', 'N/A')})"
                )

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


class ABTestRunner:
    def __init__(self, test_name: str, variants: List[str]):
        self.test_name = test_name
        self.variants = variants
        self.assignments: Dict[str, str] = {}
        self.results: Dict[str, List[Dict]] = {v: [] for v in variants}

    def assign_variant(self, participant_id: str) -> str:
        if participant_id in self.assignments:
            return self.assignments[participant_id]

        variant = random.choice(self.variants)
        self.assignments[participant_id] = variant
        return variant

    def record_result(
        self,
        participant_id: str,
        success: bool,
        duration: float,
        quality: float = 0.0,
        metadata: Dict[str, Any] = None,
    ):
        variant = self.assignments.get(participant_id)
        if not variant:
            return

        self.results[variant].append(
            {
                "participant_id": participant_id,
                "success": success,
                "duration": duration,
                "quality": quality,
                "metadata": metadata or {},
            }
        )

    def analyze(self) -> Dict[str, Any]:
        analysis = {
            "test_name": self.test_name,
            "variants": {},
        }

        for variant in self.variants:
            results = self.results[variant]
            if not results:
                continue

            successes = [r for r in results if r["success"]]
            durations = [r["duration"] for r in successes]
            qualities = [r["quality"] for r in successes if r["quality"] > 0]

            analysis["variants"][variant] = {
                "participants": len(results),
                "success_rate": len(successes) / len(results),
                "avg_duration": statistics.mean(durations) if durations else 0,
                "avg_quality": statistics.mean(qualities) if qualities else 0,
            }

        if len(self.variants) == 2:
            v1, v2 = self.variants
            r1, r2 = self.results[v1], self.results[v2]

            if r1 and r2:
                s1 = sum(1 for r in r1 if r["success"])
                s2 = sum(1 for r in r2 if r["success"])
                n1, n2 = len(r1), len(r2)

                p1, p2 = s1 / n1, s2 / n2
                p_pooled = (s1 + s2) / (n1 + n2)

                se = (p_pooled * (1 - p_pooled) * (1 / n1 + 1 / n2)) ** 0.5
                z = (p1 - p2) / se if se > 0 else 0

                analysis["statistical_test"] = {
                    "z_statistic": z,
                    "significant": abs(z) > 1.96,
                    "confidence_level": "95%",
                }

        return analysis


def create_iac_user_study() -> UserStudyManager:
    study = UserStudyManager(
        study_name="Kube-Tofu IaC Generation Usability Study",
        study_type=StudyType.USABILITY,
    )

    study.add_task(
        StudyTask(
            id="task_001",
            name="Basic Docker Container",
            description="Create a Dockerfile for a Python Flask application",
            difficulty=TaskDifficulty.EASY,
            expected_time_minutes=5,
            requirements=["Python 3.11", "Flask", "Port 5000"],
            success_criteria=["Valid Dockerfile", "Builds successfully", "App runs"],
            iac_type="dockerfile",
        )
    )

    study.add_task(
        StudyTask(
            id="task_002",
            name="Kubernetes Deployment",
            description="Create a Kubernetes deployment with 3 replicas and a service",
            difficulty=TaskDifficulty.MEDIUM,
            expected_time_minutes=10,
            requirements=["Deployment", "Service", "3 replicas", "Load balancer"],
            success_criteria=[
                "Valid YAML",
                "Deploys successfully",
                "Service accessible",
            ],
            iac_type="kubernetes",
        )
    )

    study.add_task(
        StudyTask(
            id="task_003",
            name="AWS Infrastructure",
            description="Create Terraform for VPC with public and private subnets",
            difficulty=TaskDifficulty.HARD,
            expected_time_minutes=20,
            requirements=[
                "VPC",
                "2 public subnets",
                "2 private subnets",
                "NAT Gateway",
            ],
            success_criteria=["Valid HCL", "Plan succeeds", "Resources created"],
            iac_type="terraform",
        )
    )

    study.add_task(
        StudyTask(
            id="task_004",
            name="Multi-Service Application",
            description="Create docker-compose for a web app with database and cache",
            difficulty=TaskDifficulty.MEDIUM,
            expected_time_minutes=15,
            requirements=["Web service", "PostgreSQL", "Redis", "Networking"],
            success_criteria=["Valid YAML", "Services start", "Connectivity works"],
            iac_type="docker-compose",
        )
    )

    study.add_task(
        StudyTask(
            id="task_005",
            name="Helm Chart",
            description="Create a Helm chart for a microservice with configurable values",
            difficulty=TaskDifficulty.HARD,
            expected_time_minutes=25,
            requirements=[
                "values.yaml",
                "Deployment template",
                "Service template",
                "Ingress",
            ],
            success_criteria=["Valid chart", "Installs successfully", "Values work"],
            iac_type="helm",
        )
    )

    return study


def run_simulated_user_study(verbose: bool = True) -> Dict[str, Any]:
    study = create_iac_user_study()

    expertise_dist = [
        (ExpertiseLevel.NOVICE, 10),
        (ExpertiseLevel.INTERMEDIATE, 15),
        (ExpertiseLevel.EXPERT, 5),
    ]

    participant_id = 0
    for level, count in expertise_dist:
        for i in range(count):
            participant_id += 1
            study.add_participant(
                Participant(
                    id=f"P{participant_id:03d}",
                    expertise_level=level,
                    years_experience=random.randint(0, 10)
                    if level != ExpertiseLevel.NOVICE
                    else random.randint(0, 2),
                    familiar_tools=random.sample(
                        ["Terraform", "Docker", "Kubernetes", "Ansible", "Helm"],
                        k=random.randint(1, 4),
                    ),
                    consent_given=True,
                )
            )

    if verbose:
        print(f"Simulating user study with {len(study.participants)} participants...")

    for pid, participant in study.participants.items():
        for task_id, task in study.tasks.items():
            base_success_rate = 0.5
            if participant.expertise_level == ExpertiseLevel.INTERMEDIATE:
                base_success_rate = 0.7
            elif participant.expertise_level == ExpertiseLevel.EXPERT:
                base_success_rate = 0.9

            if task.difficulty == TaskDifficulty.HARD:
                base_success_rate -= 0.2
            elif task.difficulty == TaskDifficulty.EASY:
                base_success_rate += 0.15

            success = random.random() < base_success_rate

            base_duration = task.expected_time_minutes * 60
            if participant.expertise_level == ExpertiseLevel.NOVICE:
                duration = base_duration * random.uniform(1.2, 2.0)
            elif participant.expertise_level == ExpertiseLevel.EXPERT:
                duration = base_duration * random.uniform(0.5, 0.9)
            else:
                duration = base_duration * random.uniform(0.8, 1.3)

            iterations = random.randint(1, 5) if success else random.randint(3, 10)

            attempt = study.start_task(task_id, pid, "kube-tofu")
            attempt.end_time = datetime.now().isoformat()
            attempt.duration_seconds = duration

            study.complete_task(
                attempt,
                success=success,
                generated_code=f"# Generated code for {task.name}",
                iterations=iterations,
            )

        sus_base = 50
        if participant.expertise_level == ExpertiseLevel.EXPERT:
            sus_base = 75
        elif participant.expertise_level == ExpertiseLevel.INTERMEDIATE:
            sus_base = 65

        sus_responses = [
            max(1, min(5, int(sus_base / 20) + random.randint(-1, 1)))
            for _ in range(10)
        ]
        study.record_sus_survey(pid, sus_responses)

        study.record_nasa_tlx(
            pid,
            mental_demand=random.randint(8, 16),
            physical_demand=random.randint(2, 6),
            temporal_demand=random.randint(6, 14),
            performance=random.randint(10, 18),
            effort=random.randint(8, 16),
            frustration=random.randint(4, 12),
        )

    for pid in list(study.participants.keys())[:10]:
        study.record_comparative_result(
            participant_id=pid,
            task_id="task_001",
            tool_a="kube-tofu",
            tool_b="manual",
            tool_a_time=random.uniform(120, 300),
            tool_b_time=random.uniform(300, 600),
            tool_a_success=random.random() < 0.85,
            tool_b_success=random.random() < 0.7,
            preference=random.choice(["a", "a", "a", "b"]),
            preference_reason=random.choice(
                [
                    "Faster iteration",
                    "Better suggestions",
                    "More intuitive",
                    "Prefer manual control",
                ]
            ),
        )

    if verbose:
        print("\nAnalyzing results...")
        report = study.generate_report()
        print(report)

    return study.analyze_results()


if __name__ == "__main__":
    run_simulated_user_study()
