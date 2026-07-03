import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))


def setup_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kubetofu",
        description="Kube-Tofu: Deep Agentic IaC Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze a project and generate IaC
    kubetofu analyze ./my-project
    
    # Generate IaC from natural language
    kubetofu generate "Create a Kubernetes deployment for a Python API"
    
    # Generate IaC with project context
    kubetofu generate "Add Redis caching" --context ./my-project
    
    # Validate IaC files
    kubetofu validate ./terraform --type terraform
    
    # Interactive chat mode
    kubetofu chat
    
    # Run evaluation benchmarks
    kubetofu eval --benchmark classification
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze existing source code and generate IaC"
    )
    analyze_parser.add_argument("project_path", help="Path to project directory")
    analyze_parser.add_argument("-o", "--output", help="Output directory")
    analyze_parser.add_argument(
        "-f",
        "--format",
        choices=[
            "all",
            "dockerfile",
            "docker-compose",
            "kubernetes",
            "helm",
            "terraform",
            "ansible",
        ],
        default="all",
    )
    analyze_parser.add_argument("--json", action="store_true", help="Output as JSON")
    analyze_parser.add_argument("-v", "--verbose", action="store_true")

    generate_parser = subparsers.add_parser(
        "generate", help="Generate IaC from natural language using deep agents"
    )
    generate_parser.add_argument("request", help="Natural language request")
    generate_parser.add_argument(
        "-c", "--context", help="Project directory for context"
    )
    generate_parser.add_argument(
        "-f",
        "--format",
        choices=[
            "auto",
            "dockerfile",
            "docker-compose",
            "kubernetes",
            "helm",
            "terraform",
            "ansible",
            "vagrant",
        ],
        default="auto",
    )
    generate_parser.add_argument("-o", "--output", help="Output directory")
    generate_parser.add_argument("--max-iterations", type=int, default=5)
    generate_parser.add_argument("--model", default="gpt-4", help="LLM model to use")
    generate_parser.add_argument("-v", "--verbose", action="store_true")

    validate_parser = subparsers.add_parser(
        "validate", help="Validate IaC configurations"
    )
    validate_parser.add_argument("path", help="Path to IaC file or directory")
    validate_parser.add_argument(
        "-t",
        "--type",
        choices=[
            "auto",
            "terraform",
            "kubernetes",
            "dockerfile",
            "docker-compose",
            "ansible",
            "helm",
        ],
        default="auto",
    )
    validate_parser.add_argument(
        "--strict", action="store_true", help="Fail on warnings"
    )
    validate_parser.add_argument("--json", action="store_true")

    chat_parser = subparsers.add_parser(
        "chat", help="Interactive chat mode with deep agents"
    )
    chat_parser.add_argument("-c", "--context", help="Project directory for context")
    chat_parser.add_argument("--model", default="gpt-4")
    chat_parser.add_argument(
        "--memory", action="store_true", help="Enable persistent memory"
    )

    eval_parser = subparsers.add_parser("eval", help="Run evaluation benchmarks")
    eval_parser.add_argument(
        "-b",
        "--benchmark",
        choices=[
            "all",
            "classification",
            "optimization",
            "anomaly",
            "generation",
            "dpiac",
            "security",
            "cloud",
            "userstudy",
        ],
        default="all",
    )
    eval_parser.add_argument("--samples", type=int, default=500)
    eval_parser.add_argument("--seed", type=int, default=42)
    eval_parser.add_argument("--json", action="store_true")

    security_parser = subparsers.add_parser(
        "security", help="Run security vulnerability scan on IaC"
    )
    security_parser.add_argument("path", help="Path to IaC file or directory")
    security_parser.add_argument(
        "-t",
        "--type",
        choices=[
            "auto",
            "terraform",
            "kubernetes",
            "dockerfile",
            "docker-compose",
            "ansible",
            "helm",
        ],
        default="auto",
    )
    security_parser.add_argument("--json", action="store_true")
    security_parser.add_argument(
        "--strict", action="store_true", help="Fail on any vulnerability"
    )

    dpiac_parser = subparsers.add_parser("dpiac", help="Run DPIaC-Eval benchmark")
    dpiac_parser.add_argument("--max-iterations", type=int, default=10)
    dpiac_parser.add_argument("--json", action="store_true")
    dpiac_parser.add_argument("-v", "--verbose", action="store_true")

    deploy_parser = subparsers.add_parser(
        "deploy", help="Deploy IaC to cloud providers"
    )
    deploy_parser.add_argument("path", help="Path to IaC directory")
    deploy_parser.add_argument(
        "-p",
        "--provider",
        choices=["auto", "aws", "arvancloud", "gcp", "azure", "local"],
        default="auto",
    )
    deploy_parser.add_argument("--dry-run", action="store_true")
    deploy_parser.add_argument(
        "--approve", action="store_true", help="Auto-approve changes"
    )

    return parser


