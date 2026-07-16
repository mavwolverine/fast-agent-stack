# Part 1 - Scaffold

> **Series:** [Tutorial index](index.md) · [Part 0](00-prerequisites.md) · **You are here:** Part 1 · [Part 2](02-database-models.md)

In this nine-part series you'll build a **Document Q&A Assistant**: an API that lets users upload PDF documents and ask questions about them using an LLM. By Part 8 the app will have JWT authentication, a RAG pipeline, background workers, rate limiting, and a production-ready deployment.

**In Part 1** you'll scaffold the project with the `agent` preset, explore what was generated, add a custom `/status` route, and run the dev server.

---

## Prerequisites

Complete [Part 0 - Prerequisites](00-prerequisites.md) before continuing. You need:

- Docker services running: PostgreSQL on port 5432, Valkey/Redis on 6379, Qdrant on 6333
- Ollama installed with the tutorial models pulled
- Python 3.11 or later
- `uv` installed

---

## 1. Install fast-agent-stack

Create a working directory and install the package:

```bash
mkdir docqa && cd docqa
uv venv && source .venv/bin/activate
uv pip install fast-agent-stack
```

Confirm the CLI is available:

```bash
fas --version
```

> **`fas` vs `fastagentstack`:** Both names point to the same CLI. This tutorial uses `fas` for brevity.

---

## 2. Scaffold with the `agent` preset

The `agent` preset generates a full AI-ready project: PostgreSQL database, JWT auth, Redis-backed rate limiting, a vector-store client, and an agents module wired to an LLM backend.

```bash
fas new docqa --preset agent
```

The scaffolder runs without further prompts and creates the project immediately. All choices come from the `agent` preset defaults.

Install the generated dependencies:

```bash
uv pip install -r pyproject.toml
```

---

## 3. Explore the structure

The scaffolder creates:

```
.
├── .env.example
├── alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions
├── docker-compose.yml
├── Dockerfile
├── docqa
│   ├── __init__.py
│   ├── agents.py        <- LLM agent definitions
│   ├── app.py
│   ├── models.py
│   ├── routes.py
│   ├── schemas.py
│   ├── settings.py
│   └── tasks.py         <- background task stubs (Dramatiq)
├── main.py
├── pyproject.toml
└── scripts
    ├── format.sh
    └── lint.sh
```

A few files worth noting:

- `agents.py` wires LLM backends to the framework's agent dispatcher. In Part 5 you'll extend it with `agent_loop` and tool calling.
- `tasks.py` contains background task stubs. You'll implement async document ingestion in Part 7.
- `docker-compose.yml` and `Dockerfile` are ready for Part 8 when you containerise the app.

For now, focus on the settings and routing layer.

---

## 4. Look at `settings.py`

Open `docqa/settings.py`:

```python
from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from fast_agent_stack.config import BaseSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCQA_")

    database_url: str = "postgresql+asyncpg://docqa:docqa@localhost:5432/docqa"
    redis_url: str = "redis://localhost:6379/0"
    auth_backends: list[str] = ["jwt"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Two things to notice:

- `database_url` defaults to the PostgreSQL container you started in Part 0. If you changed the credentials in `docker-compose.yml`, update this value in your `.env` file.
- `auth_backends: ["jwt"]` enables JWT authentication. You'll configure users and protected routes in Part 3.

Copy the example env file:

```bash
cp .env.example .env
```

The services from Part 0 match the defaults above, so no edits are needed for local development.

---

## 5. Add a `/status` route

Open `docqa/routes.py` and add a `/status` endpoint:

```python
from fast_agent_stack import __version__
from fastapi import APIRouter, Depends

from .settings import Settings, get_settings

router = APIRouter()


@router.get("/")
async def root(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"message": "Hello from docqa!"}


@router.get("/status")
async def status(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "debug": settings.debug,
        "framework_version": __version__,
    }
```

`Depends(get_settings)` injects the cached `Settings` instance into the route. You'll use this same pattern for database sessions and auth in later parts.

---

## 6. Run migrations and start the dev server

Apply the initial migrations, then start the server:

```bash
fas migrate
fas dev
```

You should see:

```
  -> main:app on http://127.0.0.1:8000  (development)
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

`fas dev` binds to `127.0.0.1` and enables auto-reload. Save a file and the server restarts automatically.

---

## 7. Call the API

In a second terminal, hit all three endpoints:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/status
curl http://127.0.0.1:8000/health/live
```

Or with Python:

```python
import httpx

base = "http://127.0.0.1:8000"
print(httpx.get(f"{base}/").json())
print(httpx.get(f"{base}/status").json())
print(httpx.get(f"{base}/health/live").json())
```

The `/health/live` endpoint returns `{"status": "ok"}` as long as the process is alive. In Part 2 you'll also see `/health/ready`, which checks that the database is reachable.

---

## What you built

- A scaffolded project using the `agent` preset: PostgreSQL, Redis, Qdrant, and JWT all configured
- A `settings.py` subclass with `DOCQA_` env-var namespacing and a `postgresql+asyncpg` database URL
- A generated `agents.py` wired to an LLM backend (you'll extend it in Part 5)
- A `/status` route that returns app metadata using the public `fast_agent_stack` API
- A running dev server at `http://127.0.0.1:8000` with auto-reload

---

## Next steps

[Part 2 - Database & Models](02-database-models.md)

In Part 2 you'll define the `Document` SQLAlchemy model, generate an Alembic migration, and add CRUD routes for uploading and listing documents.
