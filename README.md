# fast-agent-stack

[![PyPI](https://img.shields.io/pypi/v/fast-agent-stack)](https://pypi.org/project/fast-agent-stack/)
[![Python](https://img.shields.io/pypi/pyversions/fast-agent-stack)](https://pypi.org/project/fast-agent-stack/)
[![CI](https://github.com/your-org/fast-agent-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/fast-agent-stack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**FastAPI framework for production AI agents.**

fast-agent-stack wires together the infrastructure every AI application needs — auth, database, vector search, background tasks, rate limiting, observability, and email — so you ship agent logic instead of boilerplate.

---

## Quick Start

```bash
mkdir myproject && cd myproject
pip install fast-agent-stack
fastagentstack new myproject --preset agent
uv pip install -r pyproject.toml
fastagentstack migrate
fastagentstack dev
```

Visit `http://localhost:8000/docs` to see the interactive API.

---

## Installation

```bash
# Core only
pip install fast-agent-stack

# With extras (mix and match)
pip install "fast-agent-stack[anthropic,auth-jwt,db-postgres,vector-qdrant]"

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
fastagentstack new myproject --preset standard
```

---

## Features

### Auth
- JWT + session auth backends, pluggable via settings
- RBAC: users, groups, permissions, API keys
- Redis JTI denylist, email verification, password reset
- SQLAdmin UI (optional)

### AI / Agents
- `@app.agent()` decorator — registers streaming or non-streaming agent handlers
- LLM backends: AWS Bedrock, OpenAI, Anthropic, LiteLLM proxy
- Server-sent event streaming built in
- Token usage logging and `get_usage()` query API

### Vector Search & RAG
- Vector stores: Qdrant, pgvector, OpenSearch, Weaviate
- Embedding backends: Bedrock, OpenAI, fastembed (local)
- RAG pipeline: chunk → embed → store / retrieve → generate
- Document extraction: PDF, DOCX, XLSX, EML

### Infrastructure
- SQLAlchemy async + Alembic migrations
- Redis/Valkey: auth, rate limiting, response caching
- Background tasks (Dramatiq) + scheduler (Periodiq)
- Storage: S3, MinIO, local filesystem
- OpenTelemetry tracing (Jaeger backend)
- AWS / GCP secrets managers

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
| `fastagentstack new <name>` | Scaffold a new project |
| `fastagentstack dev` | Dev server (127.0.0.1, auto-reload) |
| `fastagentstack run` | Production server (0.0.0.0, multi-worker) |
| `fastagentstack migrate` | Apply all migrations |
| `fastagentstack makemigrations` | Generate migration from model changes |
| `fastagentstack worker <module>` | Start Dramatiq worker |
| `fastagentstack scheduler <module>` | Start Periodiq scheduler |
| `fastagentstack createsuperuser` | Create a superuser account |
| `fastagentstack version` | Print installed version |

Short alias: `fas` works everywhere `fastagentstack` does.

---

## Example: Add an Agent

```python
# myproject/agents.py
from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend
from fast_agent_stack.core.ai.llm import Message

_llm = AnthropicLLMBackend(model_id="claude-haiku-4-5-20251001")

def register_agents(app):
    @app.agent("chat", backend=_llm)
    async def chat(messages: list[Message], *, user_id, **kw) -> str:
        result = await _llm.complete(messages)
        return result.content

    @app.agent("stream", backend=_llm)
    async def stream(messages: list[Message], *, user_id, **kw):
        async for chunk in _llm.stream(messages):
            yield chunk
```

---

## Documentation

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
- [API Reference](docs/api-reference.md)
- [Migration & Upgrade Guide](docs/migration.md)

---

## License

MIT
