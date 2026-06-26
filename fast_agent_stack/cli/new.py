
from pathlib import Path

import typer
from copier import run_copy
from rich.console import Console

console = Console()

TEMPLATE_DIR: Path = Path(__file__).parent.parent / "template"

PRESETS: dict[str, dict[str, str | bool]] = {
    "minimal": {
        "llm_provider": "none",
        "vector_db": "none",
        "embedding_provider": "none",
        "storage_backend": "local",
        "task_broker": "none",
        "include_scheduler": False,
        "include_auth": False,
        "include_email": False,
        "include_admin": False,
        "include_frontend": False,
        "include_rate_limit": False,
        "secrets_backend": "none",
        "tracing": "none",
        "include_dockerfile": False,
        "include_docker_compose": False,
        "include_k8s": False,
    },
    "standard": {
        "llm_provider": "none",
        "vector_db": "none",
        "embedding_provider": "none",
        "storage_backend": "none",
        "task_broker": "none",
        "include_scheduler": False,
        "include_auth": True,
        "auth_method": "jwt",
        "include_email": False,
        "include_admin": True,
        "include_frontend": False,
        "include_rate_limit": False,
        "secrets_backend": "none",
        "tracing": "none",
        "include_dockerfile": True,
        "include_docker_compose": True,
        "include_k8s": False,
    },
    "full": {
        "llm_provider": "none",
        "vector_db": "none",
        "embedding_provider": "none",
        "storage_backend": "s3",
        "task_broker": "redis",
        "include_scheduler": True,
        "include_auth": True,
        "auth_method": "jwt",
        "include_email": True,
        "include_admin": True,
        "include_frontend": False,
        "include_rate_limit": True,
        "secrets_backend": "none",
        "tracing": "jaeger",
        "include_dockerfile": True,
        "include_docker_compose": True,
        "include_k8s": False,
    },
    "agent": {
        "llm_provider": "bedrock",
        "vector_db": "qdrant",
        "embedding_provider": "bedrock",
        "storage_backend": "s3",
        "task_broker": "redis",
        "include_scheduler": True,
        "include_auth": True,
        "auth_method": "jwt",
        "include_email": False,
        "include_admin": True,
        "include_frontend": True,
        "include_rate_limit": True,
        "secrets_backend": "none",
        "tracing": "jaeger",
        "include_dockerfile": True,
        "include_docker_compose": True,
        "include_k8s": False,
    },
}


def new(
    project_name: str = typer.Argument(..., help="Name of the project to create."),
    preset: str | None = typer.Option(
        None,
        "--preset",
        "-p",
        help="Use a named preset: [bold]minimal[/], [bold]standard[/], [bold]full[/], [bold]agent[/].",
    ),
    db: str | None = typer.Option(
        None,
        "--db",
        help="Database: postgres, mysql, sqlite, mssql.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Target directory for generated files (default: current dir).",
        exists=False,
    ),
) -> None:
    """Create a new FastAgentStack project."""
    if preset is not None and preset not in PRESETS:
        valid = ", ".join(sorted(PRESETS))
        console.print(
            f"[red]Error:[/] Unknown preset [bold]{preset!r}[/]. "
            f"Valid presets: {valid}"
        )
        raise typer.Exit(code=1)

    dest = output_dir or Path.cwd()

    if any(dest.iterdir()) and not preset:
        console.print(
            "[yellow]Warning:[/] Current directory is not empty."
        )

    data: dict[str, str | bool] = {
        "project_name": project_name,
        "description": "",
    }
    if preset is not None:
        data.update(PRESETS[preset])

    # DB is always asked — too important to silently default
    if "db" not in data:
        if db:
            data["db"] = db
        else:
            db_choices = {"1": "postgres", "2": "mysql", "3": "sqlite", "4": "mssql"}
            console.print(
                "\n[bold]Which database?[/]\n"
                "  1) PostgreSQL\n  2) MySQL\n  3) SQLite\n  4) MSSQL"
            )
            choice = typer.prompt("Choose", default="1")
            data["db"] = db_choices.get(choice, "postgres")

    console.print(f"Creating [bold green]{project_name}[/] …")

    run_copy(
        src_path=str(TEMPLATE_DIR),
        dst_path=str(dest),
        data=data,
        defaults=preset is not None,
        overwrite=False,
        quiet=True,
        unsafe=True,
    )

    console.print(
        f"\n[bold green]✓[/] Created [bold]{project_name}[/]\n"
        f"  Dev:  [dim]fastagentstack migrate && fastagentstack dev[/]\n"
        f"  Prod: [dim]fastagentstack migrate && fastagentstack run[/]"
    )
