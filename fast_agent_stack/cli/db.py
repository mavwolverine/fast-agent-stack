import asyncio
import importlib
import importlib.util
import os
import sys
from pathlib import Path

import typer
import yaml
from alembic import command
from alembic.config import Config

app = typer.Typer(help="Database management commands.")

# ADR-044: maps framework migration module → gate packages.
# A module's versions directory is added to version_locations only when at least
# one gate package is importable (any-of semantics, same as I16).
FRAMEWORK_MIGRATION_GATES: list[tuple[str, list[str]]] = [
    ("fast_agent_stack.core.auth.migrations", ["pwdlib"]),
    (
        "fast_agent_stack.core.ai.migrations",
        ["anthropic", "openai", "litellm", "aioboto3"],
    ),
]


def _gate_package_available(pkg: str) -> bool:
    """Return True if *pkg* is findable without importing it."""
    try:
        return importlib.util.find_spec(pkg) is not None
    except (ValueError, AttributeError):
        # find_spec raises ValueError when sys.modules contains a non-module (e.g. MagicMock).
        return False


def _framework_version_locations() -> list[str]:
    """Return version directories for enabled framework modules (ADR-044)."""
    locs: list[str] = []
    for module_name, gate_packages in FRAMEWORK_MIGRATION_GATES:
        if not any(_gate_package_available(pkg) for pkg in gate_packages):
            continue
        try:
            mod = importlib.import_module(module_name)
            if mod.__file__ is None:
                continue
            locs.append(str(Path(mod.__file__).parent / "versions"))
        except ImportError:
            pass
    return locs


def _alembic_cfg() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("path_separator", "os")
    # ADR-044: version_locations must be set before ScriptDirectory.from_config() runs,
    # which happens at the start of every alembic command — not inside env.py.
    locs = [str(Path("alembic") / "versions")] + _framework_version_locations()
    cfg.set_main_option("version_locations", os.pathsep.join(locs))
    return cfg


def _require_alembic_dir() -> None:
    if not Path("alembic").is_dir():
        typer.echo(
            "Error: alembic/ directory not found.\nRun this command from your project root.",
            err=True,
        )
        raise typer.Exit(1)


def _read_project_name() -> str:
    """Read project_name from .copier-answers.yml (ADR-048)."""
    answers_path = Path(".copier-answers.yml")
    if not answers_path.exists():
        typer.echo(
            "Error: .copier-answers.yml not found.\n"
            "Run this command from your project root (the directory created by 'fas new').",
            err=True,
        )
        raise typer.Exit(1)
    answers = yaml.safe_load(answers_path.read_text())
    project_name: str = answers.get("project_name", "")
    if not project_name:
        typer.echo("Error: project_name not found in .copier-answers.yml.", err=True)
        raise typer.Exit(1)
    return project_name


@app.command()
def migrate() -> None:
    """Apply framework + user database migrations (ADR-044, heads = all branches)."""
    _require_alembic_dir()
    command.upgrade(_alembic_cfg(), "heads")
    typer.echo("Migrations applied.")


@app.command()
def makemigrations(
    message: str | None = typer.Option(None, "-m", "--message", help="Migration message."),
) -> None:
    """Autogenerate a migration revision targeting the user's named branch (ADR-048, I16)."""
    _require_alembic_dir()
    project_name = _read_project_name()
    user_versions = str(Path("alembic") / "versions")
    command.revision(
        _alembic_cfg(),
        autogenerate=True,
        message=message or "auto",
        version_path=user_versions,
        head=f"{project_name}@head",
    )
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
