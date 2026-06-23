# Invariants

These rules are non-negotiable. No implementation may violate them. Agents must treat any violation as a BLOCK.

## I1 — Full Protocol Conformance

Every pluggable backend must implement every method of its Protocol/ABC. Partial implementations are forbidden — they silently break user projects at runtime.

**Applies to:** all backends under `core/ai/` (including `core/ai/embedding/`), `core/vector/`, `core/storage/`

**Known gap (Phase 6):** ADR-018 allows a custom email backend via dotted path in `email_backend`
setting. Unlike other backend families, there is no `EmailProtocol` defined yet and no extras gate
for user-supplied email implementations. This must be resolved when email support is implemented.

## I2 — Async-Only I/O

No synchronous blocking calls in any async code path. All database access, HTTP calls, file I/O, and external service calls must use async APIs.

**Applies to:** all of `core/`

## I3 — Extras Gate on Every Optional Dependency

Every optional third-party import must be guarded:

```python
try:
    import qdrant_client
except ImportError:
    raise ImportError("pip install fast-agent-stack[vector-qdrant]")
```

A missing guard means `pip install fast-agent-stack` fails at import time for users who don't need that backend.

**Applies to:** all backends, any module under an `[extras]` key in `pyproject.toml`

**Scope clarification (ADR-025):** `sqlalchemy` and `alembic` are core dependencies, not optional extras. I3 does not apply to SQLAlchemy or Alembic imports. The extras gate applies to the async engine drivers in `db-*` groups (`asyncpg`, `aiosqlite`, `aiomysql`) but not to the ORM layer itself.

## I4 — Escape Hatch on Every Wrapped Component

Every component that wraps a third-party library must expose the underlying object directly. Users must never be trapped inside the abstraction.

Examples:
- `app.fastapi_app` → the raw `FastAPI` instance
- `engine` accessible from the database module
- each backend exposes the underlying client

## I5 — No New Required Dependencies Without a Decision Record

`project.dependencies` in `pyproject.toml` must not grow without a corresponding entry in `spec/DECISIONS.md`. Optional deps go in `project.optional-dependencies` only.

## I6 — Public API Stability Within Minor Versions

The following must not change between minor versions without a deprecation cycle:
- `FastAgentStack()` constructor signature
- `@app.agent(name, model)` decorator
- `BaseSettings` subclass pattern and `env_prefix` convention
- All CLI command names and their arguments
- Generated project file paths

## I7 — Template Variables Must Match copier.yml Exactly

Jinja2 conditionals in template files (`{% if llm_provider != "none" %}`) must use variable names that exist verbatim in `copier.yml`. No assumed or derived variable names.

## I8 — Schema Name Injection Guard

The `get_async_session_for_schema(schema)` dependency must validate the schema name against the
regex `^[a-zA-Z_][a-zA-Z0-9_]*$` before issuing `SET search_path`. Any input not matching must
raise `ValueError` immediately — never interpolated into SQL. This prevents SQL injection via
tenant identifiers.

**Applies to:** `core/database.py` (or equivalent session factory module)

## I9 — Lifespan Hook Registration Order

`DatabaseLifespanHook` must be registered before any hook that depends on the database. The
canonical registration order is:

1. `DatabaseLifespanHook` — initialises engine and session factory
2. `AuthLifespanHook` — connects auth backend (may use Redis, but not DB directly)
3. `RateLimitLifespanHook` — connects to Redis for rate-limit counters
4. `TracingLifespanHook` — initialises OpenTelemetry exporters
5. `AdminLifespanHook` — mounts SQLAdmin; requires the engine to already exist

Any hook that reads `db_module._engine` or calls `get_async_session()` at startup will raise
`RuntimeError` if registered before `DatabaseLifespanHook`. The generated `{{project_name}}/app.py`
template must enforce this order. Agents must BLOCK any template or code change that violates it.

**`install_app()` ordering contract:** All `install_app()` calls must complete before the lifespan
sequence begins (i.e., before `__aenter__` is called on the first hook). `AdminLifespanHook`
collects admin views from previously-installed modules — calling `install_app()` after lifespan
start results in views not appearing in the admin panel.

