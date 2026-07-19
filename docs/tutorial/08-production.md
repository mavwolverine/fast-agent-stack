# Part 8 - Production

> **Series:** [Tutorial index](index.md) · [Part 7](07-background-tasks.md) · **You are here:** Part 8

In Part 7 you moved PDF ingestion to a Dramatiq background worker. In Part 8 you harden the stack for production: tune rate limiting, add distributed tracing with Jaeger, and ship everything with Docker Compose.

**By the end of this part** the chat endpoint is rate-limited, every agent call produces a Jaeger trace, and `docker compose up --build` starts the entire `docqa` stack from a single command.

---

## Prerequisites

- Part 7 complete (web server, worker, and scheduler all running)
- Docker Compose available (`docker compose version`)

---

## 1. Rate limiting

Rate limiting is already wired - the `agent` preset generated `app.py` with `RateLimitLifespanHook` and `include_rate_limit: True` in `settings.py`. You only need to tune the window via `.env`:

```bash
# .env additions - 20 requests per 60-second window per IP
DOCQA_RATE_LIMIT_REQUESTS=20
DOCQA_RATE_LIMIT_PERIOD=60
```

Restart the dev server, then test it against the document list endpoint (faster than the chat endpoint since it does not call Ollama):

```bash
TOKEN="eyJhbGci..."   # paste your access_token from Part 3

for i in $(seq 1 22); do
  STATUS=$(curl -s -o /tmp/rl -w "%{http_code}" \
    http://127.0.0.1:8000/documents \
    -H "Authorization: Bearer $TOKEN")
  echo "Request $i: $STATUS"
done
```

Requests 1-20 return `200`. Request 21 returns `429 Too Many Requests`. Wait 60 seconds and the window resets.

The limiter uses a Redis Lua script that atomically increments a counter and sets its TTL in one round-trip - no race condition under concurrent load.

---

## 2. Jaeger tracing

The `agent` preset was scaffolded with `tracing: none`, so `TracingLifespanHook` is not in `app.py` yet. Add it in four steps.

### Install the extras

```bash
uv add "fast-agent-stack[tracing]" opentelemetry-instrumentation-httpx
```

The `tracing` extra brings OpenTelemetry SDK and the OTLP exporter. `opentelemetry-instrumentation-httpx` traces outgoing HTTP calls (including LLM requests to Ollama).

### Add Jaeger to your dev docker-compose.yml

Open `docker-compose.yml` in your project root (the one you copied in Part 0) and add the Jaeger service before the `volumes:` block:

```yaml
  jaeger:
    image: jaegertracing/jaeger:latest
    ports:
      - "16686:16686"   # web UI
      - "4317:4317"     # OTLP gRPC receiver
```

Start it:

```bash
docker compose up -d jaeger
```

### Enable tracing in settings

Add to `.env`:

```bash
DOCQA_TRACING_ENABLED=true
DOCQA_OTEL_EXPORTER_ENDPOINT=http://localhost:4317
```

### Wire the hooks

Open `docqa/app.py`. Add the imports at the top of the file, **before** any local imports (this is important because the httpx instrumentor must run before any module creates an HTTP client):

```python
from fast_agent_stack.observability import TracingLifespanHook
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Instrument httpx before any module creates an httpx client (e.g. OpenAI SDK)
HTTPXClientInstrumentor().instrument()
```

Then register the tracing hook after `RateLimitLifespanHook`:

```python
_stack.add_lifespan_hook(TracingLifespanHook(_settings, app=app))
```

Restart the dev server:

```bash
fas dev
```

### Verify traces

Open the chat UI, log in, and ask a question. Then open `http://localhost:16686`, select the `docqa` service from the dropdown, and click **Find Traces**. Click on a `/agents/chat` trace to expand it. You will see:

- The incoming HTTP request span (`POST /agents/chat`)
- Outgoing LLM call spans (`POST http://localhost:11434/v1/chat/completions`) with duration

The httpx instrumentation shows HTTP-level spans (URL, method, duration). For richer LLM tracing (tool calls, token counts, prompt/response content), use an agentic framework with OpenTelemetry GenAI support (such as Strands or LangChain) - their instrumentation integrates automatically with the `TracerProvider` configured above.

---

## 3. Docker Compose

The scaffold already generated `docker-compose.yml` (at the project root) because the `agent` preset has `include_docker_compose: True`. It includes five services:

| Service | Image | Purpose |
|---------|-------|---------|
| `app` | built from `Dockerfile` | web server (`fastagentstack run`) |
| `db` | `postgres:16-alpine` | PostgreSQL |
| `redis` | `valkey/valkey:8-alpine` | auth tokens + rate limiting |
| `worker` | built from `Dockerfile` | Dramatiq ingestion worker |
| `qdrant` | `qdrant/qdrant:latest` | vector store |

The `agent` preset does not include a scheduler service by default. Add it to `docker-compose.yml`:

```yaml
  scheduler:
    build: .
    command: fastagentstack scheduler docqa.tasks
    env_file:
      - .env
    depends_on:
      redis:
        condition: service_healthy
```

Note: inside the container the full command name `fastagentstack` is used instead of `fas` - shell aliases are not available in Docker `command` entries.

The default credentials in `docker-compose.yml` (`user`/`password` for Postgres) match the defaults in `settings.py`. They work out of the box for local Docker. Update both files to use real credentials before deploying to a shared environment.

Update `.env` to point at the Docker service hostnames instead of `localhost`:

```bash
DOCQA_DATABASE_URL=postgresql+asyncpg://user:password@db/docqa
DOCQA_REDIS_URL=redis://redis:6379/0
DOCQA_QDRANT_URL=http://qdrant:6333
DOCQA_OTEL_EXPORTER_ENDPOINT=http://jaeger:4317
```

Then build and start everything:

```bash
docker compose up --build
```

Open `http://localhost:8000` - the same chat UI from Part 6, now running entirely inside Docker.

---

## 4. Production checklist

Before pointing real traffic at `docqa`:

- [ ] Set `DOCQA_SECRET_KEY` to a random 32+ character string (not `"change-me-in-production"`)
- [ ] Set `DOCQA_DEBUG=false`
- [ ] Set real database credentials (not `user`/`password`)
- [ ] Tune `DOCQA_RATE_LIMIT_REQUESTS` and `DOCQA_RATE_LIMIT_PERIOD` for expected traffic
- [ ] Set `DOCQA_TRACING_ENABLED=true` with a real OTLP collector endpoint
- [ ] Qdrant data volume is already persistent in the generated `docker-compose.yml` (`qdrant_data` volume) - verify backups are in place
- [ ] Worker and scheduler running as separate containers (already in Compose)
- [ ] `fas run` vs `fas dev`: `fas dev` runs a single reloading worker bound to `127.0.0.1`. `fas run` runs multiple workers bound to `0.0.0.0` - use it in production

---

## What you built

Over eight parts you built a production-ready Document Q&A Assistant:

- **Part 0-1:** Docker services, scaffold, dev server
- **Part 2:** PostgreSQL document model with Alembic migrations
- **Part 3:** JWT authentication, protected endpoints
- **Part 4:** PDF upload, RAG ingestion pipeline, Qdrant vector store
- **Part 5:** Agentic chat endpoint with tool use and SSE streaming
- **Part 6:** Browser chat UI served from the same process
- **Part 7:** Dramatiq background worker, periodiq scheduler
- **Part 8:** Rate limiting, Jaeger tracing, Docker Compose deployment

Return to the [Tutorial index](index.md) or explore the [API reference](../api-reference.md) to go deeper on any component.
