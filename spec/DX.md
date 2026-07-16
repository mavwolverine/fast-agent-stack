# Developer Experience (Target DX)

## Project Creation

```bash
mkdir myproject && cd myproject
uv venv && uv pip install fast-agent-stack
fastagentstack new myproject --preset minimal
fastagentstack dev   # development: auto-reload, 127.0.0.1
fastagentstack run   # production: multi-worker, 0.0.0.0
```

`fastagentstack new` places files in the current directory, using the provided name in `pyproject.toml`.

## Minimal App

```python
from fast_agent_stack import FastAgentStack
from fast_agent_stack.core.ai.llm import get_llm_backend

app = FastAgentStack()
backend = get_llm_backend()

@app.agent(name="assistant", backend=backend)
async def assistant(message: str, history: list):
    # your agent logic
    return response

@app.get("/hello")
async def hello():
    return {"message": "world"}
```

## Settings

Define settings by subclassing `BaseSettings` in `{project_name}/settings.py`:

```python
from pydantic_settings import SettingsConfigDict
from fast_agent_stack.config import BaseSettings

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    database_url: str
    redis_url: str
    llm_provider: str = "bedrock"
    llm_model: str = "claude-sonnet"

    # Auth backends — ordered list; first entry is the primary (issues tokens on login).
    # Built-in aliases: "jwt", "session". Dotted path for custom backends (ADR-012).
    auth_backends: list[str] = ["jwt"]          # JWT only (default)
    # auth_backends: list[str] = ["session"]    # session only
    # auth_backends: list[str] = ["jwt", "session"]  # JWT primary, session fallback
```

Access settings in route handlers via a cached FastAPI dependency:

```python
from functools import lru_cache
from fastapi import Depends
from .settings import Settings

@lru_cache
def get_settings() -> Settings:
    return Settings()

# in a route:
@router.get("/info")
async def info(settings: Settings = Depends(get_settings)) -> dict:
    return {"llm_provider": settings.llm_provider}
```

`get_settings` is defined in `settings.py` and exported from there. Override it in tests with `app.dependency_overrides[get_settings] = lambda: Settings(database_url="sqlite:///:memory:")`.

## Generated Project Structure

```
./
├── main.py            # thin entry: from {project_name}.app import app
├── pyproject.toml
├── .env.example
├── Dockerfile         # {% if include_dockerfile %}
├── docker-compose.yml # {% if include_docker_compose %}
├── frontend/          # {% if include_frontend %} — empty drop target for compiled SPA output (ADR-024); no starter content generated
├── alembic/
│   └── versions/
│       └── 0001_{project_name}_initial.py  # seed migration (ADR-048)
└── {project_name}/    # importable package
    ├── __init__.py
    ├── app.py         # app factory (FastAgentStack instance + router wiring)
    ├── routes.py
    ├── models.py
    ├── schemas.py
    ├── agents.py      # {% if llm_provider != "none" %}
    ├── tasks.py       # {% if task_broker != "none" %}
    └── settings.py
```

Additional route files are added as standard `APIRouter` modules and included in `{project_name}/app.py`.

For `agent`, `full`, and `standard` presets, `models/`, `schemas/`, and `routes/` are generated as packages (directories with `__init__.py`) to accommodate growth. The `minimal` preset keeps them as flat files.

## Database CLI (Django-style)

```bash
fastagentstack makemigrations          # autogenerate migration from user model changes
fastagentstack makemigrations -m "add user profile fields"  # with message
fastagentstack migrate                 # apply framework + user migrations
fastagentstack seed                    # run seeds.py
```

Behavior mirrors Django's `manage.py makemigrations` / `manage.py migrate`:

- `makemigrations` detects changes in the **user's models only** and generates a new Alembic revision in the project's `alembic/versions/`. Framework-provided models (User, ConversationLog, etc.) are not included — the framework ships its own migrations.
- `migrate` applies **both** framework-bundled migrations and user project migrations (framework first, then user). Like Django applying `auth` and `contenttypes` migrations alongside your app's.
- Framework migrations are shipped inside the `fast_agent_stack` package and applied automatically — users never edit or generate them.
- When the framework adds new models in a future version, `migrate` picks them up on next run (no `makemigrations` needed for framework changes).

## CLI UX Flow

```
$ fastagentstack new myproject

? Project name: myproject

Preset:
? Which preset? (minimal / standard / full / agent / custom)

Database:
? Which database? (PostgreSQL / MySQL / SQLite)

Auth:
? Include authentication? (Yes / No)
? Auth backend? (JWT / Session / JWT + Session)
? Include email (password reset, verification)? (Yes / No)

Admin:
? Include SQLAdmin panel? (Yes / No)

Rate Limiting:
? Include rate limiting? (Yes / No)

Storage:
? File storage backend? (Local / S3 / MinIO / None)

Task Queue:
? Background task broker? (Redis/Valkey / None)
? Include scheduler? (Yes / No)

AI / LLM:
? LLM provider? (OpenAI-compatible / Bedrock / Anthropic / LiteLLM proxy / None)
? Vector database? (Qdrant / pgvector / OpenSearch / Weaviate / None)
? Embedding provider? (OpenAI-compatible / Bedrock / Local / None)

UI:
? Include frontend placeholder directory? (Yes / No)

Observability:
? Tracing? (Jaeger + OpenTelemetry / None)

Deployment:
? Secrets manager? (None / AWS Secrets Manager / GCP Secret Manager)
? Include Dockerfile? (Yes / No)
? Include docker-compose? (Yes / No)
? Include K8s manifests? (Yes / No)

✅ Created myproject
   Dev:  fastagentstack migrate && fastagentstack dev
   Prod: fastagentstack migrate && fastagentstack run
```

**Sequence rationale (ADR-047):** Secure it, store it, make it smart, show it, observe it, ship it.
Conditional questions only appear when a prior answer makes them relevant (e.g., Vector DB only if
LLM != None, Auth backend only if auth enabled, Scheduler only if task broker != None).

**CLI presentation:** Rich (via `typer[all]`) provides styled prompts, numbered choice menus,
and a completion summary after project generation.

## Presets

```bash
# Full AI agent stack (OpenAI-compatible + Qdrant + local storage + auth + admin + frontend)
fastagentstack new myproject --preset agent

# Full non-AI stack (auth + admin + tasks + rate-limit + tracing)
fastagentstack new myproject --preset full

# Standard REST API (auth + admin, no AI/vector/storage/tasks)
fastagentstack new myproject --preset standard

# Minimal: no auth, no admin, no Docker — fastest start
fastagentstack new myproject --preset minimal

# Custom via flags (CI-friendly, no prompts)
fastagentstack new myproject \
  --preset agent \
  --db postgres \
  --llm openai \
  --vector-db qdrant \
  --storage local \
  --auth \
  --admin \
  -y
```

## Project Update

```bash
# When template evolves, users can update their project
fastagentstack update
# Runs copier update under the hood, merges new template changes
```
