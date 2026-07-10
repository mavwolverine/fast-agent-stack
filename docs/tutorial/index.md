# Tutorial

Build a **Document Q&A Assistant** step by step — from a bare scaffold to a production-ready AI application.

| Part | Topic | What you add |
|---|---|---|
| [Part 1 — Hello World](01-hello-world.md) | Scaffold, routes, dev server | Project foundation |
| [Part 2 — Database & Models](02-database-models.md) | SQLAlchemy, Alembic, CRUD | PostgreSQL + data model |
| [Part 3 — Authentication](03-authentication.md) | JWT auth, users, protected routes | Auth system |
| [Part 4 — Build a Chat Agent](04-chat-agent.md) | LLM backend, agent decorator, SSE streaming | AI conversation API |
| [Part 5 — RAG Pipeline](05-rag-pipeline.md) | PDF upload, embed, vector search | Document retrieval |
| [Part 6 — Background Tasks](06-background-tasks.md) | Dramatiq, periodiq, worker process | Async processing |
| [Part 7 — Production](07-production.md) | Rate limiting, tracing, Docker Compose | Deployment |

## What you're building

Each part extends the same `docqa` package. After Part 1 you have a running web server. After Part 7 you have a deployable production application:

- PostgreSQL database with Alembic-managed migrations
- JWT authentication with RBAC permissions
- An LLM-powered chat agent with streaming SSE responses
- A RAG pipeline that retrieves context from uploaded PDF documents
- Background document-processing workers (Dramatiq + periodiq)
- Redis-backed rate limiting and OpenTelemetry tracing

## How to use this tutorial

**Working through it?** Start at Part 1 and follow in order. Each part builds on the code from the previous one.

**Jumping in?** Each part is self-contained enough to start from. Check the **Prerequisites** box at the top — it tells you exactly what to have in place before you begin.

**Need depth?** The [API reference](../api-reference.md) and individual [guides](../index.md) cover every feature in detail.
