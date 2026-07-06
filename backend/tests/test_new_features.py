import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_llm_providers():
    print("\n" + "=" * 60)
    print("Testing LLM Providers")
    print("=" * 60)

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "llm_providers", Path(__file__).parent.parent / "agents" / "llm_providers.py"
    )
    llm_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(llm_module)

    UnifiedLLMProvider = llm_module.UnifiedLLMProvider
    MockProvider = llm_module.MockProvider
    LLMConfig = llm_module.LLMConfig
    LLMProvider = llm_module.LLMProvider

    config = LLMConfig(provider=LLMProvider.MOCK, model="mock")
    provider = MockProvider(config)

    response = provider.generate("Create a Dockerfile for Python Flask app")
    print(f"✅ Mock provider generation: {len(response.content)} chars")
    print(f"   Model: {response.model}")
    print(f"   Latency: {response.latency_ms:.2f}ms")
    print(f"   Tokens: {response.tokens_used}")

    unified = UnifiedLLMProvider()
    print(f"✅ Unified provider initialized: {unified.provider}")

    response = unified.generate("Create a Kubernetes deployment")
    print(f"✅ Unified generation: {len(response.content)} chars")

    return True


def test_dpiac_eval():
    print("\n" + "=" * 60)
    print("Testing DPIaC-Eval Benchmark")
    print("=" * 60)

    from evaluation.dpiac_eval import (
        DPIaCEvalBenchmark,
    )

    benchmark = DPIaCEvalBenchmark(max_iterations=3)
    print(f"✅ Loaded {len(benchmark.scenarios)} scenarios")

    categories = set(s.category for s in benchmark.scenarios)
    print(f"   Categories: {len(categories)}")

    difficulties = set(s.difficulty for s in benchmark.scenarios)
    print(f"   Difficulties: {len(difficulties)}")

    def mock_generator(request: str, iteration: int, feedback):
        return """
terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

resource "aws_instance" "main" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
}

resource "aws_security_group" "main" {
  name = "main-sg"
  ingress {
    cidr_blocks = ["0.0.0.0/0"]
  }
}
"""

    results = benchmark.run_benchmark(
        generator_fn=mock_generator,
        scenarios=benchmark.scenarios[:3],
        verbose=False,
    )

    print("✅ Benchmark run complete:")
    print(f"   Total: {results.total_scenarios}")
    print(f"   Successful: {results.successful}")
    print(f"   Pass@1: {results.pass_at_1 * 100:.1f}%")
    print(f"   Avg Iterations: {results.avg_iterations:.2f}")

    return True


def test_cloud_testing():
    print("\n" + "=" * 60)
    print("Testing Cloud Deployment")
    print("=" * 60)

    from evaluation.cloud_testing import (
        CloudDeploymentRunner,
        DockerTester,
        DeploymentConfig,
        CloudProvider,
    )

    config = DeploymentConfig(
        provider=CloudProvider.LOCAL_DOCKER,
        dry_run=True,
    )

    tester = DockerTester(config)

    dockerfile = """FROM python:3.11-slim
WORKDIR /app
COPY . .
CMD ["python", "app.py"]"""

    result = tester.deploy(dockerfile, "dockerfile")

    print("✅ Docker deployment test (dry-run):")
    print(f"   Success: {result.success}")
    print(f"   Status: {result.status.value}")
    print(f"   Time: {result.deployment_time_ms:.2f}ms")

    runner = CloudDeploymentRunner()
    result = runner.test_deployment(
        dockerfile,
        "dockerfile",
        CloudProvider.LOCAL_DOCKER,
    )

    print("✅ Cloud runner test complete:")
    summary = runner.get_summary()
    print(f"   Total tests: {summary['total_tests']}")
    print(f"   Success rate: {summary['success_rate'] * 100:.1f}%")

    return True


