# Roadmap

## Phase 1: Hello World
- [ ] Package skeleton (pyproject.toml, `fast_agent_stack/`, py.typed)
- [ ] `FastAgentStack` class wrapping FastAPI (pass-through routing, lifespan hooks)
- [ ] Config via pydantic-settings (`BaseSettings` with env/dotenv)
- [ ] CLI entry point: `fastagentstack --help`, `fastagentstack run` (delegates to `fastapi run`)
- [ ] Scaffolder: `fastagentstack new` with `minimal` preset only
- [ ] Generated project runs: scaffold → run → GET / returns JSON
- [ ] Tests for wrapper, config, CLI, scaffolder

## Phase 2: Database
- [ ] SQLAlchemy async engine + session management
- [ ] Base model (id, created_at, updated_at)
- [ ] Alembic integration (auto-configured)
- [ ] CLI: `migrate`, `makemigrations`, `seed`
- [ ] Health check: `/health/live`, `/health/ready` (DB connectivity)
- [ ] Tests

## Phase 3: Auth & Admin
- [ ] Redis client (`redis.asyncio`) + `/health/ready` ping
- [ ] User model (hashed passwords, email, roles)
- [ ] JWT + session backends (pluggable via ADR-008)
- [ ] Access + refresh token lifecycle (ADR-015, Redis denylist)
- [ ] Routes: `/auth/token`, `/auth/refresh`, `/auth/logout`
- [ ] API key management (`/api-keys`)
- [ ] SQLAdmin integration
- [ ] CLI: `createsuperuser`
- [ ] Tests

## Phase 4: AI & Streaming
- [ ] LLM provider abstraction (Bedrock, OpenAI, Anthropic, LiteLLM)
- [ ] SSE streaming response helpers
- [ ] Conversation persistence
- [ ] Agent registration + lifecycle
- [ ] Tests

## Phase 5: Data Pipeline
- [ ] Storage backends (S3, local, MinIO)
- [ ] Vector store backends (Qdrant, pgvector, OpenSearch, Weaviate)
- [ ] Embedding backends (Bedrock, OpenAI, local)
- [ ] RAG pipeline service
- [ ] Tests

## Phase 6: Background Tasks & Hardening
- [ ] Background tasks (Dramatiq) + scheduling (periodiq)
- [ ] Rate limiting (Redis fixed-window, ADR-016)
- [ ] Observability (OpenTelemetry + Jaeger, config-driven)
- [ ] Password reset + email verification (aiosmtplib)
- [ ] Secrets manager backends (AWS, GCP)
- [ ] Tests

## Phase 7: Scaffolder Completion & Release
- [ ] Full scaffolder: all presets (`ai-full`, `api`), all copier questions
- [ ] Docker + K8s template generation
- [ ] Documentation site
- [ ] CI/CD (GitHub Actions: lint, tox, integration, PyPI publish)
- [ ] Tests
