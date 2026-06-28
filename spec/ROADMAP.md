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
- [ ] Bedrock backend (extras-gated: `llm-bedrock`)
- [ ] OpenAI backend (extras-gated: `llm-openai`)
- [ ] Anthropic backend (extras-gated: `llm-anthropic`)
- [ ] LiteLLM proxy backend (extras-gated: `llm-litellm`)
- [ ] Each backend emits trailing `CompletionResult` sentinel in `stream()`
- [ ] Tests

## Phase 4c: Agent Lifecycle & Metering (ADR-035)
- [ ] `@app.agent()` decorator + handler registration
- [ ] Agent dispatcher: non-streaming → `complete()`, streaming → `stream_sse()` (via `inspect.isasyncgenfunction`)
- [ ] `ConversationLog` table + migration (`0001_fas_ai_*.py`)
- [ ] `token_usage_log` table + migration (ADR-035)
- [ ] `UsageService.log_usage()` real DB write (replaces 4a stub)
- [ ] Conversation persistence (`core/ai/conversation.py`)
- [ ] Tests
- [ ] `agent` preset complete

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

## Phase 7: Scaffolder Completion & Release (standard preset complete)
- [ ] Full scaffolder: all presets (`minimal`, `standard`, `full`, `agent`), all copier questions
- [ ] Docker + K8s template generation
- [ ] Documentation site
- [ ] CI/CD (GitHub Actions: lint, tox, integration, PyPI publish)
- [ ] Tests

## Phase 8: Redis SDK Migration (ADR-037)
- [ ] Replace `redis>=5` with `fastapi-redis-sdk>=0.1` across `auth-jwt`, `auth-session`, `rate-limit` extras
- [ ] Migrate `AuthLifespanHook` pool lifecycle to `FastAPIRedis(app).lifespan()` (amend I9)
- [ ] Migrate `JWTAuthBackend` and `SessionAuthBackend` constructors to `AsyncRedisDep` DI pattern
- [ ] Update rate-limit middleware to use `AsyncRedisDep`
- [ ] Update I3 import guards: `redis_fastapi` replaces `redis.asyncio` guards
- [ ] Update all affected tests
- [ ] Unlock response caching (`cache()`, `cache_evict()`, `cache_put()`) for new routes
