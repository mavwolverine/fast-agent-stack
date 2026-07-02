"""CLI command: fas scheduler — start a Periodiq scheduler process (ADR-020)."""
from __future__ import annotations

import typer


def scheduler(
    module: str = typer.Argument(..., help="Dotted module path containing periodic tasks."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
) -> None:
    """Start the Periodiq scheduler for periodic background tasks."""
    try:
        import periodiq.__main__  # noqa: F401
    except ImportError:
        typer.echo(
            "periodiq is not installed. "
            "Run: pip install fast-agent-stack[scheduler]",
            err=True,
        )
        raise typer.Exit(1)

    import subprocess
    import sys

    cmd = [sys.executable, "-m", "periodiq", module]
    if verbose:
        cmd.append("--verbose")

    raise SystemExit(subprocess.call(cmd))
