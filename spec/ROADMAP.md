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
- [x] SQLAlchemy async engine + session management
- [x] Base model (id, created_at, updated_at)
- [x] Alembic integration (auto-configured)
- [x] CLI: `migrate`, `makemigrations`, `seed`
- [x] Health check: `/health/live`, `/health/ready` (DB connectivity)
- [x] Tests

## Phase 3a: User Model & Identity
- [x] User model (email, password_hash, is_active, is_verified, is_staff, is_superuser, date_joined)
- [x] Group model (name, description)
- [x] Permission model (resource, action)
- [x] Join tables: user_groups, group_permissions, user_permissions
- [x] `auth_verification_token` table (token, user_id, type, expires_at)
- [x] `api_keys` table (ADR-031 schema)
- [x] CLI: `createsuperuser`
- [x] Tests

## Phase 3b: Auth Backends & Core Routes
- [x] JWT + session backends (pluggable, ADR-008)
- [x] Routes: `/auth/token`, `/auth/refresh`, `/auth/logout` (logout deletes refresh token only; JTI denylist added in 3c)
- [x] Verification route stubs: `POST /auth/send-verification`, `POST /auth/verify-email`, `POST /auth/forgot-password`, `POST /auth/reset-password` (email delivery deferred to Phase 6)
- [x] Permission-checking dependencies (`require_permission("posts.delete")`)
- [x] Tests

## Phase 3c: Redis, Token Hardening & Admin
- [ ] Redis client (`redis.asyncio`) + `/health/ready` ping
- [ ] Access + refresh token lifecycle (ADR-015, Redis JTI denylist)
- [ ] API key management (`/api-keys`)
- [ ] SQLAdmin integration (gated behind `admin` extra)
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
- [ ] Full scaffolder: all presets (`minimal`, `standard`, `full`, `agent`), all copier questions
- [ ] Docker + K8s template generation
- [ ] Documentation site
- [ ] CI/CD (GitHub Actions: lint, tox, integration, PyPI publish)
- [ ] Tests
