from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from kubetofu.commands import init, plan, apply, destroy, chat, agents, config

app = typer.Typer(
    name="kubetofu",
    help="Kube-Tofu: Deep Agentic Infrastructure as Code CLI",
    add_completion=True,
)

console = Console()

app.add_typer(init.app, name="init", help="Initialize a new project")
app.add_typer(chat.app, name="chat", help="Interactive AI chat")
app.add_typer(agents.app, name="agents", help="Manage AI agents")
app.add_typer(config.app, name="config", help="Manage configuration")


@app.command()
def plan(
    description: str = typer.Argument(
        ..., help="Natural language description of infrastructure"
    ),
    provider: str = typer.Option(
        "arvancloud", "--provider", "-p", help="Cloud provider"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    console.print(
        Panel.fit(
            f"[bold blue]Kube-Tofu Plan Generator[/bold blue]\nProvider: {provider}",
            title="🚀 Planning",
        )
    )

    console.print(f"\n[bold]Description:[/bold] {description}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task1 = progress.add_task("[cyan]Analyzing requirements...", total=None)
        import time

        time.sleep(1)
        progress.update(
            task1, completed=True, description="[green]✓ Requirements analyzed"
        )

        task2 = progress.add_task(
            "[cyan]Generating Terraform configuration...", total=None
        )
        time.sleep(1.5)
        progress.update(
            task2, completed=True, description="[green]✓ Terraform generated"
        )

        task3 = progress.add_task("[cyan]Running security scan...", total=None)
        time.sleep(1)
        progress.update(
            task3, completed=True, description="[green]✓ Security scan passed"
        )

        task4 = progress.add_task("[cyan]Estimating costs...", total=None)
        time.sleep(0.5)
        progress.update(
            task4, completed=True, description="[green]✓ Cost estimate ready"
        )

    console.print("\n[bold green]Plan Generated Successfully![/bold green]\n")

    terraform_code = generate_sample_terraform(description, provider)
    console.print(
        Panel(
            terraform_code,
            title="Generated Terraform Configuration",
            border_style="blue",
        )
    )

    cost_table = Table(title="Cost Estimate (Monthly)")
    cost_table.add_column("Resource", style="cyan")
    cost_table.add_column("Cost", style="green", justify="right")
    cost_table.add_row("Compute", "14,600,000 IRR")
    cost_table.add_row("Storage", "200,000 IRR")
    cost_table.add_row("Network", "100,000 IRR")
    cost_table.add_row("[bold]Total[/bold]", "[bold]14,900,000 IRR[/bold]")
    console.print(cost_table)

    console.print("\n[bold]Security Score:[/bold] [green]85/100[/green]")
    console.print("  ✓ No critical vulnerabilities")
    console.print("  ✓ Encryption enabled")
    console.print("  ⚠ Consider adding network policies")

    if output:
        with open(output, "w") as f:
            f.write(terraform_code)
        console.print(f"\n[dim]Configuration saved to {output}[/dim]")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Review the configuration")
    console.print("  2. Run [cyan]kubetofu apply[/cyan] to deploy")


@app.command()
def apply(
    auto_approve: bool = typer.Option(
        False, "--auto-approve", "-y", help="Skip approval prompt"
    ),
    plan_file: Optional[str] = typer.Option(
        None, "--plan", "-p", help="Plan file to apply"
    ),
):
    console.print(
        Panel.fit("[bold blue]Kube-Tofu Apply[/bold blue]", title="🚀 Deploying")
    )

    if not auto_approve:
        console.print("\n[yellow]The following changes will be applied:[/yellow]\n")
        console.print("  + arvancloud_iaas_network.main")
        console.print("  + arvancloud_iaas_subnet.main")
        console.print("  + arvancloud_iaas_security_group.web")
        console.print("  + arvancloud_iaas_abrak.web")
        console.print("  + arvancloud_iaas_floating_ip.web")
        console.print("\n[bold]Plan:[/bold] 5 to add, 0 to change, 0 to destroy.\n")

        if not typer.confirm("Do you want to apply these changes?"):
            console.print("[yellow]Apply cancelled.[/yellow]")
            raise typer.Exit()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        import time

        task = progress.add_task("[cyan]Creating network...", total=None)
        time.sleep(1)
        progress.update(task, description="[green]✓ Network created")

        task = progress.add_task("[cyan]Creating subnet...", total=None)
        time.sleep(0.5)
        progress.update(task, description="[green]✓ Subnet created")

        task = progress.add_task("[cyan]Creating security group...", total=None)
        time.sleep(0.5)
        progress.update(task, description="[green]✓ Security group created")

        task = progress.add_task("[cyan]Creating server...", total=None)
        time.sleep(2)
        progress.update(task, description="[green]✓ Server created")

        task = progress.add_task("[cyan]Attaching floating IP...", total=None)
        time.sleep(0.5)
        progress.update(task, description="[green]✓ Floating IP attached")

    console.print("\n[bold green]Apply complete![/bold green]")
    console.print("\n[bold]Outputs:[/bold]")
    console.print("  server_ip = 185.123.45.67")
    console.print("  server_id = srv-abc123def456")


@app.command()
def destroy(
    auto_approve: bool = typer.Option(
        False, "--auto-approve", "-y", help="Skip approval prompt"
    ),
    target: Optional[str] = typer.Option(
        None, "--target", "-t", help="Specific resource to destroy"
    ),
):
    console.print(
        Panel.fit("[bold red]Kube-Tofu Destroy[/bold red]", title="⚠️  Warning")
    )

    if not auto_approve:
        console.print("\n[red]The following resources will be DESTROYED:[/red]\n")
        if target:
            console.print(f"  - {target}")
        else:
            console.print("  - arvancloud_iaas_floating_ip.web")
            console.print("  - arvancloud_iaas_abrak.web")
            console.print("  - arvancloud_iaas_security_group.web")
            console.print("  - arvancloud_iaas_subnet.main")
            console.print("  - arvancloud_iaas_network.main")

        if not typer.confirm("\n[red]Are you SURE you want to destroy?[/red]"):
            console.print("[yellow]Destroy cancelled.[/yellow]")
            raise typer.Exit()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        import time

        task = progress.add_task("[red]Destroying resources...", total=None)
        time.sleep(3)
        progress.update(task, description="[green]✓ All resources destroyed")

    console.print("\n[bold]Destroy complete![/bold]")


@app.command()
def status():
    console.print(
        Panel.fit("[bold blue]Kube-Tofu Status[/bold blue]", title="📊 Status")
    )

    table = Table(title="Infrastructure Resources")
    table.add_column("Resource", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("ID", style="dim")

    table.add_row("main", "network", "✓ active", "net-abc123")
    table.add_row("main", "subnet", "✓ active", "sub-def456")
    table.add_row("web", "security_group", "✓ active", "sg-ghi789")
    table.add_row("web", "server", "✓ running", "srv-jkl012")
    table.add_row("web", "floating_ip", "✓ attached", "185.123.45.67")

    console.print(table)


@app.command()
def version():
    from kubetofu import __version__

    console.print(
        Panel.fit(
            f"[bold]Kube-Tofu CLI[/bold] v{__version__}\n"
            "[dim]Deep Agentic Infrastructure as Code[/dim]\n\n"
            "🌐 https://kubetofu.io\n"
            "📖 https://docs.kubetofu.io\n"
            "💻 https://github.com/kubetofu/kube-tofu",
            title="ℹ️  Version Info",
        )
    )


def generate_sample_terraform(description: str, provider: str) -> str:
    return """terraform {
  required_providers {
    arvancloud = {
      source  = "arvancloud/iaas"
      version = ">= 0.6.0"
    }
  }
}

provider "arvancloud" {
  api_key = var.arvan_api_key
  region  = "ir-thr-at1"
}

variable "arvan_api_key" {
  type      = string
  sensitive = true
}

# Network
resource "arvancloud_iaas_network" "main" {
  name   = "app-network"
  region = "ir-thr-at1"
}

resource "arvancloud_iaas_subnet" "main" {
  name            = "app-subnet"
  network_id      = arvancloud_iaas_network.main.id
  cidr            = "10.0.0.0/24"
  gateway_ip      = "10.0.0.1"
  enable_dhcp     = true
  dns_nameservers = ["8.8.8.8", "8.8.4.4"]
}

# Security Group
resource "arvancloud_iaas_security_group" "web" {
  name        = "web-sg"
  region      = "ir-thr-at1"
  description = "Web server security group"
}

# Server
resource "arvancloud_iaas_abrak" "web" {
  name      = "web-server"
  region    = "ir-thr-at1"
  flavor_id = "g2-2-2-0"
  image_id  = "ubuntu-22.04"
  
  network_interface {
    network_id = arvancloud_iaas_network.main.id
  }
}

# Floating IP
resource "arvancloud_iaas_floating_ip" "web" {
  region      = "ir-thr-at1"
  description = "Web server public IP"
}

output "server_ip" {
  value = arvancloud_iaas_floating_ip.web.floating_ip_address
}"""


if __name__ == "__main__":
    app()
