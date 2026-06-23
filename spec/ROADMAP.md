# Roadmap

## Phase 1: Hello World
- [x] Package skeleton (pyproject.toml, `fast_agent_stack/`, py.typed)
- [x] `FastAgentStack` class wrapping FastAPI (pass-through routing, lifespan hooks, CORS, request-id, error handlers)
- [x] Config via pydantic-settings (`BaseSettings` with env/dotenv)
- [x] CLI entry point: `fastagentstack --help`, `fastagentstack dev` (reload, 127.0.0.1) and `fastagentstack run` (multi-worker, 0.0.0.0) — both call `fastapi_cli` discovery + `uvicorn.run()`
- [x] Scaffolder: `fastagentstack new` with `minimal` preset only
- [x] Generated project runs: scaffold → run → GET / returns JSON
- [x] Tests for wrapper, config, CLI, scaffolder, middleware
- [x] CLI: `version` command

## Phase 2: Database
- [ ] SQLAlchemy async engine + session management
- [ ] Base model (id, created_at, updated_at)
- [ ] Alembic integration (auto-configured)
- [ ] CLI: `migrate`, `makemigrations`, `seed`
- [ ] Health check: `/health/live`, `/health/ready` (DB connectivity)
- [ ] Tests

## Phase 3: Auth & Admin
- [ ] Redis client (`redis.asyncio`) + `/health/ready` ping
- [ ] User model (hashed passwords, email, roles, `is_verified` field)
- [ ] `auth_verification_token` table (token, user_id, type, expires_at — TTL: 24h reset, 72h verification)
- [ ] JWT + session backends (pluggable via ADR-008)
- [ ] Access + refresh token lifecycle (ADR-015, Redis denylist)
- [ ] Routes: `/auth/token`, `/auth/refresh`, `/auth/logout`
- [ ] Verification route stubs: `POST /auth/send-verification`, `POST /auth/verify-email`, `POST /auth/forgot-password`, `POST /auth/reset-password` (email delivery deferred to Phase 6)
- [ ] API key management (`/api-keys`)
- [ ] SQLAdmin integration
- [ ] CLI: `createsuperuser`
- [ ] Tests

## Phase 4: AI & Streaming
- [ ] LLM provider abstraction (Bedrock, OpenAI, Anthropic, LiteLLM)
- [ ] SSE streaming response helpers
- [ ] Conversation persistence
- [ ] Agent registration + lifecycle
- [ ] Token usage metering middleware — **NEEDS-DECISION:** schema shape, per-user vs per-org, storage backend
- [ ] Tests

## Phase 5: Data Pipeline
- [ ] Storage backends (S3, local, MinIO)
- [ ] Vector store backends (Qdrant, pgvector, OpenSearch, Weaviate)
- [ ] Embedding backends (Bedrock, OpenAI, local)
- [ ] Document extraction backends (PDF, DOCX, XLSX, EML)
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
