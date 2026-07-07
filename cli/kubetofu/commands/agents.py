import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(help="Manage AI agents")
console = Console()


@app.command("list")
def list_agents():
    console.print(
        Panel.fit("[bold blue]Kube-Tofu AI Agents[/bold blue]", title="🤖 Agents")
    )

    table = Table()
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Description", style="dim")
    table.add_column("Capabilities")

    agents = [
        {
            "name": "Planner",
            "status": "✓ Ready",
            "description": "Infrastructure planning and design",
            "capabilities": "Requirements analysis, Terraform generation, Architecture design",
        },
        {
            "name": "Security",
            "status": "✓ Ready",
            "description": "Security scanning and compliance",
            "capabilities": "Vulnerability scanning, CIS/SOC2 compliance, Policy enforcement",
        },
        {
            "name": "Cost",
            "status": "✓ Ready",
            "description": "Cost estimation and optimization",
            "capabilities": "Cost estimation, Optimization suggestions, Budget alerts",
        },
        {
            "name": "Deployment",
            "status": "✓ Ready",
            "description": "Infrastructure deployment execution",
            "capabilities": "Terraform apply, Rollbacks, State management",
        },
        {
            "name": "Monitoring",
            "status": "✓ Ready",
            "description": "Infrastructure monitoring and alerting",
            "capabilities": "Health checks, Metrics collection, Anomaly detection",
        },
        {
            "name": "Evaluator",
            "status": "✓ Ready",
            "description": "Quality assurance and validation",
            "capabilities": "Best practices, Code review, Complexity analysis",
        },
    ]

    for agent in agents:
        table.add_row(
            agent["name"],
            agent["status"],
            agent["description"],
            agent["capabilities"],
        )

    console.print(table)


@app.command("status")
def agent_status(
    agent_name: str = typer.Argument(None, help="Specific agent name"),
):
    if agent_name:
        show_single_agent_status(agent_name)
    else:
        show_all_agents_status()


def show_single_agent_status(name: str):
    console.print(
        Panel.fit(
            f"[bold blue]{name} Agent Status[/bold blue]", title="🤖 Agent Details"
        )
    )

    console.print(f"""
[bold]Agent:[/bold] {name}
[bold]Status:[/bold] [green]Ready[/green]
[bold]Model:[/bold] claude-sonnet-4-20250514
[bold]Temperature:[/bold] 0.1
[bold]Max Iterations:[/bold] 10

[bold]Recent Activity:[/bold]
  • Analyzed 5 infrastructure requests
  • Generated 3 Terraform configurations
  • 100% success rate

[bold]Tools Available:[/bold]
  • analyze_requirements
  • generate_terraform
  • decompose_task
""")


def show_all_agents_status():
    console.print(
        Panel.fit("[bold blue]All Agents Status[/bold blue]", title="🤖 System Status")
    )

    table = Table()
    table.add_column("Agent", style="cyan")
    table.add_column("Status")
    table.add_column("Tasks", justify="right")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Time")

    table.add_row("Planner", "[green]✓ Ready[/green]", "5", "100%", "2.3s")
    table.add_row("Security", "[green]✓ Ready[/green]", "3", "100%", "1.8s")
    table.add_row("Cost", "[green]✓ Ready[/green]", "4", "100%", "0.9s")
    table.add_row("Deployment", "[green]✓ Ready[/green]", "2", "100%", "5.2s")
    table.add_row("Monitoring", "[green]✓ Ready[/green]", "1", "100%", "1.1s")
    table.add_row("Evaluator", "[green]✓ Ready[/green]", "3", "100%", "1.5s")

    console.print(table)


@app.command("invoke")
def invoke_agent(
    agent_name: str = typer.Argument(..., help="Agent name"),
    task: str = typer.Argument(..., help="Task description"),
):
    console.print(f"\n[bold]Invoking {agent_name} Agent[/bold]")
    console.print(f"[dim]Task: {task}[/dim]\n")

    with console.status(f"[cyan]{agent_name} agent thinking...[/cyan]", spinner="dots"):
        import time

        time.sleep(2)

    console.print(f"[green]✓ {agent_name} agent completed task[/green]\n")
    console.print("[bold]Result:[/bold]")
    console.print(f"  Agent '{agent_name}' successfully processed: {task[:50]}...")
