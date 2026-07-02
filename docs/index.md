# fast-agent-stack

**FastAPI framework for production AI agents.**

fast-agent-stack wires together the infrastructure you need for real AI applications — auth, database, vector search, background tasks, rate limiting, observability, and email — so you can focus on your agent logic.

## Quick Start

```bash
pip install fast-agent-stack
fastagentstack new myproject --preset agent
cd myproject
fastagentstack migrate
fastagentstack dev
```

## Presets

| Preset | What you get |
|--------|-------------|
| `minimal` | FastAPI + SQLAlchemy only. Fastest start. |
| `standard` | + JWT auth + SQLAdmin |
| `full` | + background tasks + rate limiting + tracing + email |
| `agent` | + Bedrock LLM + Qdrant + S3 + all of `full` |

## Key Design Choices

- **Database**: SQLAlchemy 2 async, Alembic migrations, multi-DB support (Postgres, MySQL, SQLite)
- **Auth**: JWT + session backends, pluggable via dotted-path (ADR-034)
- **AI**: `LLMBackend` Protocol — Bedrock, OpenAI, Anthropic, LiteLLM
- **RAG**: StorageProtocol + VectorStoreProtocol + EmbeddingProtocol
- **Tasks**: Dramatiq + Redis/Valkey
- **Observability**: OpenTelemetry + Jaeger (OTLP exporter, config-driven)