def cmd_analyze(args):
    from analyzers.project_analyzer import ProjectAnalyzer
    from analyzers.iac_generator import IaCFromSourceGenerator

    project_path = os.path.abspath(args.project_path)
    if not os.path.isdir(project_path):
        print(f"❌ Error: '{project_path}' is not a valid directory")
        return 1

    print(f"🔍 Analyzing project: {project_path}")

    analyzer = ProjectAnalyzer(project_path)
    info = analyzer.analyze()

    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
        return 0

    print("\n📊 Analysis Results:")
    print(f"   Name: {info.name}")
    print(f"   Language: {info.language.value}")
    print(f"   Frameworks: {', '.join(f.value for f in info.frameworks)}")
    print(f"   Service Type: {info.service_type.value}")
    print(f"   Dependencies: {len(info.dependencies)}")
    print(f"   Ports: {', '.join(str(p.port) for p in info.ports)}")

    if info.databases:
        print(f"   Databases: {', '.join(d.type for d in info.databases)}")

    if args.verbose and info.env_vars:
        print("\n   Environment Variables:")
        for env in info.env_vars[:10]:
            print(f"     - {env.name}")

    print("\n🏗️  Generating IaC configurations...")

    generator = IaCFromSourceGenerator(info)
    iac = generator.generate_all()

    output_dir = args.output or os.path.join(project_path, "generated-iac")
    os.makedirs(output_dir, exist_ok=True)

    iac.save_to_directory(output_dir)

    print(f"\n✅ IaC files generated in: {output_dir}")
    return 0


def cmd_generate(args):
    from agents.deep_iac_agent import DeepIaCAgent
    from analyzers.project_analyzer import ProjectAnalyzer

    print("🤖 Kube-Tofu Deep Agent")
    print(f"📝 Request: {args.request}")

    project_context = None
    if args.context:
        context_path = os.path.abspath(args.context)
        if os.path.isdir(context_path):
            print(f"📂 Loading context from: {context_path}")
            analyzer = ProjectAnalyzer(context_path)
            project_info = analyzer.analyze()
            project_context = {
                "project_info": project_info.to_dict(),
                "files": _load_project_files(context_path),
            }

    agent = DeepIaCAgent(
        model=args.model,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
    )

    print(f"\n🔄 Generating IaC (max {args.max_iterations} iterations)...")

    result = agent.generate(
        request=args.request,
        format_hint=args.format if args.format != "auto" else None,
        project_context=project_context,
    )

    if result.success:
        print("\n✅ Generation successful!")
        print(f"   Iterations: {result.iterations}")
        print(f"   Format: {result.format}")

        output_dir = args.output or "./generated-iac"
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, result.filename)
        with open(output_file, "w") as f:
            f.write(result.code)

        print(f"   Output: {output_file}")

        if args.verbose:
            print("\n📄 Generated Code:\n")
            print(result.code)
    else:
        print(f"\n❌ Generation failed after {result.iterations} iterations")
        if result.errors:
            print(f"   Errors: {result.errors}")
        return 1

    return 0


def cmd_validate(args):
    from evaluation.validators import validate_iac

    path = os.path.abspath(args.path)

    if not os.path.exists(path):
        print(f"❌ Error: '{path}' does not exist")
        return 1

    files_to_validate = []

    if os.path.isfile(path):
        files_to_validate.append(path)
    else:
        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d
                for d in dirs
                if d not in ["node_modules", "__pycache__", ".git", "venv", ".venv"]
            ]
            for file in files:
                filepath = os.path.join(root, file)
                files_to_validate.append(filepath)

    print(f"🔍 Validating {len(files_to_validate)} files...")

    results = []
    errors = 0
    warnings = 0

    for filepath in files_to_validate:
        iac_type = args.type
        if iac_type == "auto":
            iac_type = _detect_iac_type(filepath)

        if not iac_type:
            continue

        try:
            with open(filepath, "r") as f:
                content = f.read()

            result = validate_iac(content, iac_type)
            rel_path = os.path.relpath(
                filepath, path if os.path.isdir(path) else os.path.dirname(path)
            )

            results.append(
                {
                    "file": rel_path,
                    "type": iac_type,
                    "valid": result.valid,
                    "stage": result.stage_reached.value,
                    "errors": len(result.errors),
                    "warnings": len(result.warnings),
                }
            )

            errors += len(result.errors)
            warnings += len(result.warnings)

            if not args.json:
                status = "✅" if result.valid else "❌"
                print(f"  {status} {rel_path} ({iac_type})")

                for err in result.errors:
                    print(f"      ❌ {err.message}")

                if args.verbose:
                    for warn in result.warnings:
                        print(f"      ⚠️  {warn.message}")

        except Exception as e:
            if not args.json:
                print(f"  ❌ {filepath}: {e}")

    if args.json:
        print(
            json.dumps(
                {
                    "files": results,
                    "total_errors": errors,
                    "total_warnings": warnings,
                },
                indent=2,
            )
        )
    else:
        print(
            f"\n📊 Summary: {len(results)} files, {errors} errors, {warnings} warnings"
        )

    if args.strict and warnings > 0:
        return 1

    return 0 if errors == 0 else 1


