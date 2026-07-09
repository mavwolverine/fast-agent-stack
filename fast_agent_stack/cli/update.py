from pathlib import Path

from copier import run_update
from rich.console import Console

console = Console()


def update() -> None:
    """Update the current project from the latest FastAgentStack template."""
    dst = Path.cwd()
    answers_file = dst / ".copier-answers.yml"
    if not answers_file.exists():
        console.print(
            "[red]Error:[/] No [bold].copier-answers.yml[/] found in the current "
            "directory. Run [bold]fastagentstack update[/] from the project root."
        )
        import typer

        raise typer.Exit(code=1)

    console.print("Updating project from template …")
    run_update(
        dst_path=str(dst),
        overwrite=True,
        quiet=True,
        unsafe=True,
        defaults=False,
    )
    console.print("[bold green]✓[/] Project updated.")
