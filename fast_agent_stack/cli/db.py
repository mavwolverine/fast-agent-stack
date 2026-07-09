import asyncio
import importlib
import importlib.util
import sys
from pathlib import Path

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
            "Error: alembic/ directory not found.\nRun this command from your project root.",
            err=True,
        )
        raise typer.Exit(1)


def _discover_database_url() -> str | None:
    """Return the project's database URL by importing its settings module."""
    sys.path.insert(0, str(Path.cwd()))
    candidates = ["settings"] + [
        f"{p.name}.settings"
        for p in Path.cwd().iterdir()
        if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_") and (p / "settings.py").exists()
    ]
    for module_name in candidates:
        try:
            mod = importlib.import_module(module_name)
            get_settings = getattr(mod, "get_settings", None)
            if callable(get_settings):
                return get_settings().database_url  # type: ignore[no-any-return]
        except Exception:
            continue
    return None


# I16: registry mapping feature keys to (migration_module, gate_packages) tuples.
# fas migrate applies AI migrations when ANY gate package is importable (any-of semantics).
FRAMEWORK_MIGRATION_MODULES: dict[str, tuple[str, list[str]]] = {
    "auth": ("fast_agent_stack.core.auth.migrations", ["pwdlib"]),
    "ai": (
        "fast_agent_stack.core.ai.migrations",
        ["anthropic", "openai", "litellm", "aioboto3"],
    ),
}


def _gate_package_available(pkg: str) -> bool:
    """Return True if *pkg* is findable without importing it."""
    try:
        return importlib.util.find_spec(pkg) is not None
    except (ValueError, AttributeError):
        # find_spec raises ValueError when sys.modules contains a non-module
        # (e.g. a MagicMock in tests). Treat as not available.
        return False


def _run_framework_migrations(database_url: str) -> None:
    """Apply framework-bundled migrations for enabled modules (I16)."""
    import importlib.resources as ilr

    for _key, (module_path, gate_packages) in FRAMEWORK_MIGRATION_MODULES.items():
        # Any-of gating: run migrations if at least one gate package is findable.
        if not any(_gate_package_available(pkg) for pkg in gate_packages):
            continue

        pkg = ilr.files(module_path)
        migrations_dir = str(pkg)
        cfg = Config()
        cfg.set_main_option("script_location", migrations_dir)
        cfg.attributes["database_url"] = database_url
        command.upgrade(cfg, "head")


@app.command()
def migrate() -> None:
    """Apply framework + user database migrations (framework first, I16)."""
    _require_alembic_dir()
    database_url = _discover_database_url()
    if database_url is not None:
        _run_framework_migrations(database_url)
    command.upgrade(_alembic_cfg(), "head")
    typer.echo("Migrations applied.")


@app.command()
def makemigrations(
    message: str | None = typer.Option(None, "-m", "--message", help="Migration message."),
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