def cmd_chat(args):
    from agents.deep_iac_agent import DeepIaCAgent, AgentMemory

    print("🤖 Kube-Tofu Interactive Chat")
    print("   Type 'quit' or 'exit' to end the session")
    print("   Type 'clear' to clear memory")
    print("   Type 'context /path' to load project context")
    print()

    memory = AgentMemory() if args.memory else None
    agent = DeepIaCAgent(model=args.model, memory=memory)

    project_context = None
    if args.context:
        project_context = _load_context(args.context)
        print(f"📂 Loaded context from: {args.context}")

    while True:
        try:
            user_input = input("\n👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["quit", "exit"]:
            print("👋 Goodbye!")
            break

        if user_input.lower() == "clear":
            if memory:
                memory.clear()
            print("🧹 Memory cleared")
            continue

        if user_input.lower().startswith("context "):
            path = user_input[8:].strip()
            project_context = _load_context(path)
            print(f"📂 Loaded context from: {path}")
            continue

        print("\n🤖 Agent: ", end="", flush=True)

        try:
            response = agent.chat(
                message=user_input,
                project_context=project_context,
            )
            print(response)
        except Exception as e:
            print(f"❌ Error: {e}")


def cmd_eval(args):
    from evaluation.ml_evaluation import (
        ClassifierEvaluator,
        OptimizationEvaluator,
        AnomalyDetectorEvaluator,
        run_full_evaluation,
    )

    print("🧪 Kube-Tofu Evaluation")
    print(f"   Benchmark: {args.benchmark}")
    print(f"   Samples: {args.samples}")
    print(f"   Seed: {args.seed}")
    print()

    if args.benchmark == "all":
        results = run_full_evaluation(seed=args.seed)
    elif args.benchmark == "dpiac":
        return cmd_dpiac_eval(args)
    elif args.benchmark == "security":
        return cmd_security_eval(args)
    elif args.benchmark == "cloud":
        return cmd_cloud_eval(args)
    elif args.benchmark == "userstudy":
        return cmd_userstudy_eval(args)
    else:
        results = {"benchmark": args.benchmark, "seed": args.seed}

        if args.benchmark == "classification":
            evaluator = ClassifierEvaluator(seed=args.seed)
            results["classification"] = {
                name: r.to_dict()
                for name, r in evaluator.evaluate_all(n_samples=args.samples).items()
            }
        elif args.benchmark == "optimization":
            evaluator = OptimizationEvaluator(seed=args.seed)
            results["optimization"] = {
                name: r.to_dict() for name, r in evaluator.evaluate_all().items()
            }
        elif args.benchmark == "anomaly":
            evaluator = AnomalyDetectorEvaluator(seed=args.seed)
            results["anomaly_detection"] = {
                name: r.to_dict()
                for name, r in evaluator.evaluate_all(n_samples=args.samples).items()
            }

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_eval_results(results)

    return 0


def cmd_dpiac_eval(args):
    from evaluation.dpiac_eval import run_dpiac_eval

    print("🧪 Running DPIaC-Eval Benchmark")
    print("=" * 60)

    results = run_dpiac_eval(verbose=not args.json if hasattr(args, "json") else True)

    if hasattr(args, "json") and args.json:
        print(
            json.dumps(
                {
                    "total_scenarios": results.total_scenarios,
                    "successful": results.successful,
                    "pass_at_1": results.pass_at_1,
                    "pass_at_5": results.pass_at_5,
                    "pass_at_10": results.pass_at_10,
                    "avg_iterations": results.avg_iterations,
                    "intent_alignment": results.intent_alignment_rate,
                    "by_difficulty": results.by_difficulty,
                    "by_category": results.by_category,
                },
                indent=2,
            )
        )

    return 0


def cmd_security_eval(args):
    from evaluation.security_cve import run_cve_detection_tests

    print("🔒 Running Security CVE Detection Tests")
    print("=" * 60)

    results = run_cve_detection_tests(
        verbose=not args.json if hasattr(args, "json") else True
    )

    if hasattr(args, "json") and args.json:
        print(json.dumps(results, indent=2))

    return 0


def cmd_cloud_eval(args):
    from evaluation.cloud_testing import run_cloud_deployment_tests

    print("☁️ Running Cloud Deployment Tests")
    print("=" * 60)

    results = run_cloud_deployment_tests(
        verbose=not args.json if hasattr(args, "json") else True
    )

    if hasattr(args, "json") and args.json:
        print(json.dumps(results, indent=2))

    return 0


def cmd_userstudy_eval(args):
    from evaluation.user_studies import run_simulated_user_study

    print("👥 Running Simulated User Study")
    print("=" * 60)

    results = run_simulated_user_study(
        verbose=not args.json if hasattr(args, "json") else True
    )

    if hasattr(args, "json") and args.json:
        print(json.dumps(results, indent=2, default=str))

    return 0


def cmd_security(args):
    from evaluation.security_cve import SecurityScanner

    path = os.path.abspath(args.path)

    if not os.path.exists(path):
        print(f"❌ Error: '{path}' does not exist")
        return 1

    print(f"🔒 Security Scan: {path}")
    print("=" * 60)

    scanner = SecurityScanner()

    files_to_scan = []

    if os.path.isfile(path):
        files_to_scan.append(path)
    else:
        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d
                for d in dirs
                if d not in ["node_modules", "__pycache__", ".git", "venv", ".venv"]
            ]
            for file in files:
                filepath = os.path.join(root, file)
                files_to_scan.append(filepath)

    all_results = []
    total_vulns = 0
    total_critical = 0
    total_high = 0

    for filepath in files_to_scan:
        iac_type = args.type
        if iac_type == "auto":
            iac_type = _detect_iac_type(filepath)

        if not iac_type:
            continue

        try:
            with open(filepath, "r") as f:
                content = f.read()

            result = scanner.scan(content, iac_type, filepath)

            if result.total_vulnerabilities > 0:
                rel_path = os.path.relpath(
                    filepath, os.path.dirname(path) if os.path.isfile(path) else path
                )

                all_results.append(
                    {
                        "file": rel_path,
                        "type": iac_type,
                        "vulnerabilities": result.total_vulnerabilities,
                        "critical": result.critical_count,
                        "high": result.high_count,
                        "medium": result.medium_count,
                        "low": result.low_count,
                    }
                )

                total_vulns += result.total_vulnerabilities
                total_critical += result.critical_count
                total_high += result.high_count

                if not args.json:
                    print(f"\n📄 {rel_path} ({iac_type})")
                    for vuln in result.vulnerabilities:
                        severity_icon = {
                            "critical": "🔴",
                            "high": "🟠",
                            "medium": "🟡",
                            "low": "🔵",
                            "info": "ℹ️",
                        }.get(vuln.severity.value, "⚪")

                        print(
                            f"  {severity_icon} [{vuln.severity.value.upper()}] {vuln.title}"
                        )
                        if vuln.line_number:
                            print(f"      Line: {vuln.line_number}")
                        if vuln.remediation:
                            print(f"      Fix: {vuln.remediation}")

        except Exception as e:
            if not args.json:
                print(f"  ⚠️ Error scanning {filepath}: {e}")

    if args.json:
        print(
            json.dumps(
                {
                    "files_scanned": len(files_to_scan),
                    "total_vulnerabilities": total_vulns,
                    "critical": total_critical,
                    "high": total_high,
                    "results": all_results,
                },
                indent=2,
            )
        )
    else:
        print("\n" + "=" * 60)
        print(f"📊 Summary: {len(files_to_scan)} files scanned")
        print(f"   Total Vulnerabilities: {total_vulns}")
        print(f"   Critical: {total_critical}")
        print(f"   High: {total_high}")

    if args.strict and total_vulns > 0:
        return 1
    if total_critical > 0:
        return 1

    return 0


