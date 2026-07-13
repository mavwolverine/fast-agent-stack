"""fas new — scaffold a new FastAgentStack project.

Presets supply defaults; every choice is still prompted interactively unless
overridden by a CLI flag.  copier always runs with defaults=True because all
data is gathered before invoking it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import typer
from copier import run_copy
from rich.console import Console

console = Console()

TEMPLATE_DIR: Path = Path(__file__).parent.parent / "template"

# ---------------------------------------------------------------------------
# Presets — these set the *default* shown at each prompt, nothing more.
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict[str, str | bool]] = {
    "minimal": {
        "db": "sqlite",
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
        "db": "postgres",
        "llm_provider": "none",
        "vector_db": "none",
        "embedding_provider": "none",
        "storage_backend": "none",
        "task_broker": "none",
        "include_scheduler": False,
        "include_auth": True,
        "auth_backends": "jwt",
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
        "db": "postgres",
        "llm_provider": "none",
        "vector_db": "none",
        "embedding_provider": "none",
        "storage_backend": "s3",
        "task_broker": "redis",
        "include_scheduler": True,
        "include_auth": True,
        "auth_backends": "jwt",
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
        "db": "postgres",
        "llm_provider": "openai",
        "vector_db": "qdrant",
        "embedding_provider": "openai",
        "storage_backend": "local",
        "task_broker": "redis",
        "include_scheduler": False,
        "include_auth": True,
        "auth_backends": "jwt",
        "include_email": False,
        "include_admin": True,
        "include_frontend": True,
        "include_rate_limit": True,
        "secrets_backend": "none",
        "tracing": "none",
        "include_dockerfile": True,
        "include_docker_compose": True,
        "include_k8s": False,
    },
}

# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

# Each choice question is: (label, value) pairs.
_DB_CHOICES: list[tuple[str, str]] = [
    ("PostgreSQL", "postgres"),
    ("MySQL", "mysql"),
    ("SQLite", "sqlite"),
]

_LLM_CHOICES: list[tuple[str, str]] = [
    ("OpenAI-compatible (works with Ollama)", "openai"),
    ("AWS Bedrock", "bedrock"),
    ("Anthropic", "anthropic"),
    ("LiteLLM Proxy", "litellm"),
    ("None", "none"),
]

_VECTOR_DB_CHOICES: list[tuple[str, str]] = [
    ("Qdrant", "qdrant"),
    ("pgvector", "pgvector"),
    ("OpenSearch", "opensearch"),
    ("Weaviate", "weaviate"),
    ("None", "none"),
]

_EMBEDDING_CHOICES: list[tuple[str, str]] = [
    ("OpenAI-compatible (works with Ollama)", "openai"),
    ("AWS Bedrock", "bedrock"),
    ("Local (fastembed)", "local"),
    ("None", "none"),
]

_STORAGE_CHOICES: list[tuple[str, str]] = [
    ("Local filesystem", "local"),
    ("S3", "s3"),
    ("MinIO", "minio"),
    ("None", "none"),
]

_TASK_BROKER_CHOICES: list[tuple[str, str]] = [
    ("Redis/Valkey", "redis"),
    ("None", "none"),
]

_AUTH_BACKEND_CHOICES: list[tuple[str, str]] = [
    ("JWT", "jwt"),
    ("Session", "session"),
    ("JWT + Session", "jwt-and-session"),
]

_TRACING_CHOICES: list[tuple[str, str]] = [
    ("Jaeger + OpenTelemetry", "jaeger"),
    ("None", "none"),
]

_SECRETS_CHOICES: list[tuple[str, str]] = [
    ("None", "none"),
    ("AWS Secrets Manager", "aws"),
    ("GCP Secret Manager", "gcp"),
]


def _prompt_choice(
    label: str,
    choices: Sequence[tuple[str, str]],
    default: str,
) -> str:
    """Show a numbered choice menu and return the selected value."""
    # Find the default index (1-based)
    default_idx = 1
    for i, (_, val) in enumerate(choices, 1):
        if val == default:
            default_idx = i
            break

    console.print(f"\n[bold]{label}[/]")
    for i, (display, _) in enumerate(choices, 1):
        marker = "*" if i == default_idx else " "
        console.print(f"  {marker} {i}) {display}")

    raw = typer.prompt("Choose", default=str(default_idx))
    try:
        idx = int(raw)
        if 1 <= idx <= len(choices):
            return choices[idx - 1][1]
    except ValueError:
        pass
    return default


def _prompt_bool(label: str, default: bool) -> bool:
    """Prompt a yes/no question."""
    suffix = "Y/n" if default else "y/N"
    raw = typer.prompt(f"\n{label} [{suffix}]", default="y" if default else "n", show_default=False)
    return raw.strip().lower() in ("y", "yes", "1", "true")


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


def new(
    project_name: str = typer.Argument(..., help="Name of the project to create."),
    preset: str | None = typer.Option(
        None,
        "--preset",
        "-p",
        help="Preset to use as defaults: minimal, standard, full, agent.",
    ),
    db: str | None = typer.Option(None, "--db", help="Database: postgres, mysql, sqlite."),
    llm: str | None = typer.Option(None, "--llm", help="LLM provider: openai, bedrock, anthropic, litellm, none."),
    vector_db: str | None = typer.Option(
        None, "--vector-db", help="Vector DB: qdrant, pgvector, opensearch, weaviate, none."
    ),
    embedding: str | None = typer.Option(
        None, "--embedding", help="Embedding provider: openai, bedrock, local, none."
    ),
    storage: str | None = typer.Option(None, "--storage", help="Storage: local, s3, minio, none."),
    task_broker: str | None = typer.Option(None, "--task-broker", help="Task broker: redis, none."),
    auth: bool | None = typer.Option(None, "--auth/--no-auth", help="Include authentication."),
    admin: bool | None = typer.Option(None, "--admin/--no-admin", help="Include SQLAdmin panel."),
    rate_limit: bool | None = typer.Option(None, "--rate-limit/--no-rate-limit", help="Include rate limiting."),
    tracing: str | None = typer.Option(None, "--tracing", help="Tracing: jaeger, none."),
    dockerfile: bool | None = typer.Option(None, "--dockerfile/--no-dockerfile", help="Include Dockerfile."),
    docker_compose: bool | None = typer.Option(
        None, "--docker-compose/--no-docker-compose", help="Include docker-compose.yml."
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Target directory (default: current dir).",
        exists=False,
    ),
    accept_defaults: bool = typer.Option(
        False,
        "--defaults",
        "-y",
        help="Accept all defaults without prompting (requires --preset).",
    ),
) -> None:
    """Create a new FastAgentStack project."""
    if preset is not None and preset not in PRESETS:
        valid = ", ".join(sorted(PRESETS))
        console.print(f"[red]Error:[/] Unknown preset [bold]{preset!r}[/]. Valid presets: {valid}")
        raise typer.Exit(code=1)

    dest = output_dir or Path.cwd()

    # If no preset given on CLI, ask interactively
    if preset is None and not accept_defaults:
        _PRESET_CHOICES: list[tuple[str, str]] = [
            ("minimal  - FastAPI + SQLAlchemy, no extras", "minimal"),
            ("standard - + JWT auth, admin, Docker", "standard"),
            ("full     - + tasks, email, rate limiting, tracing", "full"),
            ("agent    - + LLM, vector DB, RAG, chat UI", "agent"),
            ("custom   - choose everything yourself", "custom"),
        ]
        chosen = _prompt_choice("Which preset?", _PRESET_CHOICES, "custom")
        if chosen != "custom":
            preset = chosen

    # Resolve defaults from preset (or bare framework defaults)
    defaults: dict[str, str | bool] = {}
    if preset is not None:
        defaults = dict(PRESETS[preset])

    # Collect CLI overrides — these skip prompting for that question
    overrides: dict[str, str | bool] = {}
    if db is not None:
        overrides["db"] = db
    if llm is not None:
        overrides["llm_provider"] = llm
    if vector_db is not None:
        overrides["vector_db"] = vector_db
    if embedding is not None:
        overrides["embedding_provider"] = embedding
    if storage is not None:
        overrides["storage_backend"] = storage
    if task_broker is not None:
        overrides["task_broker"] = task_broker
    if auth is not None:
        overrides["include_auth"] = auth
    if admin is not None:
        overrides["include_admin"] = admin
    if rate_limit is not None:
        overrides["include_rate_limit"] = rate_limit
    if tracing is not None:
        overrides["tracing"] = tracing
    if dockerfile is not None:
        overrides["include_dockerfile"] = dockerfile
    if docker_compose is not None:
        overrides["include_docker_compose"] = docker_compose

    # Build data — prompt for anything not overridden
    data: dict[str, str | bool] = {
        "project_name": project_name,
        "description": "",
    }

    def _get_choice(key: str, label: str, choices: Sequence[tuple[str, str]], fallback: str) -> str:
        if key in overrides:
            return str(overrides[key])
        default_val = str(defaults.get(key, fallback))
        if accept_defaults:
            return default_val
        return _prompt_choice(label, choices, default_val)

    def _get_bool(key: str, label: str, fallback: bool) -> bool:
        if key in overrides:
            return bool(overrides[key])
        default_val = bool(defaults.get(key, fallback))
        if accept_defaults:
            return default_val
        return _prompt_bool(label, default_val)

    # --- Core choices ---
    data["db"] = _get_choice("db", "Which database?", _DB_CHOICES, "postgres")
    data["llm_provider"] = _get_choice("llm_provider", "LLM provider?", _LLM_CHOICES, "none")
    data["vector_db"] = _get_choice("vector_db", "Vector database?", _VECTOR_DB_CHOICES, "none")

    if data["vector_db"] != "none":
        data["embedding_provider"] = _get_choice(
            "embedding_provider", "Embedding provider?", _EMBEDDING_CHOICES, "openai"
        )
    else:
        data["embedding_provider"] = "none"

    data["storage_backend"] = _get_choice("storage_backend", "File storage?", _STORAGE_CHOICES, "none")
    data["task_broker"] = _get_choice("task_broker", "Background task broker?", _TASK_BROKER_CHOICES, "none")

    if data["task_broker"] != "none":
        data["include_scheduler"] = _get_bool("include_scheduler", "Include periodiq scheduler?", False)
    else:
        data["include_scheduler"] = False

    # --- Auth ---
    data["include_auth"] = _get_bool("include_auth", "Include authentication?", False)
    if data["include_auth"]:
        data["auth_backends"] = _get_choice(
            "auth_backends", "Auth backend?", _AUTH_BACKEND_CHOICES, str(defaults.get("auth_backends", "jwt"))
        )
        data["include_email"] = _get_bool("include_email", "Include email (password reset, verification)?", False)
    else:
        data["auth_backends"] = "jwt"
        data["include_email"] = False

    # --- Infrastructure ---
    data["include_admin"] = _get_bool("include_admin", "Include SQLAdmin panel?", False)
    data["include_frontend"] = _get_bool("include_frontend", "Include chat frontend?", False)
    data["include_rate_limit"] = _get_bool("include_rate_limit", "Include rate limiting?", False)
    data["tracing"] = _get_choice("tracing", "Tracing backend?", _TRACING_CHOICES, "none")
    data["secrets_backend"] = _get_choice("secrets_backend", "Secrets manager?", _SECRETS_CHOICES, "none")

    # --- Deployment ---
    data["include_dockerfile"] = _get_bool("include_dockerfile", "Include Dockerfile?", False)
    data["include_docker_compose"] = _get_bool("include_docker_compose", "Include docker-compose.yml?", False)
    data["include_k8s"] = _get_bool("include_k8s", "Include Kubernetes manifests?", False)

    # --- Generate ---
    console.print(f"\nCreating [bold green]{project_name}[/] …")

    run_copy(
        src_path=str(TEMPLATE_DIR),
        dst_path=str(dest),
        data=data,
        defaults=True,
        overwrite=False,
        quiet=True,
        unsafe=True,
    )

    # --- Post-create notes ---
    env_notes: list[str] = []
    prefix = project_name.upper()
    if data.get("include_admin"):
        env_notes.append(f"  [yellow]![/] Set [bold]{prefix}_ADMIN_SECRET_KEY[/] in [dim].env[/] (admin panel)")
    if data.get("include_auth"):
        env_notes.append(f"  [yellow]![/] Replace [bold]{prefix}_SECRET_KEY[/] in [dim].env[/] (auth signing)")

    env_block = ""
    if env_notes:
        env_block = "\n\n  [dim]cp .env.example .env[/]\n" + "\n".join(env_notes)

    console.print(
        f"\n[bold green]✓[/] Created [bold]{project_name}[/]{env_block}\n\n"
        f"  Dev:  [dim]fastagentstack migrate && fastagentstack dev[/]\n"
        f"  Prod: [dim]fastagentstack migrate && fastagentstack run[/]"
    )