## I10 — Token Revocation Must Use a Shared Store

Any auth backend that exposes a `revoke_token()` method must store revocation state in a shared
external store (Redis or equivalent) so that a revocation in one worker is immediately visible to
all other workers and replicas. Storing revocation state in process-local memory (e.g., a plain
Python `set` on the backend instance) is forbidden.

**Applies to:** all backends under `core/auth/backends/` that implement `revoke_token()`

## I11 — Required Secrets Must Be Validated at Startup

An application must not start in a configuration where the first authenticated request will fail
due to a missing secret. The following are hard startup requirements:

- `secret_key` must be set when `auth_backend` is `"jwt"` or `"both"`
- `admin_secret_key` must be set when the admin panel is enabled without auth
- `redis_url` must be set and connectable (≤5s timeout) when `auth_backend` is `"jwt"` or `"both"` (token revocation store — see I10).

Failure to meet these conditions must raise `RuntimeError` with a message naming the missing
setting before the app begins serving requests. Deferring the check to request time is forbidden.

---

## I12 — No Cross-Module Internal Imports in core/

No module in `core/` may import from another module's internals — only from its public `__init__.py`. For example, `core/auth/` may import from `core.database` but never from `core.database.session` directly.

**Applies to:** all modules under `core/`

---

## I13 — Readiness Check Must Verify External Services

`/health/ready` must perform lightweight connectivity checks against every configured external service (database `SELECT 1`, Redis `PING`, vector store health check). If any check fails, it must return 503 with a body naming the failing service. An always-ok readiness check is forbidden.

**Applies to:** health check endpoint implementation

---

## I14 — SQLAlchemy and Alembic Must Remain in Core Dependencies

`sqlalchemy[asyncio]` and `alembic` must always be present in `project.dependencies` in `pyproject.toml`. They must never be moved to an optional extras group. Any PR or agent action that removes either package from `project.dependencies` or places it behind an extras gate is a BLOCK.

**Rationale:** The database layer is not a pluggable backend. SQLAlchemy is the fixed ORM (ADR-002) and Alembic is the fixed migration tool. The CLI commands `migrate` and `makemigrations` depend on Alembic and must work after a bare `pip install fast-agent-stack` with no extras. See ADR-025.

**Applies to:** `pyproject.toml` `[project] dependencies` list

---

## I15 — Database URL Must Come From Settings, Not Environment

The database engine must read `DATABASE_URL` from the `Settings` object (which pydantic-settings resolves from the project's prefixed env var, e.g., `MYPROJECT_DATABASE_URL`). Directly reading `os.environ["DATABASE_URL"]` bypasses the settings prefix convention and breaks multi-project environments.

**Applies to:** `core/database/session.py`, any module that creates an engine or session factory

---

## I16 — Framework and User Migrations Are Separate

Framework-provided models (User, ConversationLog, etc.) ship with their own migrations bundled inside the `fast_agent_stack` package. User project models have their own `alembic/versions/` directory.

- `fastagentstack makemigrations` autogenerates revisions for **user models only** — framework models are excluded from the diff.
- `fastagentstack migrate` applies **both** framework-bundled migrations and user migrations (framework first).
- The generated `alembic/env.py` must set `target_metadata` to include only the user's models for autogeneration purposes. Framework migrations are managed separately.

This mirrors Django's approach: the framework ships its own migrations (like `django.contrib.auth`), and `makemigrations` only touches user app models.

**Applies to:** `template/alembic/env.py.jinja`, `cli/db.py`

---

## I17 — Token Revocation Must Fail Closed

When the auth backend checks whether a token has been revoked (I10), a failure to reach Redis must
**reject the request** (fail closed), not silently allow it through (fail open). If Redis is
unreachable during a revocation check, the middleware must return 503 Service Unavailable.

Rationale: fail-open means a revoked token continues to grant access during a Redis outage —
this is a security hole. Fail-closed may cause availability degradation but preserves the security
invariant that revoked tokens cannot be used.

**Applies to:** all auth backends under `core/auth/backends/` that implement token revocation checks
