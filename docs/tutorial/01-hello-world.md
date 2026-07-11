# Part 1 - Hello World

> **Series:** [Progressive Tutorial](index.md) · **You are here:** Part 1 · [Part 2 →](02-database-models.md)

In this seven-part series you'll build a **Document Q&A Assistant** - an API that lets users upload PDF documents and ask questions about them using a large language model. By Part 7 the app will have JWT authentication, a RAG pipeline, background workers, rate limiting, and a production-ready Docker deployment.

**In Part 1** you'll scaffold the project, add a custom route, and hit a live dev server. No database or external services required.

---

## Prerequisites

- Python 3.11 or later
- `uv` installed (`pip install uv`) - or plain `pip`

No external services needed for Part 1.

---

## 1. Create the project directory

```bash
mkdir docqa && cd docqa
uv venv && source .venv/bin/activate
```

## 2. Install fast-agent-stack

```bash
uv pip install fast-agent-stack
```

Confirm the CLI is available:

```bash
fas --version
```

> **`fas` vs `fastagentstack`:** Both names point to the same CLI. This tutorial uses `fas` for brevity. Use whichever you prefer.

---

## 3. Scaffold the project

Scaffold a `minimal` preset using SQLite - the simplest setup that needs no running database server:

```bash
fas new docqa --preset minimal --db sqlite
uv pip install -r pyproject.toml
```

You'll see the `✓ Created docqa` confirmation. The `minimal` preset skips auth, admin, Docker, and AI extras so you start with the smallest possible surface area. You'll layer those in over the next six parts.

---

## 4. Explore the structure

```
docqa/
├── .env.example       # environment variable template
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── docqa/             # importable Python package
│   ├── __init__.py
│   ├── app.py         # FastAgentStack instance + router wiring
│   ├── models.py      # SQLAlchemy models (empty for now)
│   ├── routes.py      # your routes go here
│   ├── schemas.py     # Pydantic schemas
│   └── settings.py    # Settings subclass
├── main.py            # entry point - imports `app` from docqa.app
├── pyproject.toml
└── scripts/
    ├── format.sh
    └── lint.sh
```

Open `docqa/settings.py`. The generated file looks like this:

```python
from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from fast_agent_stack.config import BaseSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCQA_")
    database_url: str = "sqlite+aiosqlite:///./docqa.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

The `env_prefix` scopes every environment variable your app reads: `DOCQA_DATABASE_URL`, `DOCQA_SECRET_KEY`, and so on. When you deploy multiple projects to the same environment this prevents key collisions. The `get_settings()` function caches a single `Settings` instance for the lifetime of the process.

---

## 5. Add a status route

Open `docqa/routes.py`. The generated file already has a root route with settings injection:

```python
from fastapi import APIRouter, Depends

from .settings import Settings, get_settings

router = APIRouter()


@router.get("/")
async def root(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"message": "Hello from docqa!"}
```

Add a `/status` endpoint below the root route that reports the app name and framework version:

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

Notice how `Depends(get_settings)` injects the cached `Settings` instance into each route. This is FastAPI's dependency injection at work - you'll use the same pattern for database sessions, auth, and more in later parts. Here we read `settings.app_name` and `settings.debug` to confirm the app's configuration is working.

---

## 6. Start the dev server

Copy the example environment file and run the database migration (fast-agent-stack always sets up its internal schema tables, even with SQLite and no user models yet):

```bash
cp .env.example .env
fas migrate
fas dev
```

You should see:

```
  → main:app on http://127.0.0.1:8000  (development)
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [...]
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

`fas dev` binds to `127.0.0.1` by default and enables auto-reload. When you save a file the server restarts automatically.

---

## 7. Call the API

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

The `/health/live` endpoint is always present - it returns `{"status": "ok"}` as long as the process is alive. In Part 2 you'll also see `/health/ready`, which checks that the database is reachable.

---

## What you built

- A scaffolded `fast-agent-stack` project using the `minimal` preset and SQLite
- A `Settings` subclass with `DOCQA_` env-var namespacing
- A `/status` route that returns app metadata
- A running dev server at `http://127.0.0.1:8000` with auto-reload

The `docqa` package is the foundation all later parts extend. In Part 2 you'll define a `Document` SQLAlchemy model, generate your first Alembic migration, and add CRUD routes.

---

## Next steps

[Part 2 - Database & Models →](02-database-models.md)
