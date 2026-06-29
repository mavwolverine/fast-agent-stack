# Invariants

These rules are non-negotiable. No implementation may violate them. Agents must treat any violation as a BLOCK.

## I1 — Full Protocol Conformance

Every pluggable backend must implement every method of its Protocol/ABC. Partial implementations are forbidden — they silently break user projects at runtime.

**Applies to:** all backends under `core/ai/` (including `core/ai/embedding/`), `core/vector/`, `core/storage/`, `core/auth/backends/`

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
- `@app.agent(name, backend)` decorator
- `BaseSettings` subclass pattern and `env_prefix` convention
- All CLI command names and their arguments
- Generated project file paths

## I7 — Template Variables and Choice Values Must Match copier.yml Exactly

Jinja2 conditionals in template files (`{% if llm_provider != "none" %}`) must use variable names that exist verbatim in `copier.yml`. No assumed or derived variable names.

Additionally, every literal value compared in a conditional (e.g., `{% if auth_backends == "jwt-and-session" %}`) must match verbatim the corresponding `choices` value in `copier.yml` — not the display label, not a derived string. A typo in a comparison value (e.g., `"jwt_and_session"` vs `"jwt-and-session"`) silently generates a broken project with no copier-level error. Agents must BLOCK any template conditional whose value does not appear verbatim in the `choices` block of the corresponding copier.yml question.

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

- `secret_key` must be set when `"jwt" in settings.auth_backends`
- `admin_secret_key` must be set when the admin panel is enabled without auth
- `redis_url` must be set and connectable (≤5s timeout) when `"jwt" in settings.auth_backends`,
  `"session" in settings.auth_backends`, or `settings.include_rate_limit is True` (token
  revocation store for JWT — see I10; session storage — see ADR-032; rate-limit counters —
  see ADR-016).

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
- Framework migrations are shipped inside the package and applied automatically — users never edit or generate them.
- When the framework adds new models in a future version, `migrate` picks them up on next run (no `makemigrations` needed for framework changes).

### Framework migration discovery (`fas migrate`)

A settings-driven registry maps enabled features to their migration modules. The gate is the **presence of the corresponding extras package** (not a settings field):

```python
FRAMEWORK_MIGRATION_MODULES = {
    "auth": ("fast_agent_stack.core.auth.migrations", "pwdlib"),  # gate: pwdlib importable
    "ai": ("fast_agent_stack.core.ai.migrations", ["anthropic", "openai", "litellm", "aioboto3"]),  # gate: any one importable
}
```

`fas migrate` attempts to import the gate package. If it succeeds, the module's migrations are applied. If the extra isn't installed, the migrations are skipped silently. This avoids needing a settings field for each feature — installation of the extra is the signal.

### User autogenerate exclusion (`fas makemigrations`)

The generated `alembic/env.py` uses an `include_object` filter that excludes framework-owned tables from autogeneration:

```python
from fast_agent_stack.database import FRAMEWORK_TABLES

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in FRAMEWORK_TABLES:
        return False
    return True
```

`FRAMEWORK_TABLES` is a `set[str]` exported by the framework listing all table names owned by core modules. This ensures `fas makemigrations` never generates migrations for framework tables.

### Naming convention

Framework migration files: `NNNN_fas_<module>_<description>.py`

```
fast_agent_stack/core/auth/migrations/
├── 0001_fas_auth_initial.py
├── 0002_fas_auth_api_keys.py
└── ...
```

- `NNNN` — sequential number within the module
- `fas_` — prefix identifying framework-owned migrations
- `<module>` — core submodule (auth, ai, etc.)
- `<description>` — short snake_case description

**Applies to:** `template/alembic/env.py.jinja`, `cli/db.py`, `core/*/migrations/`

---

## I17 — Token Revocation Must Fail Closed

When the auth backend checks whether a token has been revoked (I10), a failure to reach Redis must
**reject the request** (fail closed), not silently allow it through (fail open). If Redis is
unreachable during a revocation check, the middleware must return 503 Service Unavailable.

Rationale: fail-open means a revoked token continues to grant access during a Redis outage —
this is a security hole. Fail-closed may cause availability degradation but preserves the security
invariant that revoked tokens cannot be used.

**Applies to:** all auth backends under `core/auth/backends/` that implement token revocation checks

---

## I18 — Password Hashing Parameters Must Meet OWASP Minimums

Argon2id parameters must be at minimum: time_cost=3, memory_cost=65536 (64MB), parallelism=4.
Any implementation that uses weaker parameters (lower time_cost, lower memory_cost) is a BLOCK.

If bcrypt is used as a fallback (legacy migration), cost factor must be ≥ 12.

**Applies to:** `core/auth/password.py` or equivalent hashing module

---

## I19 — API Keys Must Be Hashed at Rest and Show-Once

API keys must never be stored in plaintext. The full key is returned exactly once (in the creation
response) and only the SHA-256 hash is persisted. Any endpoint or admin view that exposes the full
key after creation is a BLOCK.

**Applies to:** `core/auth/api_keys.py`, API key routes, admin views

---

## I20 — Auth Backend Chain: revoke_token Must Run on All Backends

When `auth_backends` contains more than one entry, the internal chain's `revoke_token()` method
must invoke `revoke_token()` on **every** backend in the list, not just the primary. Skipping
revocation on any backend means a user who authenticates via that backend remains authenticated
after logout.

**Applies to:** `core/auth/backends/factory.py` internal chain implementation

**Rationale:** See ADR-034 chain delegation rules. Logout must invalidate all authentication
paths, not just the one that was used for the current request.

---

## I21 — Token Usage Log Write Failures Must Not Abort the LLM Response

Failures in `UsageService.log_usage()` — whether due to database unavailability, connection pool
exhaustion, or any other error — must be caught, logged at `WARNING` level, and swallowed. They
must never propagate to the caller in a way that aborts, delays, or errors the ongoing LLM
response (streaming or non-streaming).

Rationale: metering is an observability concern, not a correctness concern. A user receiving an
LLM response must not experience a failure or timeout because the usage record could not be written.
Missing usage rows are recoverable (re-derivable from logs); an aborted response is not.

**Applies to:** `core/ai/streaming.py` (`stream_sse` helper), `core/ai/agents.py` (agent dispatcher),
and any other call site of `UsageService.log_usage()`
