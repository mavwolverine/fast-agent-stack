"""CLI command: fas scheduler — start a Periodiq scheduler process (ADR-020)."""

from __future__ import annotations

import sys

import typer


def scheduler(
    module: str = typer.Argument(..., help="Dotted module path containing periodic tasks."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
) -> None:
    """Start the Periodiq scheduler for periodic background tasks."""
    try:
        from periodiq import entrypoint
    except ImportError:
        typer.echo(
            "periodiq is not installed. Run: pip install fast-agent-stack[scheduler]",
            err=True,
        )
        raise typer.Exit(1)

    sys.argv = ["periodiq", module]
    if verbose:
        sys.argv.append("--verbose")

    entrypoint()
