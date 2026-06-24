import asyncio
import importlib
import sys
from pathlib import Path
from typing import Optional

import typer
from alembic import command
from alembic.config import Config

app = typer.Typer(help="Database management commands.")


def _alembic_cfg() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    return cfg


def _require_alembic_dir() -> None:
    if not Path("alembic").is_dir():
        typer.echo(
            "Error: alembic/ directory not found.\n"
            "Run this command from your project root.",
            err=True,
        )
        raise typer.Exit(1)


@app.command()
def migrate() -> None:
    """Apply framework + user database migrations (framework first, I16)."""
    _require_alembic_dir()
    command.upgrade(_alembic_cfg(), "head")
    typer.echo("Migrations applied.")


@app.command()
def makemigrations(
    message: Optional[str] = typer.Option(
        None, "-m", "--message", help="Migration message."
    ),
) -> None:
    """Autogenerate a migration revision from user model changes (I16)."""
    _require_alembic_dir()
    command.revision(_alembic_cfg(), autogenerate=True, message=message or "auto")
    typer.echo("Migration file created.")


@app.command()
def seed() -> None:
    """Run seeds.py if present in the project root."""
    seeds_path = Path("seeds.py")
    if not seeds_path.exists():
        typer.echo("No seeds.py found — nothing to do.")
        raise typer.Exit(0)
    sys.path.insert(0, str(Path.cwd()))
    module = importlib.import_module("seeds")
    run = getattr(module, "run", None)
    if run is None:
        typer.echo("seeds.py has no run() entry point — nothing to do.")
        raise typer.Exit(0)
    if asyncio.iscoroutinefunction(run):
        asyncio.run(run())
    else:
        run()
    typer.echo("Seeds complete.")
