# Developer Experience (Target DX)

## Project Creation

```bash
pip install fast-agent-stack
fastagentstack new myproject
cd myproject
fastagentstack migrate
fastagentstack createsuperuser
fastagentstack run
```

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

## Generated Project Structure

```
myproject/
├── manage.py
├── settings.py
├── apps/
│   └── chat/
│       ├── routes.py
│       ├── models.py
│       ├── schemas.py
│       ├── agents.py
│       └── tasks.py
├── alembic/
│   └── versions/
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

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
? Python version? (3.11 / 3.12 / 3.13)
? Include docker-compose? (Yes / No)
? Include K8s manifests? (Yes / No)

✅ Created myproject/
   Run: cd myproject && fastagentstack migrate && fastagentstack run
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
