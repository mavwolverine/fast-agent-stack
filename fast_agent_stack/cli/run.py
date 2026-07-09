from pathlib import Path

import typer
import uvicorn
from fastapi_cli.discover import get_import_data, get_import_data_from_import_string
from rich.console import Console

console = Console()


def _resolve(app_path: str) -> str:
    if ":" in app_path:
        return get_import_data_from_import_string(app_path, from_pyproject=False).import_string  # type: ignore[call-arg]
    return get_import_data(path=Path(app_path)).import_string


def dev(
    app_path: str = typer.Argument(
        "main:app",
        help="ASGI app — import string ([italic]module:attr[/]) or file path.",
        show_default=True,
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind."),
) -> None:
    """Run a FastAgentStack app in development mode. :test_tube:"""
    import_string = _resolve(app_path)
    console.print(
        f"  [dim]→[/] [bold green]{import_string}[/] on [cyan]http://{host}:{port}[/]  [yellow](development)[/]"
    )
    uvicorn.run(app=import_string, host=host, port=port, reload=True)


def run(
    app_path: str = typer.Argument(
        "main:app",
        help="ASGI app — import string ([italic]module:attr[/]) or file path.",
        show_default=True,
    ),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind."),
    workers: int | None = typer.Option(None, "--workers", "-w", help="Number of worker processes."),
) -> None:
    """Run a FastAgentStack app in production mode. :rocket:"""
    import_string = _resolve(app_path)
    console.print(f"  [dim]→[/] [bold green]{import_string}[/] on [cyan]http://{host}:{port}[/]")
    if workers is not None:
        uvicorn.run(app=import_string, host=host, port=port, reload=False, workers=workers)
    else:
        uvicorn.run(app=import_string, host=host, port=port, reload=False)