def test_security_cve():
    print("\n" + "=" * 60)
    print("Testing Security CVE Detection")
    print("=" * 60)

    from evaluation.security_cve import (
        SecurityScanner,
        CVEDatabase,
        Severity,
    )

    db = CVEDatabase()
    print(f"✅ CVE database loaded: {len(db.cves)} CVEs")

    k8s_cves = db.search_by_product("kubernetes")
    print(f"   Kubernetes CVEs: {len(k8s_cves)}")

    critical_cves = db.search_by_severity(Severity.CRITICAL)
    print(f"   Critical CVEs: {len(critical_cves)}")

    scanner = SecurityScanner()
    print(f"✅ Security scanner initialized: {len(scanner.rules)} rules")

    terraform_code = """
provider "aws" {
  access_key = "AKIAIOSFODNN7EXAMPLE"
  secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}

resource "aws_security_group" "open" {
  ingress {
    cidr_blocks = ["0.0.0.0/0"]
  }
}
"""

    result = scanner.scan(terraform_code, "terraform")

    print("✅ Terraform scan results:")
    print(f"   Total vulnerabilities: {result.total_vulnerabilities}")
    print(f"   Critical: {result.critical_count}")
    print(f"   High: {result.high_count}")
    print(f"   Secrets found: {result.secrets_found}")
    print(f"   Misconfigurations: {result.misconfigurations_found}")

    k8s_code = """
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    securityContext:
      privileged: true
      runAsUser: 0
"""

    result = scanner.scan(k8s_code, "kubernetes")

    print("✅ Kubernetes scan results:")
    print(f"   Total vulnerabilities: {result.total_vulnerabilities}")
    print(f"   Critical: {result.critical_count}")

    print("   Compliance status:")
    for framework, compliant in result.compliance_status.items():
        status = "✅" if compliant else "❌"
        print(f"     {framework}: {status}")

    return True


def test_user_studies():
    print("\n" + "=" * 60)
    print("Testing User Studies Framework")
    print("=" * 60)

    from evaluation.user_studies import (
        ABTestRunner,
        Participant,
        ExpertiseLevel,
        create_iac_user_study,
    )

    study = create_iac_user_study()
    print(f"✅ User study created: {study.study_name}")
    print(f"   Type: {study.study_type.value}")
    print(f"   Tasks: {len(study.tasks)}")

    participant = Participant(
        id="TEST001",
        expertise_level=ExpertiseLevel.INTERMEDIATE,
        years_experience=5,
        familiar_tools=["Terraform", "Kubernetes", "Docker"],
        consent_given=True,
    )
    study.add_participant(participant)
    print(f"✅ Participant added: {participant.id}")

    task_id = list(study.tasks.keys())[0]
    attempt = study.start_task(task_id, participant.id, "kube-tofu")
    print(f"✅ Task started: {task_id}")

    study.complete_task(
        attempt,
        success=True,
        generated_code="# Test code",
        iterations=2,
    )
    print("✅ Task completed:")
    print(f"   Duration: {attempt.duration_seconds:.2f}s")
    print(f"   Iterations: {attempt.iterations}")
    print(f"   Quality Score: {attempt.quality_score:.2f}")

    sus_responses = [4, 2, 4, 3, 4, 2, 5, 2, 4, 2]
    metrics = study.record_sus_survey(participant.id, sus_responses)
    print("✅ SUS survey recorded:")
    print(f"   Score: {metrics.sus_score:.1f}")

    study.record_nasa_tlx(
        participant.id,
        mental_demand=12,
        physical_demand=3,
        temporal_demand=10,
        performance=15,
        effort=12,
        frustration=6,
    )
    print("✅ NASA-TLX recorded")

    ab_test = ABTestRunner("Feature Test", ["control", "treatment"])
    variant = ab_test.assign_variant("user1")
    ab_test.record_result("user1", success=True, duration=120, quality=0.9)
    print(f"✅ A/B test recorded: user1 -> {variant}")

    analysis = ab_test.analyze()
    print(f"   Variants: {list(analysis['variants'].keys())}")

    return True


def run_all_tests():
    print("🧪 Kube-Tofu New Features Test Suite")
    print("=" * 60)

    tests = [
        ("LLM Providers", test_llm_providers),
        ("DPIaC-Eval Benchmark", test_dpiac_eval),
        ("Cloud Deployment Testing", test_cloud_testing),
        ("Security CVE Detection", test_security_cve),
        ("User Studies Framework", test_user_studies),
    ]

    results = []

    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success, None))
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False, str(e)))

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {name}")
        if error:
            print(f"         Error: {error}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
