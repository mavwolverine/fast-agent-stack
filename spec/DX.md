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

app = FastAgentStack()

@app.agent(name="assistant", model="claude-sonnet")
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
├── alembic/
│   └── versions/
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

For `ai-full` and `api` presets, `models/`, `schemas/`, and `routes/` are generated as packages (directories with `__init__.py`) to accommodate growth. The `minimal` preset keeps them as flat files.

## CLI UX Flow

```
$ fastagentstack new myproject

? Project name: myproject
? Description: My AI-powered API

Database:
? Which database? (PostgreSQL / MySQL / SQLite / MSSQL)

AI / LLM:
? LLM provider? (Bedrock / OpenAI / Anthropic / LiteLLM proxy / None)
? Default model? (claude-sonnet / gpt-4o / ...)

Vector Store:
? Vector database? (Qdrant / pgvector / OpenSearch / Weaviate / None)

Embedding:
? Embedding provider? (Bedrock / OpenAI / Local / None)

Storage:
? File storage backend? (S3 / Local / MinIO / None)

Task Queue:
? Background task broker? (Redis/Valkey / None)
? Include scheduler? (Yes / No)

Auth:
? Include user auth? (Yes / No)
? Auth method? (JWT / Session / Both)

Admin:
? Include admin panel? (Yes / No)

Observability:
? Tracing? (Jaeger + OpenTelemetry / None)

Secrets:
? Cloud secrets backend? (None / AWS Secrets Manager / GCP Secret Manager)

Deployment:
? Include Dockerfile? (Yes / No)
? Python version? (3.11 / 3.12 / 3.13 / 3.14)
? Include docker-compose? (Yes / No)
? Include K8s manifests? (Yes / No)

✅ Created myproject
   Dev:  fastagentstack migrate && fastagentstack dev
   Prod: fastagentstack migrate && fastagentstack run
```

**CLI presentation:** Rich (via `typer[all]`) provides styled prompts, grouped sections with panels, colored output, and a summary table of selections before project generation.

## Presets

```bash
# Full AI stack with sensible defaults
fastagentstack new myproject --preset ai-full

# REST API: FastAPI + PostgreSQL + auth + admin, no AI/vector/storage
fastagentstack new myproject --preset api

# Minimal: SQLite, no auth, no admin, no Docker — fastest start
fastagentstack new myproject --preset minimal

# Custom via flags (CI-friendly, no prompts)
fastagentstack new myproject \
  --db postgres \
  --llm bedrock \
  --vector qdrant \
  --storage s3 \
  --auth jwt \
  --admin
```

## Project Update

```bash
# When template evolves, users can update their project
fastagentstack update
# Runs copier update under the hood, merges new template changes
```
