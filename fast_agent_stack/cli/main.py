
import sys

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fast_agent_stack import __version__
from fast_agent_stack.cli.auth import createsuperuser as _createsuperuser
from fast_agent_stack.cli.db import makemigrations as _makemigrations
from fast_agent_stack.cli.db import migrate as _migrate
from fast_agent_stack.cli.db import seed as _seed
from fast_agent_stack.cli.new import new as _new
from fast_agent_stack.cli.run import dev as _dev
from fast_agent_stack.cli.run import run as _run
from fast_agent_stack.cli.scheduler_cmd import scheduler as _scheduler
from fast_agent_stack.cli.update import update as _update
from fast_agent_stack.cli.worker import worker as _worker

console = Console()

app = typer.Typer(
    name="fastagentstack",
    no_args_is_help=True,
    rich_markup_mode="rich",
    help=(
        "[bold green]FastAgentStack[/] — production-grade FastAPI framework"
        " for AI and agent applications.\n\n"
        "Run [bold]fastagentstack COMMAND --help[/] for command-specific options."
    ),
    add_completion=False,
)


def _version_panel() -> Panel:
    import fastapi

    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_row("[bold green]fastagentstack[/]", f"[cyan]{__version__}[/]")
    table.add_row("[dim]fastapi[/]", f"[dim]{fastapi.__version__}[/]")
    table.add_row("[dim]python[/]", f"[dim]{sys.version.split()[0]}[/]")
    return Panel(
        table,
        title="[bold green] version [/]",
        expand=False,
        border_style="green",
        box=box.ROUNDED,
    )


@app.callback(invoke_without_command=True)
def _callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version info and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        console.print(_version_panel())
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command(name="version")
def version_cmd() -> None:
    """Show version and environment info."""
    console.print(_version_panel())


app.command(name="dev")(_dev)
app.command(name="run")(_run)
app.command(name="new")(_new)
app.command(name="update")(_update)
app.command(name="migrate")(_migrate)
app.command(name="makemigrations")(_makemigrations)
app.command(name="seed")(_seed)
app.command(name="createsuperuser")(_createsuperuser)
app.command(name="worker")(_worker)
app.command(name="scheduler")(_scheduler)
