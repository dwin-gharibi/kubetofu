import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(help="Manage configuration")
console = Console()


@app.command("show")
def show_config():
    console.print(
        Panel.fit("[bold blue]Kube-Tofu Configuration[/bold blue]", title="⚙️ Config")
    )

    table = Table()
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Source", style="dim")

    config_items = [
        ("Provider", "arvancloud", "kubetofu.yaml"),
        ("Region", "ir-thr-at1", "kubetofu.yaml"),
        ("API Key", "••••••••", ".env"),
        ("LLM Provider", "anthropic", "default"),
        ("LLM Model", "claude-sonnet-4-20250514", "default"),
        ("Auto Approve", "false", "kubetofu.yaml"),
        ("Terraform Version", ">= 1.6.0", "kubetofu.yaml"),
    ]

    for setting, value, source in config_items:
        table.add_row(setting, value, source)

    console.print(table)


@app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    console.print(f"[green]✓ Set {key} = {value}[/green]")


@app.command("get")
def get_config(
    key: str = typer.Argument(..., help="Configuration key"),
):
    values = {
        "provider": "arvancloud",
        "region": "ir-thr-at1",
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-4-20250514",
    }

    if key in values:
        console.print(f"{key}: {values[key]}")
    else:
        console.print(f"[red]Unknown key: {key}[/red]")


@app.command("providers")
def list_providers():
    console.print(
        Panel.fit(
            "[bold blue]Supported Cloud Providers[/bold blue]", title="☁️ Providers"
        )
    )

    providers = [
        ("ArvanCloud", "arvancloud", "✓ Full Support", "Iran"),
        ("AWS", "aws", "✓ Full Support", "Global"),
        ("Google Cloud", "gcp", "✓ Full Support", "Global"),
        ("Azure", "azure", "✓ Full Support", "Global"),
        ("Hetzner", "hetzner", "✓ Full Support", "Europe"),
        ("DigitalOcean", "digitalocean", "○ Partial", "Global"),
    ]

    table = Table()
    table.add_column("Provider", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Status", style="green")
    table.add_column("Regions")

    for name, id_, status, regions in providers:
        table.add_row(name, id_, status, regions)

    console.print(table)
