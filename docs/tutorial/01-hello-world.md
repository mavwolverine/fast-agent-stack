# Part 1 — Hello World

> **Series:** [Progressive Tutorial](index.md) · **You are here:** Part 1 · [Part 2 →](02-database-models.md)

In this seven-part series you'll build a **Document Q&A Assistant** — an API that lets users upload PDF documents and ask questions about them using a large language model. By Part 7 the app will have JWT authentication, a RAG pipeline, background workers, rate limiting, and a production-ready Docker deployment.

**In Part 1** you'll scaffold the project, add a custom route, and hit a live dev server. No database or external services required.

---

## Prerequisites

- Python 3.11 or later
- `uv` installed (`pip install uv`) — or plain `pip`

No external services needed for Part 1.

---

## 1. Install fast-agent-stack

```bash
uv pip install fast-agent-stack
```

Confirm the CLI is available:

```bash
fas --version
```

> **`fas` vs `fastagentstack`:** Both names point to the same CLI. This tutorial uses `fas` for brevity. Use whichever you prefer.

---

## 2. Scaffold the project

Create a directory for the project and scaffold a `minimal` preset using SQLite — the simplest setup that needs no running database server:

```bash
mkdir docqa && cd docqa
fas new docqa --preset minimal --db sqlite
```

You'll see the `✓ Created docqa` confirmation. The `minimal` preset skips auth, admin, Docker, and AI extras so you start with the smallest possible surface area. You'll layer those in over the next six parts.

---

## 3. Explore the structure

```
docqa/
├── main.py            # entry point — imports `app` from docqa.app
├── pyproject.toml
├── .env.example
└── docqa/             # importable Python package
    ├── __init__.py
    ├── app.py         # FastAgentStack instance + router wiring
    ├── routes.py      # your routes go here
    ├── models.py      # SQLAlchemy models (empty for now)
    ├── schemas.py     # Pydantic schemas
    └── settings.py    # Settings subclass
```

Open `docqa/settings.py`. The generated file looks like this:

```python
from fast_agent_stack.config import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCQA_")
```

The `env_prefix` scopes every environment variable your app reads: `DOCQA_DATABASE_URL`, `DOCQA_SECRET_KEY`, and so on. When you deploy multiple projects to the same environment this prevents key collisions.

---

## 4. Add a status route

Open `docqa/routes.py`. Replace its contents with the following — this keeps the generated root route and adds a `/status` endpoint that confirms the app is running and reports the framework version:

```python
from fast_agent_stack import __version__
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root() -> dict:
    return {"message": "Welcome to the Document Q&A Assistant"}


@router.get("/status")
async def status() -> dict:
    return {
        "status": "ok",
        "app": "docqa",
        "framework_version": __version__,
    }
```

The import `from fast_agent_stack import __version__` uses the framework's public API. You'll never need to reach into `fast_agent_stack.core` directly — everything you need is re-exported from the top-level package.

---

## 5. Start the dev server

Copy the example environment file and run the database migration (fast-agent-stack always sets up its internal schema tables, even with SQLite and no user models yet):

```bash
cp .env.example .env
fas migrate
fas dev
```

You should see:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

`fas dev` binds to `127.0.0.1` by default and enables auto-reload. When you save a file the server restarts automatically.

---

## 6. Call the API

In a second terminal, test all three endpoints:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/status
curl http://127.0.0.1:8000/health/live
```

Or, using Python with `httpx` (included with `fastapi[standard]`):

```python
import httpx

base = "http://127.0.0.1:8000"
print(httpx.get(f"{base}/").json())
print(httpx.get(f"{base}/status").json())
print(httpx.get(f"{base}/health/live").json())
```

The `/health/live` endpoint is always present — it returns `{"status": "ok"}` as long as the process is alive. In Part 2 you'll also see `/health/ready`, which checks that the database is reachable.

---

## What you built

- A scaffolded `fast-agent-stack` project using the `minimal` preset and SQLite
- A `Settings` subclass with `DOCQA_` env-var namespacing
- A `/status` route that returns app metadata
- A running dev server at `http://127.0.0.1:8000` with auto-reload

The `docqa` package is the foundation all later parts extend. In Part 2 you'll switch to PostgreSQL, define a SQLAlchemy model, generate your first Alembic migration, and add CRUD routes.

---

## Next steps

[Part 2 — Database & Models →](02-database-models.md)
