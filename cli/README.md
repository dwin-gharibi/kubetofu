# Kube-Tofu CLI

Deep Agentic Infrastructure as Code CLI - Manage infrastructure with AI.

## Installation

```bash
pip install kubetofu
```

Or from source:

```bash
git clone https://github.com/kubetofu/kube-tofu.git
cd kube-tofu/cli
pip install -e .
```

## Quick Start

### Initialize a Project

```bash
kubetofu init
```

This will guide you through setting up a new project with:
- Cloud provider selection (ArvanCloud, AWS, GCP, Azure)
- API key configuration
- Region selection
- Project structure creation

### Generate Infrastructure from Natural Language

```bash
kubetofu plan "Deploy a web application with nginx, PostgreSQL, and load balancer"
```

The AI agents will:
1. Analyze your requirements
2. Generate Terraform configuration
3. Run security scan
4. Provide cost estimates

### Apply Infrastructure

```bash
kubetofu apply
```

Or with auto-approve:

```bash
kubetofu apply --auto-approve
```

### Interactive AI Chat

```bash
kubetofu chat
```

Chat with the AI assistant to:
- Design infrastructure
- Get security recommendations
- Optimize costs
- Debug deployment issues

## Commands

| Command | Description |
|---------|-------------|
| `kubetofu init` | Initialize a new project |
| `kubetofu plan "..."` | Generate infrastructure plan |
| `kubetofu apply` | Apply infrastructure changes |
| `kubetofu destroy` | Destroy infrastructure |
| `kubetofu chat` | Interactive AI chat |
| `kubetofu status` | Show infrastructure status |
| `kubetofu agents list` | List available AI agents |
| `kubetofu config show` | Show configuration |

## AI Agents

Kube-Tofu uses specialized AI agents:

- **Planner Agent**: Infrastructure design and Terraform generation
- **Security Agent**: Vulnerability scanning and compliance
- **Cost Agent**: Cost estimation and optimization
- **Deployment Agent**: Execution and rollbacks
- **Monitoring Agent**: Health checks and alerts
- **Evaluator Agent**: Quality assurance

## Configuration

Configuration is stored in `kubetofu.yaml`:

```yaml
project:
  name: my-project
  version: "1.0.0"

provider:
  name: arvancloud
  region: ir-thr-at1

agents:
  planner:
    enabled: true
  security:
    enabled: true
    compliance:
      - CIS
      - SOC2
  cost:
    enabled: true
```

## Environment Variables

```bash
ARVAN_API_KEY=your-api-key
ANTHROPIC_API_KEY=your-anthropic-key  # Optional
OPENAI_API_KEY=your-openai-key        # Optional
```

## Examples

### Deploy a Kubernetes Cluster

```bash
kubetofu plan "Create a Kubernetes cluster with 1 master and 3 workers on ArvanCloud"
```

### Security Scan

```bash
kubetofu chat
> Scan my infrastructure for security vulnerabilities
```

### Cost Optimization

```bash
kubetofu chat
> How can I reduce my monthly infrastructure costs?
```

## License

Apache 2.0