def cmd_dpiac(args):
    from evaluation.dpiac_eval import run_dpiac_eval

    print("🧪 Running DPIaC-Eval Benchmark")
    print("=" * 60)

    results = run_dpiac_eval(verbose=args.verbose)

    if args.json:
        print(
            json.dumps(
                {
                    "total_scenarios": results.total_scenarios,
                    "successful": results.successful,
                    "pass_at_1": results.pass_at_1,
                    "pass_at_5": results.pass_at_5,
                    "pass_at_10": results.pass_at_10,
                    "pass_at_25": results.pass_at_25,
                    "avg_iterations": results.avg_iterations,
                    "avg_time_ms": results.avg_time_ms,
                    "intent_alignment_rate": results.intent_alignment_rate,
                    "security_compliance_rate": results.security_compliance_rate,
                    "by_difficulty": results.by_difficulty,
                    "by_category": results.by_category,
                },
                indent=2,
            )
        )

    return 0


def cmd_deploy(args):
    print("🚀 Kube-Tofu Deploy")
    print(f"   Path: {args.path}")
    print(f"   Provider: {args.provider}")
    print(f"   Dry Run: {args.dry_run}")
    print()

    print("⚠️  Deployment not yet implemented")
    print("   This feature requires cloud provider credentials and API integration")
    print()
    print("   @TODO: Implement deployment for:")
    print("     - AWS (terraform apply)")
    print("     - ArvanCloud (terraform apply)")
    print("     - Kubernetes (kubectl apply)")
    print("     - Docker (docker-compose up)")

    return 0


