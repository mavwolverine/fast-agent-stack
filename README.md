# fast-agent-stack

[![PyPI](https://img.shields.io/pypi/v/fast-agent-stack)](https://pypi.org/project/fast-agent-stack/)
[![Python](https://img.shields.io/pypi/pyversions/fast-agent-stack)](https://pypi.org/project/fast-agent-stack/)
[![CI](https://github.com/vkanwade/fast-agent-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/vkanwade/fast-agent-stack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Production infrastructure for AI agent applications, built on FastAPI.**

fast-agent-stack gives you auth, database, vector search, background tasks, rate limiting, observability, and storage out of the box. Bring your own agent framework (Strands, Pydantic AI, LangGraph) or use the built-in `@app.agent()` for simple cases.

---

## Quick Start

```bash
mkdir myproject && cd myproject
uv venv && source .venv/bin/activate
uv pip install fast-agent-stack

fas new myproject --preset agent
uv pip install -r pyproject.toml
fas migrate
fas dev
```

Visit `http://localhost:8000/docs` to see the interactive API.

---

## Installation

```bash
# Core only
pip install fast-agent-stack

# With extras (mix and match)
pip install "fast-agent-stack[auth-jwt,db-postgres,vector-qdrant]"

# Full AI stack
pip install "fast-agent-stack[ai-full]"
```

---

## Presets

Pick a preset and get a production-ready project in seconds:

| Preset | What you get |
|--------|-------------|
| `minimal` | FastAPI app, SQLAlchemy, health checks, CLI |
| `standard` | + JWT auth, SQLAdmin, Docker |
| `full` | + rate limiting, background tasks, email, observability |
| `agent` | + LLM backends, vector store, RAG pipeline, streaming |

```bash
fas new myproject --preset standard
```

---

## Features

### Infrastructure
- SQLAlchemy async + Alembic migrations
- Redis/Valkey: auth, rate limiting, response caching
- Background tasks (Dramatiq) + scheduler (Periodiq)
- Storage: S3, MinIO, local filesystem
- OpenTelemetry tracing (Jaeger backend)
- AWS / GCP secrets managers

### Auth
- JWT + session auth backends, pluggable via settings
- RBAC: users, groups, permissions, API keys
- Redis JTI denylist, email verification, password reset
- SQLAdmin UI (optional)

### Vector Search & RAG
- Vector stores: Qdrant, pgvector, OpenSearch, Weaviate
- Embedding backends: Bedrock, OpenAI, fastembed (local)
- RAG pipeline: chunk, embed, store / retrieve
- Document extraction: PDF, DOCX, XLSX, EML

### AI / Agents
- Built-in `@app.agent()` decorator for simple single-agent endpoints
- LLM backends: AWS Bedrock, OpenAI, Anthropic, LiteLLM proxy
- `get_llm(settings)` factory for one-line backend resolution
- Framework integration guides for [Strands Agents](docs/guides/framework-integration/strands-agents.md) and [Pydantic AI](docs/guides/framework-integration/pydantic-ai.md)

---

## Bring Your Own Agent Framework

fast-agent-stack's built-in `@app.agent()` covers simple cases (like FastAPI's `BackgroundTasks`). For serious agentic work, bring your own framework and use fast-agent-stack for the infrastructure:

```python
# myproject/ai/agents/chat.py
from strands import Agent
from strands.models.litellm import LiteLLMModel

from myproject.ai.tools.search import search_docs
from myproject.settings import get_settings

_settings = get_settings()

def build_chat_agent():
    model = LiteLLMModel(
        model_id=f"openai/{_settings.llm_model}",
        params={"api_key": _settings.llm_api_key, "api_base": _settings.llm_base_url},
    )
    return Agent(model=model, tools=[search_docs])
```

```python
# myproject/routes.py
from fastapi.responses import StreamingResponse

@router.post("/agents/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    return StreamingResponse(stream_chat(body.message), media_type="text/event-stream")
```

See the [Strands Agents guide](docs/guides/framework-integration/strands-agents.md) or [Pydantic AI guide](docs/guides/framework-integration/pydantic-ai.md) for full working examples.

---

## Extras

```toml
# Auth
fast-agent-stack[auth-jwt]         # JWT backend
fast-agent-stack[auth-session]     # Session backend

# Database drivers
fast-agent-stack[db-postgres]      # asyncpg
fast-agent-stack[db-sqlite]        # aiosqlite
fast-agent-stack[db-mysql]         # aiomysql

# LLM backends
fast-agent-stack[anthropic]        # Anthropic SDK
fast-agent-stack[openai]           # OpenAI SDK
fast-agent-stack[bedrock]          # aioboto3 (AWS Bedrock)
fast-agent-stack[litellm]          # LiteLLM proxy

# Vector stores
fast-agent-stack[vector-qdrant]
fast-agent-stack[vector-pgvector]
fast-agent-stack[vector-opensearch]
fast-agent-stack[vector-weaviate]

# Background tasks
fast-agent-stack[tasks]            # Dramatiq + Redis broker

# Observability
fast-agent-stack[tracing]          # OpenTelemetry + Jaeger

# Full AI bundle
fast-agent-stack[ai-full]
```

---

## CLI

| Command | Description |
|---------|-------------|
| `fas new <name>` | Scaffold a new project |
| `fas dev` | Dev server (127.0.0.1, auto-reload) |
| `fas run` | Production server (0.0.0.0, multi-worker) |
| `fas migrate` | Apply all migrations |
| `fas makemigrations` | Generate migration from model changes |
| `fas worker <module>` | Start Dramatiq worker |
| `fas scheduler <module>` | Start Periodiq scheduler |
| `fas createsuperuser` | Create a superuser account |
| `fas version` | Print installed version |

`fastagentstack` also works as the full-length alias.

---

## Documentation

- [Tutorial](docs/tutorial/index.md) - Build a Document Q&A app step by step
- [Framework Integration Guides](docs/guides/framework-integration/index.md) - Strands Agents, Pydantic AI
- [Getting Started](docs/getting-started.md)
- [Authentication & Authorization](docs/auth.md)
- [AI Module & Agents](docs/ai.md)
- [RAG Pipeline](docs/rag.md)
- [Storage & Extraction](docs/storage.md)
- [Background Tasks & Scheduling](docs/tasks.md)
- [Rate Limiting & Observability](docs/ratelimit.md)
- [Deployment](docs/deployment.md)
- [Custom Backends](docs/custom-backends.md)
- [Configuration Reference](docs/configuration.md)

---

## License

MIT
