# Tutorial

Build a **Document Q&A Assistant** step by step - from a bare scaffold to a production-ready agentic application.

| Part | Topic | What you add |
|---|---|---|
| [Part 0 - Prerequisites](00-prerequisites.md) | Docker services, Ollama, model pulls | Local environment |
| [Part 1 - Scaffold](01-scaffold.md) | Scaffold `agent` preset, routes, dev server | Project foundation |
| [Part 2 - Database & Models](02-database-models.md) | SQLAlchemy, Alembic, CRUD routes | Document model + persistence |
| [Part 3 - Authentication](03-authentication.md) | JWT auth, users, protected endpoints | Auth system |
| [Part 4 - Ingestion Agent](04-ingestion-agent.md) | PDF upload → extract → embed → vector store | RAG data pipeline |
| [Part 5 - Chat Agent with Tools](05-chat-agent-tools.md) | `agent_loop`, tool calling, streaming | Agentic Q&A |
| [Part 6 - Chat UI](06-chat-ui.md) | Vanilla JS SSE page, `app.frontend()` | Browser interface |
| [Part 7 - Background Tasks](07-background-tasks.md) | Dramatiq workers, periodiq scheduler | Async processing |
| [Part 8 - Production](08-production.md) | Rate limiting, Jaeger tracing, Docker Compose, K8s | Deployment |

## What you're building

Each part extends the same `docqa` package. After Part 1 you have a running web server with an Ollama-backed chat agent. After Part 8 you have a deployable production application:

- PostgreSQL database with Alembic-managed migrations
- JWT authentication with RBAC permissions
- An agentic chat endpoint: the LLM decides when to search the document store and streams its response
- A RAG pipeline - upload PDFs, extract text, embed chunks, retrieve by semantic similarity, rerank results
- Background document-processing workers (Dramatiq + periodiq)
- Valkey/Redis-backed rate limiting and OpenTelemetry tracing

## How to use this tutorial

**Working through it?** Start at Part 0 and follow in order. Each part builds on the code from the previous one.

**Jumping in?** Each part is self-contained enough to start from. Check the **Prerequisites** box at the top - it tells you exactly what to have in place before you begin.

**Need depth?** The [API reference](../api-reference.md) and individual [guides](../index.md) cover every feature in detail.