def _load_project_files(project_path: str, max_files: int = 50) -> Dict[str, str]:
    files = {}
    important_patterns = [
        "*.py",
        "*.js",
        "*.ts",
        "*.go",
        "*.java",
        "*.yaml",
        "*.yml",
        "*.json",
        "*.toml",
        "Dockerfile*",
        "docker-compose*",
        "*.tf",
        "requirements.txt",
        "package.json",
        "go.mod",
    ]

    count = 0
    for root, dirs, filenames in os.walk(project_path):
        dirs[:] = [
            d
            for d in dirs
            if d
            not in [
                "node_modules",
                "__pycache__",
                ".git",
                "venv",
                ".venv",
                "dist",
                "build",
            ]
        ]

        for filename in filenames:
            if count >= max_files:
                break

            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, project_path)

            is_important = any(
                filename.endswith(p.replace("*", ""))
                or filename.startswith(p.replace("*", ""))
                for p in important_patterns
            )

            if is_important:
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if len(content) < 50000:
                        files[rel_path] = content
                        count += 1
                except Exception:
                    pass

    return files


def _load_context(path: str) -> Optional[Dict]:
    from analyzers.project_analyzer import ProjectAnalyzer

    path = os.path.abspath(path)
    if not os.path.isdir(path):
        print(f"⚠️  Invalid context path: {path}")
        return None

    analyzer = ProjectAnalyzer(path)
    info = analyzer.analyze()

    return {
        "project_info": info.to_dict(),
        "files": _load_project_files(path),
    }


def _detect_iac_type(filepath: str) -> Optional[str]:
    filename = os.path.basename(filepath).lower()

    if filename.endswith(".tf"):
        return "terraform"
    elif filename.startswith("dockerfile"):
        return "dockerfile"
    elif "docker-compose" in filename:
        return "docker_compose"
    elif filename.endswith((".yaml", ".yml")):
        try:
            with open(filepath, "r") as f:
                content = f.read()
            if "apiVersion" in content and "kind" in content:
                return "kubernetes"
            elif "hosts:" in content or "tasks:" in content:
                return "ansible"
            return "yaml"
        except:
            return "yaml"
    elif filename == "vagrantfile":
        return "vagrant"

    return None


def _print_eval_results(results: Dict):
    if "classification" in results:
        print("📊 Classification Results:")
        for name, data in results["classification"].items():
            metrics = data.get("metrics", {})
            print(f"   {name}:")
            print(f"      Accuracy: {metrics.get('accuracy', 0):.4f}")
            print(f"      F1 Score: {metrics.get('f1_score', 0):.4f}")

    if "optimization" in results:
        print("\n📊 Optimization Results:")
        for name, data in results["optimization"].items():
            metrics = data.get("metrics", {})
            print(f"   {name}:")
            print(f"      Best Fitness: {metrics.get('best_fitness', 0):.4f}")

    if "anomaly_detection" in results:
        print("\n📊 Anomaly Detection Results:")
        for name, data in results["anomaly_detection"].items():
            metrics = data.get("metrics", {})
            print(f"   {name}:")
            print(f"      AUC-ROC: {metrics.get('auc_roc', 0):.4f}")
            print(f"      F1 Score: {metrics.get('f1_score', 0):.4f}")


def main():
    parser = setup_argparse()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "analyze": cmd_analyze,
        "generate": cmd_generate,
        "validate": cmd_validate,
        "chat": cmd_chat,
        "eval": cmd_eval,
        "deploy": cmd_deploy,
        "security": cmd_security,
        "dpiac": cmd_dpiac,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
