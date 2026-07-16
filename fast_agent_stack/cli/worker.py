"""CLI command: fas worker — start a Dramatiq worker process (ADR-005, ADR-020)."""

from __future__ import annotations

import sys

import typer


def worker(
    module: str = typer.Argument(..., help="Dotted module path containing actor definitions."),
    processes: int = typer.Option(1, "--processes", "-p", help="Number of worker processes."),
    threads: int = typer.Option(8, "--threads", "-t", help="Threads per process."),
    broker_url: str | None = typer.Option(
        None,
        "--broker-url",
        envvar="TASKS_BROKER_URL",
        help="Redis broker URL (overrides settings).",
    ),
) -> None:
    """Start a Dramatiq worker for background task processing."""
    try:
        from dramatiq.cli import main as dramatiq_main
    except ImportError:
        typer.echo(
            "dramatiq is not installed. Run: pip install fast-agent-stack[tasks]",
            err=True,
        )
        raise typer.Exit(1)

    if broker_url:
        import os

        os.environ["TASKS_BROKER_URL"] = broker_url

    sys.argv = [
        "dramatiq",
        module,
        "--processes",
        str(processes),
        "--threads",
        str(threads),
    ]

    dramatiq_main()
