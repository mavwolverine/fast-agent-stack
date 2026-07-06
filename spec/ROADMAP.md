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
- [x] JWT + session backends (pluggable, ADR-034)
- [x] Routes: `/auth/token`, `/auth/refresh`, `/auth/logout` (logout deletes refresh token only; JTI denylist added in 3c)
- [x] Verification route stubs: `POST /auth/send-verification`, `POST /auth/verify-email`, `POST /auth/forgot-password`, `POST /auth/reset-password` (email delivery deferred to Phase 6)
- [x] Permission-checking dependencies (`require_permission("posts.delete")`)
- [x] Tests

## Phase 3c: Redis, Token Hardening & Admin
- [x] Redis client (`redis.asyncio`) + `/health/ready` ping
- [x] Access + refresh token lifecycle (ADR-015, Redis JTI denylist)
- [x] API key management (`/api-keys`)
- [x] SQLAdmin integration (gated behind `admin` extra)
- [x] Tests

## Phase 4a: AI Type Layer (ADR-036)
- [x] `Message` + `CompletionResult` frozen dataclasses in `core/ai/llm/__init__.py`
- [x] `LLMBackend` Protocol (`model_id`, `complete`, `stream`, `count_tokens`) — `messages: list[Message]` signature
- [x] `stream_sse` helper in `core/ai/streaming.py` — SSE dispatch + CompletionResult sentinel intercept
- [x] `UsageService` stub in `core/ai/usage.py` — swallows write failures (I21)
- [x] Tests

## Phase 4b: LLM Provider Backends (ADR-021)
- [x] Bedrock backend (extras-gated: `bedrock`) — `aioboto3` converse/converse_stream, `cost=None`
- [x] OpenAI backend (extras-gated: `openai`) — `AsyncOpenAI`, `stream_options={"include_usage": True}`, `cost=None`
- [x] Anthropic backend (extras-gated: `anthropic`) — `AsyncAnthropic`, `messages.stream()` ctx manager, real `count_tokens` API
- [x] LiteLLM proxy backend (extras-gated: `litellm`) — `litellm.acompletion`, `completion_cost()`, `asyncio.to_thread` token counter
- [x] Each backend emits trailing `CompletionResult(content="")` sentinel in `stream()` (ADR-036)
- [x] Tests (36 tests: conformance, sentinel, escape hatch, extras gate per backend)

## Phase 4c: Agent Lifecycle & Metering (ADR-035)
- [x] `@app.agent()` decorator + handler registration
- [x] Agent dispatcher: non-streaming → `complete()`, streaming → `stream_sse()` (via `inspect.isasyncgenfunction`)
- [x] `ConversationLog` table + migration (`0001_fas_ai_conversation.py`)
- [x] `token_usage_log` table + migration (`0002_fas_ai_token_usage.py`, ADR-035)
- [x] `UsageService.log_usage()` real DB write (replaces 4a stub)
- [x] Conversation persistence (`core/ai/conversation.py`)
- [x] Tests (35 tests covering behavior, contract, architecture, NFR, failure modes)
- [x] `agent` preset complete (agents.py.jinja with all 4 provider branches)

## Phase 5: Data Pipeline
- [x] Storage backends (S3, local, MinIO)
- [x] Vector store backends (Qdrant, pgvector, OpenSearch, Weaviate)
- [x] Embedding backends (Bedrock, OpenAI, local)
- [x] Document extraction backends (PDF, DOCX, XLSX, EML)
- [x] RAG pipeline service
- [x] Tests

## Phase 6: Background Tasks & Hardening
- [x] Background tasks (Dramatiq) + scheduling (periodiq)
- [x] Rate limiting (Redis fixed-window, ADR-016)
- [x] Observability (OpenTelemetry + Jaeger, config-driven)
- [x] Password reset + email verification (aiosmtplib)
- [x] Secrets manager backends (AWS, GCP)
- [x] `UsageService.get_usage(user_id, period)` query API (ADR-035)
- [x] Tests

## Phase 7: Scaffolder Completion & Release (standard preset complete)
- [x] Full scaffolder: all presets (`minimal`, `standard`, `full`, `agent`), all copier questions
- [x] Docker + K8s template generation
- [x] Documentation site
- [x] CI/CD (GitHub Actions: lint, tox, integration, PyPI publish)
- [x] Tests

## Phase 8: Redis SDK Migration (ADR-037)
- [x] Replace `redis>=5` with `fastapi-redis-sdk>=0.7` across `auth-jwt`, `auth-session`, `rate-limit` extras
- [x] Migrate `AuthLifespanHook` pool lifecycle to `FastAPIRedis(app).lifespan()` (amend I9)
- [x] Migrate `JWTAuthBackend` and `SessionAuthBackend` constructors to `AsyncRedisDep` DI pattern
- [x] Update rate-limit middleware to use `AsyncRedisDep`
- [x] Update I3 import guards: `redis_fastapi` replaces `redis.asyncio` guards
- [x] Update all affected tests
- [x] Unlock response caching (`cache()`, `cache_evict()`, `cache_put()`) for new routes

## Phase 9: Documentation & Release Readiness
- [ ] README.md (PyPI landing page — install, quick start, features, badges)
- [ ] pyproject.toml: `readme = "README.md"` field
- [ ] Getting Started tutorial (install → scaffold → run → deploy)
- [ ] Authentication & authorization guide (JWT, sessions, RBAC, API keys, email verification)
- [ ] AI module guide (LLM backends, agents, streaming, token metering)
- [ ] RAG pipeline guide (embedding, vector stores, ingestion, retrieval)
- [ ] Storage & extraction guide
- [ ] Background tasks & scheduling guide (Dramatiq, Periodiq)
- [ ] Rate limiting & observability guide (Redis fixed-window, OpenTelemetry)
- [ ] Deployment guide (Docker, K8s, production checklist)
- [ ] Custom backends guide (ADR-012 dotted-path pattern)
- [ ] API reference (auto-generated from docstrings/type hints)
- [ ] Configuration reference (all settings fields, env vars, secrets backends)
- [ ] Migration & upgrade guide
- [ ] CHANGELOG.md: set 0.1.0 release date
- [ ] Integration test: scaffold each preset → build → run → smoke test
- [ ] E2E test: testcontainers (Postgres + Redis) → scaffold → migrate → hit endpoints (release gate)
- [ ] PyPI test publish (TestPyPI dry-run)
