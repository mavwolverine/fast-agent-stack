# Vision

A pip-installable, opinionated full-stack framework that wraps FastAPI the same way FastAPI wraps Starlette. Provides conventions, glue, and batteries-included modules so AI/agent projects ship to production without weeks of boilerplate wiring.

```
FastAgentStack (auth, admin, ORM, CLI, AI services, conventions)
    └── FastAPI (routing, validation, OpenAPI, dependency injection)
            └── Starlette (ASGI, middleware, requests/responses)
                    └── Uvicorn (server)
```

## Design Principles

1. **Convention over configuration** — sensible defaults, override when needed
2. **Escape hatches everywhere** — always access underlying FastAPI app, SQLAlchemy engine, etc.
3. **Extras-based modularity** — only install what you use
4. **Async-first** — everything async by default
5. **Production-ready from day one** — observability, health checks, Docker, migrations included
6. **AI-native, not AI-only** — works great for non-AI FastAPI apps too

## Reference Implementation

Architecture extracted from: `nts-rfq-backend` — a production FastAPI + AI agent system with:
- Strands Agents (multi-agent graph/swarm)
- RAG pipeline (Qdrant, Bedrock embeddings, PDF extraction)
- Dramatiq + periodiq workers
- SQLAlchemy + Alembic (MSSQL + Postgres)
- Jaeger + OTEL observability
- Docker + K8s + Terraform deployment
- Pluggable backends for storage, vector, extraction, web search, web crawling
