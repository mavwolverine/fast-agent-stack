# Non-Functional Requirements

## Performance

- Framework overhead must not exceed **5ms per request** (excluding application logic, DB queries, and external calls)
- The `FastAgentStack()` app factory must complete startup in under **2 seconds** on standard hardware with a cold database connection
- No synchronous blocking in any async hot path (see Invariant I2)

## Compatibility

- **Python:** 3.11, 3.12, 3.13, 3.14 — all must pass the tox matrix on every release
- **FastAPI:** >=0.138.0 (`app.frontend()` static file serving; `fastapi-cli` app discovery required by ADR-019)
- **SQLAlchemy:** >=2.0 (async-native era)
- **Operating systems:** Linux, macOS; Windows is best-effort

## Modularity

- `pip install fast-agent-stack` alone must not import or require any AI, vector, storage, or task-queue dependency
- Each extras group must be independently installable without pulling in other extras
- A project using only `[api]` preset must have zero AI/vector/storage deps in its lockfile
- **ORM and migrations are not subject to the above exclusion.** `sqlalchemy[asyncio]` and `alembic` are always installed as core dependencies (ADR-025). The `db-*` extras groups contain only the async engine driver for the chosen database (e.g., `asyncpg`, `aiosqlite`); they do not re-bundle the ORM or migration tooling.

## Reliability

- Every backend family must have integration tests against a real service (not mocked)
- Database migrations must be reversible (down migrations required)
- Health check endpoints (`/health/live`, `/health/ready`) must respond within 100ms regardless of application state
- `/health/live` must return 200 unconditionally (process is alive). `/health/ready` must perform
  lightweight connectivity checks against every external service that is configured (database
  `SELECT 1`, Redis `PING`, vector store `collection_exists` or equivalent). If any check fails,
  `/health/ready` must return 503 with a body naming the failing service (see I13).
- External service clients (LLM providers, vector stores, storage backends) must support a
  configurable timeout. Each backend family must read a `*_timeout: float` setting from
  `BaseSettings` (e.g. `llm_timeout`, `vector_timeout`, `storage_timeout`, `embedding_timeout`). Default: 30 seconds.
  Requests that exceed the timeout must raise a `TimeoutError` rather than hanging indefinitely.
  **Exemption:** pure-arithmetic `count_tokens` heuristics that make no network I/O (e.g. the
  character-count estimate for Bedrock, word-count estimate for OpenAI) are exempt from this
  timeout requirement — they cannot block the event loop for a meaningful duration.

## Maintainability

- All public API must have type annotations; mypy strict must pass with zero errors
- No module in `core/` may import from another module's internals — only from its public `__init__.py` (see I12)
- Test coverage for `core/` must remain above 80%

## Security

- The development server (`fastagentstack dev`) must bind to `127.0.0.1` by default. Binding to
  `0.0.0.0` must require an explicit `--host 0.0.0.0` flag.
- The production server (`fastagentstack run`) must bind to `0.0.0.0` by default to serve all
  interfaces. Reload must be off and a `--workers` flag must be available.
- Passwords must be hashed with Argon2id via pwdlib (ADR-030); minimum parameters per I18: time_cost=3, memory_cost=65536, parallelism=4. Bcrypt fallback for legacy migration requires cost factor ≥ 12.
- JWT tokens must be signed; algorithm configurable; default HS256 (ADR-029). RS256 available via config for asymmetric deployments.
- No secrets may appear in generated files — `.env.example` only shows key names, never values
- Admin panel must require authentication; unauthenticated access to `/admin` must return 401/403
- **Token revocation must be durable across all worker processes and replicas.** In-process
  denylist storage (e.g., a plain Python `set`) is forbidden in any auth backend that exposes a
  `revoke_token()` method. Revocation state must be stored in Redis (or equivalent shared store)
  so that revocation in one worker is immediately visible to all others.
- **Required secrets must be validated at startup.** An app must not start in a configuration
  where the first authenticated request will fail due to a missing secret. Specifically:
  `secret_key` when `"jwt" in settings.auth_backends`; `admin_secret_key` when admin is
  enabled without auth. Startup validation must raise `RuntimeError` with a clear message naming
  the missing setting. See I11 and ADR-034.
- **`redis_url` must be set and connectable (≤5s timeout, per I11) when any builtin auth backend
  is present in `auth_backends`.** Startup must raise `RuntimeError` on failure. This applies
  whether the backend is `"jwt"` (requires Redis for the JTI denylist and refresh tokens) or
  `"session"` (requires Redis for session storage per ADR-032). See I11 and ADR-034.

## Developer Experience

- `fastagentstack new` must complete in under **30 seconds** including dependency resolution
- Generated projects must pass `mypy --strict` out of the box with zero errors
- Every error raised by the framework must include the corrective action (e.g., which extras to install)
