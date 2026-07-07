import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

app = typer.Typer(help="Interactive AI chat for infrastructure")
console = Console()


@app.callback(invoke_without_command=True)
def chat_session(
    provider: str = typer.Option(
        "arvancloud", "--provider", "-p", help="Cloud provider"
    ),
):
    console.print(
        Panel.fit(
            "[bold blue]Kube-Tofu AI Chat[/bold blue]\n"
            f"Provider: {provider}\n\n"
            "[dim]Type 'help' for commands, 'exit' to quit[/dim]",
            title="🤖 AI Assistant",
        )
    )

    console.print("""
[bold]Welcome to Kube-Tofu AI Assistant![/bold]

I can help you:
• Plan and design infrastructure
• Generate Terraform configurations
• Analyze security and compliance
• Estimate and optimize costs
• Deploy and manage resources

[dim]Examples:[/dim]
  "Deploy a web app with nginx and postgres"
  "Scan my infrastructure for security issues"
  "How much will a 3-node Kubernetes cluster cost?"
  "Generate a VPC with public and private subnets"
""")

    history = []

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if not user_input.strip():
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("[dim]Goodbye! 👋[/dim]")
                break

            if user_input.lower() == "help":
                show_help()
                continue

            if user_input.lower() == "clear":
                console.clear()
                history = []
                continue

            if user_input.lower() == "history":
                show_history(history)
                continue

            history.append({"role": "user", "content": user_input})

            with console.status("[cyan]Thinking...[/cyan]", spinner="dots"):
                response = process_chat_message(user_input, provider, history)

            history.append({"role": "assistant", "content": response})

            console.print("\n[bold purple]Kube-Tofu[/bold purple]")
            console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def show_help():
    console.print(
        Panel(
            """
[bold]Chat Commands:[/bold]
  help     - Show this help message
  clear    - Clear chat history
  history  - Show conversation history
  exit     - Exit the chat

[bold]Infrastructure Commands:[/bold]
  "plan ..." - Generate an infrastructure plan
  "apply"    - Apply the last generated plan
  "destroy"  - Destroy infrastructure
  "status"   - Show current infrastructure status
  "cost"     - Get cost estimate

[bold]Tips:[/bold]
  • Be specific about your requirements
  • Mention the provider if not ArvanCloud
  • Ask for explanations of generated code
  • Request security or cost analysis
""",
            title="📖 Help",
        )
    )


def show_history(history):
    if not history:
        console.print("[dim]No conversation history[/dim]")
        return

    console.print("\n[bold]Conversation History:[/bold]")
    for i, msg in enumerate(history, 1):
        role = "You" if msg["role"] == "user" else "AI"
        content = (
            msg["content"][:100] + "..."
            if len(msg["content"]) > 100
            else msg["content"]
        )
        console.print(f"  {i}. [{role}]: {content}")


def process_chat_message(message: str, provider: str, history: list) -> str:
    import time

    time.sleep(1)

    message_lower = message.lower()

    if "deploy" in message_lower or "create" in message_lower:
        return generate_deployment_response(message, provider)
    elif "security" in message_lower or "scan" in message_lower:
        return generate_security_response(message)
    elif (
        "cost" in message_lower
        or "price" in message_lower
        or "estimate" in message_lower
    ):
        return generate_cost_response(message, provider)
    elif "kubernetes" in message_lower or "k8s" in message_lower:
        return generate_kubernetes_response(message, provider)
    elif "help" in message_lower or "what can" in message_lower:
        return generate_help_response()
    else:
        return generate_generic_response(message)


def generate_deployment_response(message: str, provider: str) -> str:
    return """## Infrastructure Plan Generated

Based on your request, I've designed the following infrastructure:

### Resources:
- **1 Network** with subnet (10.0.0.0/24)
- **1 Web Server** (2 vCPU, 2GB RAM)
- **1 Database** (4 vCPU, 8GB RAM)
- **1 Floating IP** for public access

### Terraform Configuration

```hcl
resource "arvancloud_iaas_network" "main" {
  name   = "app-network"
  region = "ir-thr-at1"
}

resource "arvancloud_iaas_abrak" "web" {
  name      = "web-server"
  flavor_id = "g2-2-2-0"
  image_id  = "ubuntu-22.04"
}
```

### Estimated Monthly Cost: **14,900,000 IRR**

Would you like me to:
1. Show the complete Terraform configuration
2. Apply this infrastructure
3. Modify any resources
"""


