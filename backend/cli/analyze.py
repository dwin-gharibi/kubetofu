import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzers.project_analyzer import ProjectAnalyzer
from analyzers.iac_generator import IaCFromSourceGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Analyze source code and generate IaC configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze current directory
    python -m cli.analyze .
    
    # Analyze and output to specific directory
    python -m cli.analyze ./my-project --output ./my-project-iac
    
    # Generate only Dockerfile
    python -m cli.analyze ./my-project --format dockerfile
    
    # Output analysis as JSON
    python -m cli.analyze ./my-project --json
        """,
    )

    parser.add_argument("project_path", help="Path to the project directory to analyze")

    parser.add_argument(
        "-o", "--output", help="Output directory for generated IaC files"
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=[
            "all",
            "dockerfile",
            "docker-compose",
            "kubernetes",
            "helm",
            "github-actions",
        ],
        default="all",
        help="IaC format to generate (default: all)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output analysis as JSON instead of generating files",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    project_path = os.path.abspath(args.project_path)
    if not os.path.isdir(project_path):
        print(f"Error: '{project_path}' is not a valid directory")
        sys.exit(1)

    print(f"🔍 Analyzing project: {project_path}")
    print()

    try:
        analyzer = ProjectAnalyzer(project_path)
        info = analyzer.analyze()
    except Exception as e:
        print(f"Error analyzing project: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
        return

    print("📊 Analysis Results:")
    print(f"   Name: {info.name}")
    print(f"   Language: {info.language.value}")
    print(f"   Frameworks: {', '.join(f.value for f in info.frameworks)}")
    print(f"   Service Type: {info.service_type.value}")
    print(f"   Dependencies: {len(info.dependencies)}")
    print(f"   Ports: {', '.join(str(p.port) for p in info.ports)}")

    if info.databases:
        print(f"   Databases: {', '.join(d.type for d in info.databases)}")

    if info.env_vars:
        print(f"   Environment Variables: {len(info.env_vars)}")

    if args.verbose:
        print()
        print("   Key Dependencies:")
        for dep in info.dependencies[:10]:
            print(f"     - {dep.name}")

        if info.env_vars:
            print()
            print("   Environment Variables:")
            for env in info.env_vars[:10]:
                print(f"     - {env.name}")

    print()

    print("🏗️  Generating IaC configurations...")

    generator = IaCFromSourceGenerator(info)
    iac = generator.generate_all()

    if args.output:
        output_dir = os.path.abspath(args.output)
    else:
        output_dir = os.path.join(project_path, "generated-iac")

    files_to_write = {}

    if args.format == "all":
        files_to_write = {
            "Dockerfile": iac.dockerfile,
            "docker-compose.yml": iac.docker_compose,
            "k8s/deployment.yaml": iac.kubernetes_deployment,
            "k8s/service.yaml": iac.kubernetes_service,
            "k8s/configmap.yaml": iac.kubernetes_configmap,
            "helm/values.yaml": iac.helm_values,
            ".github/workflows/ci.yml": iac.github_actions,
        }
    elif args.format == "dockerfile":
        files_to_write = {"Dockerfile": iac.dockerfile}
    elif args.format == "docker-compose":
        files_to_write = {"docker-compose.yml": iac.docker_compose}
    elif args.format == "kubernetes":
        files_to_write = {
            "k8s/deployment.yaml": iac.kubernetes_deployment,
            "k8s/service.yaml": iac.kubernetes_service,
            "k8s/configmap.yaml": iac.kubernetes_configmap,
        }
    elif args.format == "helm":
        files_to_write = {"helm/values.yaml": iac.helm_values}
    elif args.format == "github-actions":
        files_to_write = {".github/workflows/ci.yml": iac.github_actions}

    os.makedirs(output_dir, exist_ok=True)

    for filename, content in files_to_write.items():
        if content:
            filepath = os.path.join(output_dir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                f.write(content)
            print(f"   ✅ {filename}")

    print()
    print(f"📁 Output directory: {output_dir}")
    print()
    print("🚀 Next steps:")
    print(f"   1. Review generated files in {output_dir}")
    print("   2. Customize environment variables and secrets")
    print("   3. Build: docker build -t {} .".format(info.name))
    print("   4. Run: docker-compose up")


if __name__ == "__main__":
    main()