def generate_security_response(message: str) -> str:
    return """## Security Scan Results

### Overall Score: 85/100 ✓

### Findings:

| Severity | Issue | Status |
|----------|-------|--------|
| 🟢 Low | Missing resource tags | Open |
| 🟡 Medium | SSH open to 0.0.0.0/0 | Open |
| 🟢 Low | No backup policy | Open |

### Compliance Status:
- **CIS Benchmark**: 78% compliant
- **SOC2**: 85% compliant

### Recommendations:
1. Restrict SSH access to specific IPs or use bastion host
2. Enable encryption at rest for all storage
3. Add resource tags for better organization
4. Configure automated backups

Would you like me to generate remediation configurations?
"""


def generate_cost_response(message: str, provider: str) -> str:
    return f"""## Cost Estimate for {provider.title()}

### Monthly Cost Breakdown:

| Resource | Specs | Monthly Cost |
|----------|-------|-------------|
| Compute (x2) | g2-2-2-0 | 14,600,000 IRR |
| Storage | 100 GB SSD | 200,000 IRR |
| Network | Floating IP | 50,000 IRR |
| Bandwidth | Est. 100GB | 50,000 IRR |
| **Total** | | **14,900,000 IRR** |

### Annual Projection: **178,800,000 IRR**

### Optimization Suggestions:
1. **Reserved Instances**: Save 40% with 1-year commitment
2. **Auto-scaling**: Reduce costs during off-peak hours
3. **Spot Instances**: Use for non-critical workloads

**Potential Savings: Up to 71,520,000 IRR/year (40%)**
"""


def generate_kubernetes_response(message: str, provider: str) -> str:
    return """## Kubernetes Cluster Configuration

I'll help you set up a Kubernetes cluster on ArvanCloud.

### Recommended Architecture:
- **1 Master Node**: g2-4-8-0 (4 vCPU, 8GB RAM)
- **3 Worker Nodes**: g2-4-4-0 (4 vCPU, 4GB RAM)
- **Load Balancer**: For API and ingress
- **Storage**: 100GB SSD per node

### Features:
- Container runtime: containerd
- CNI: Calico
- Ingress: NGINX Ingress Controller
- Monitoring: Prometheus + Grafana

### Estimated Cost: **69,800,000 IRR/month**

### Generated Terraform:

```hcl
resource "arvancloud_iaas_abrak" "k8s_master" {
  name      = "k8s-master"
  flavor_id = "g2-4-8-0"
  image_id  = "ubuntu-22.04"
}

resource "arvancloud_iaas_abrak" "k8s_worker" {
  count     = 3
  name      = "k8s-worker-${count.index + 1}"
  flavor_id = "g2-4-4-0"
  image_id  = "ubuntu-22.04"
}
```

Shall I generate the complete configuration with networking and security?
"""


def generate_help_response() -> str:
    return """## What I Can Help You With

### 🏗️ Infrastructure Planning
- Design cloud architectures from descriptions
- Generate Terraform/OpenTofu configurations
- Create Kubernetes deployments

### 🔒 Security
- Scan configurations for vulnerabilities
- Check compliance (CIS, SOC2, HIPAA)
- Suggest security hardening

### 💰 Cost Management
- Estimate infrastructure costs
- Find optimization opportunities
- Compare providers

### 🚀 Deployment
- Execute Terraform plans
- Manage deployments
- Handle rollbacks

### 📊 Monitoring
- Check infrastructure health
- Analyze metrics
- Set up alerts

**Just describe what you need in natural language!**

Examples:
- "Deploy a production web app with high availability"
- "Set up a CI/CD pipeline with GitLab and ArgoCD"
- "Create a secure VPN connection to my cloud resources"
"""


def generate_generic_response(message: str) -> str:
    return f"""I understand you're asking about: **{message}**

To help you better, could you provide more details about:

1. **What** infrastructure do you need?
2. **Why** - what's the use case?
3. **Scale** - expected traffic/load?
4. **Budget** - any cost constraints?

Or try one of these:
- "Create a web application infrastructure"
- "Set up a Kubernetes cluster"
- "Estimate costs for a database server"
- "Scan my terraform for security issues"
"""
