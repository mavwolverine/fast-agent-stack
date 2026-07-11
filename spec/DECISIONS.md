# Architecture Decision Records

Each decision is binding. Proposing an alternative requires adding a new ADR superseding the relevant one — not silently ignoring it.

---

## ADR-001 — Package Naming: `fast-agent-stack` / `fast_agent_stack` / `fastagentstack`

**Context:** The project has three naming surfaces that each follow different conventions: the PyPI distribution name, the Python import name, and the CLI command. `DX.md` was inconsistent, using both `fastagentstack` and `fast_agent_stack` as import names. Two conventions exist in the ecosystem: FastAPI-adjacent projects collapse multi-word names (`fastapi`, `faststream`, `fastmcp`); the broader Python ecosystem maps hyphens to underscores (`pydantic_settings`, `typing_extensions`, `langchain_core`). PEP 8 explicitly recommends underscores for multi-word package names.

**Decision:**
- **PyPI distribution name:** `fast-agent-stack` (hyphens — PyPI standard)
- **Python import name:** `fast_agent_stack` (underscores — PEP 8; consistent with `pydantic_settings` and the broader ecosystem)
- **CLI entry point:** `fastagentstack` (collapsed — conventional for CLI tools in this ecosystem; mirrors `fastagentstack new`, `fastagentstack run`, etc.)

```python
# install
pip install fast-agent-stack

# import
from fast_agent_stack import FastAgentStack
from fast_agent_stack.config import BaseSettings

# CLI
fastagentstack new myproject
```

**Consequences:**
- Import name follows PEP 8 and matches user expectations coming from the broader Python ecosystem
- CLI name follows FastAPI-ecosystem conventions and is short enough to type repeatedly
- `DX.md` must use `fast_agent_stack` exclusively for all import examples
- The package directory is `fast_agent_stack/` (not `fastagentstack/`) — update `spec/ARCHITECTURE.md` package structure accordingly
- Rules out `fastagentstack` as the import name; rules out `fast_agent_stack` as the CLI command

---

## ADR-002 — ORM: SQLAlchemy Async

**Context:** Python ORMs range from Django ORM to SQLAlchemy to Tortoise. The framework targets production async FastAPI apps, so the ORM must be natively async and support Alembic migrations.

**Decision:** SQLAlchemy async (`sqlalchemy[asyncio]`) with Alembic.

**Consequences:**
- Most mature Python ORM; best ecosystem and community support
- Alembic is the de-facto migration tool for SQLAlchemy — no competing choice needed
- Rules out Django ORM, Tortoise ORM, SQLModel as the primary ORM layer
- SQLModel may be used for Pydantic-SQLAlchemy schema bridging in user code but is not a framework dependency

---

## ADR-003 — Validation: Pydantic v2

**Context:** FastAPI already depends on Pydantic. The framework needs schema validation and settings management.

**Decision:** Pydantic v2 throughout. pydantic-settings for `BaseSettings`.

**Consequences:**
- Zero additional dependency — already in the FastAPI dep tree
- Rust-backed core; best-in-class validation performance
- Rules out attrs, marshmallow, cerberus as framework-level validators
- Users on Pydantic v1 must upgrade — v1 compatibility shims are not supported

---

## ADR-004 — CLI: Typer

**Context:** The framework needs a `manage.py`-equivalent CLI with async command support and a plugin system for user-defined commands.

**Decision:** Typer (built on Click).

**Consequences:**
- Native async support via `asyncio.run()` wrappers
- Click compatibility means the ecosystem of Click extensions is available
- Rules out argparse, Click directly, and Fire
- Plugin commands are registered as Typer sub-apps

---

## ADR-005 — Task Queue: Dramatiq + Redis/Valkey

**Context:** Background task queues in Python are dominated by Celery. The framework needs a simpler, more maintainable alternative.

**Decision:** Dramatiq with Redis/Valkey as the broker.

**Consequences:**
- Simpler API than Celery; less operational complexity
- Redis/Valkey is already the session/cache dependency — no additional broker service required
- Rules out Celery, RQ, Huey, and ARQ as the built-in task queue
- Users who require Celery may wire it themselves; the framework will not provide Celery templates

---

## ADR-006 — Cache & Sessions: Valkey/Redis

**Context:** Session storage, task broker, and rate limiting all need a fast in-memory store.

**Decision:** Valkey (Redis-compatible) as the single in-memory backend. Redis is acceptable where Valkey is not yet available.

**Consequences:**
- One service covers sessions, task brokering, and rate limiting
- Rules out Memcached as a session backend
- docker-compose template includes a single `redis` service; Valkey image is preferred

---

## ADR-007 — Admin: SQLAdmin

**Context:** The framework needs a web admin panel that integrates with FastAPI and SQLAlchemy without requiring a separate Django-style admin framework.

**Decision:** SQLAdmin — purpose-built for FastAPI + SQLAlchemy.

**Consequences:**
- No additional ASGI app needed — mounts directly onto the FastAPI app
- Auto-registration from SQLAlchemy models
- Rules out building a custom admin, using Flask-Admin, or using Django admin
- Admin is always optional (`include_admin` copier question)

---

## ADR-008 — Auth: Custom JWT + Session Backends *(superseded by ADR-034)*

**Context:** Auth libraries like FastAPI-Users and AuthLib exist but impose opinionated user models and flows that conflict with framework-level control.

**Decision:** Custom auth implementation with a pluggable backend system (JWT, session, combined). User model owned by the framework.

**Consequences:**
- Full control over the user model, token format, and session semantics
- Rules out FastAPI-Users, AuthLib, and Starlette-Login as drop-in auth solutions
- Higher maintenance burden — the framework owns the auth code
- Password hashing via pwdlib (Argon2id default, with automatic re-hash on login if parameters change)
- JWT token revocation (denylist) must be stored in Redis, not in-process memory — see NFR
  Security and ADR-015 for the refresh token design that pairs with this requirement

**Superseded by ADR-034.** The `auth_mode` string setting and `CombinedAuthBackend` class described here have been replaced by `auth_backends: list[str]` and a private internal chain. Do not implement this ADR; implement ADR-034 instead.

---

## ADR-009 — Observability: Jaeger + OpenTelemetry

**Context:** Production AI apps require distributed tracing. OpenTelemetry is the vendor-neutral standard; Jaeger is the default backend.

**Decision:** Auto-instrument with OpenTelemetry SDK; Jaeger as the default tracing backend.

**Consequences:**
- OTEL instrumentation works with any OTEL-compatible backend (Datadog, Honeycomb, Tempo) — not locked to Jaeger
- Jaeger is the default in docker-compose; users swap the exporter for other backends
- Rules out proprietary APM SDKs as the primary instrumentation layer
- Tracing is always optional (`tracing` copier question)

---

## ADR-010 — Scaffolder: Copier + Typer

**Context:** Project scaffolding needs conditional file generation, template updates, and an interactive CLI — not just file copying.

**Decision:** Copier for template rendering and project updates; Typer for the interactive CLI wrapper (`fastagentstack new`).

**Consequences:**
- Copier handles `fastagentstack update` (template evolution) natively
- Jinja2 templating in all generated files
- Rules out Cookiecutter (no update support) and custom Jinja2 runners
- `.copier-answers.yml` is written to generated projects for future update tracking

---

## ADR-011 — Tooling

**Context:** The framework needs a consistent, fast development toolchain.

**Decision:** See `.claude/TECH.md` for the full spec. Summary: uv (package manager), ruff (lint/format), mypy strict (type checking), pytest + pytest-asyncio (tests), tox (multi-version matrix: Python 3.11 through the latest stable CPython release at time of testing; currently 3.11, 3.12, 3.13, 3.14).

**Consequences:**
- Rules out pip/pip-tools, black, flake8, unittest as primary tooling
- Minimum Python version: 3.11
- All CI must run the tox matrix; add each new CPython stable release to the envlist when it ships

---

## ADR-012 — Custom Backend Registration: Dotted Python Path

**Context:** Built-in backend families (LLM, vector store, embedding, storage) cover common providers but cannot anticipate every user need. The framework must allow users to supply their own implementations without forking or patching the package.

**Decision:** All four backend factory functions accept a dotted Python path string as the settings value in addition to known aliases. If the value contains a `.`, the factory imports and instantiates the class via `importlib`. The class must fully implement the family's Protocol (Invariant I1).

```python
# settings.py — alias or dotted path both valid
storage_backend: str = "s3"                          # built-in alias
storage_backend: str = "myproject.backends.AzureStorage"  # custom
```

**Consequences:**
- Users can integrate any backend without framework changes
- The Protocol/ABC is the stable contract — custom backends must implement it fully
- Custom backends live in the user's project; their dependencies are the user's responsibility
- The factory's dispatch table covers known aliases first; unknown values are treated as dotted paths
- Rules out plugin registration systems, entry-point hooks, and subclassing the factory as extension mechanisms — dotted path in settings is the one way

---

## ADR-013 — Documentation: Zensical

**Context:** The framework needs a documentation site. MkDocs + Material for MkDocs is the historical default for FastAPI-ecosystem projects, but the Material for MkDocs team has explicitly abandoned MkDocs 2.0 compatibility and is building Zensical as its replacement. FastAPI itself migrated to Zensical. Starting on MkDocs now means a mandatory migration when MkDocs 2.0 ships.

**Decision:** Zensical — static site generator built by the Material for MkDocs team. Config via `zensical.toml` (TOML). Source in `docs/`. Installed as a dev-only dependency group (`[dependency-groups] docs`), not in `project.dependencies`.

**Consequences:**
- Same design language and feature set as Material for MkDocs; no author re-learning
- Rust-based build runtime (ZRX) — faster builds at scale
- TOML config avoids YAML indentation pitfalls
- Zensical is alpha software — toolchain may require occasional patching as it stabilizes
- Rules out MkDocs, mkdocs-material standalone, and Sphinx as the docs tool
- Docs deps are dev-only and do not affect `project.dependencies` (I5 does not apply)

---

## ADR-014 — Changelog Format: Keep a Changelog

**Context:** The project needs a human-readable changelog that users and contributors can scan to understand what changed between releases.

**Decision:** [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. One `CHANGELOG.md` at the repo root. Sections per release: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`. An `[Unreleased]` section accumulates changes until a release is cut. Version tags follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Consequences:**
- Machine-readable format allows tooling (release-drafter, changie) to assist
- `[Unreleased]` section doubles as a pre-release review checklist
- Rules out auto-generated changelogs from commit messages as the primary format — human-written entries are required
- Maintainers must update `CHANGELOG.md` as part of the PR that introduces the change, not as a separate release-day commit

---

## ADR-015 — Auth Token Lifecycle: Access + Refresh Tokens

**Context:** The JWT backend ships with a single access token and a configurable expiry. This forces a binary choice: short expiry (constant re-login, poor UX) or long expiry (revocation is meaningless because the window is too large). The session backend has sliding TTL via Redis but the JWT backend has no equivalent.

**Decision:** Introduce a two-token model for the JWT backend:
- **Access token** — short-lived JWT (default 15 min), same format as today, validated stateless
- **Refresh token** — long-lived opaque token (`secrets.token_urlsafe(32)`), stored in Redis with a configurable TTL (default 30 days), keyed as `refresh:{token}` with value `{user_id}`
- `POST /auth/token` returns both tokens
- `POST /auth/refresh` accepts a refresh token, validates it against Redis, issues a new access token (and optionally rotates the refresh token)
- `POST /auth/logout` deletes the refresh token from Redis and adds the access token's JTI to the denylist

The JWT denylist is stored in Redis (key: `fas:jti:deny:{jti}`, TTL = remaining access token lifetime, per ADR-033 prefix convention) so revocation is visible across all workers.

**Consequences:**
- Access tokens remain stateless and fast to validate (no Redis hit per request)
- Revocation is durable: logout invalidates both the refresh token (deleted from Redis) and the current access token (JTI added to denylist)
- Requires `redis_url` when any entry in `auth_backends` is `"jwt"` — adds a Redis dependency to the JWT path
- Rules out purely stateless JWT architectures where no server-side state is maintained
- The `auth-jwt` extras group must pull in `redis>=5` (currently only in `auth-session` and `rate-limit`)

---

## ADR-016 — Rate Limiting: Redis Fixed-Window Counter

**Context:** Production AI APIs need per-client rate limiting to prevent abuse and manage LLM cost exposure. Common approaches include token bucket, leaky bucket, sliding window, and fixed window algorithms.

**Decision:** Fixed-window counter implemented via a Redis Lua script for atomicity. Each request increments a key scoped to `{client_ip}:{window_start}` with a TTL equal to the window period. The Lua script performs INCR and EXPIRE atomically so no request can race between the two operations. Configurable via `rate_limit_requests` (default 100) and `rate_limit_period` (default 60 seconds). Backed by the same Redis instance as ADR-006.

**Consequences:**
- Fixed window is simpler and cheaper than sliding window — one Redis key per client per window
- Atomic Lua script prevents the INCR/EXPIRE race condition that a pipeline approach has
- Shares the ADR-006 Redis instance — no additional service required
- Fixed window has a known edge case: a burst of 2× the limit can occur across a window boundary; acceptable for most AI API use cases
- Rate limiting is optional (`include_rate_limit` copier question, default false)
- Rules out in-process rate limiting (breaks multi-worker), token-bucket (more complex, marginal benefit), and third-party rate-limit services

---

## ADR-017 — Secrets Management: Cloud Secrets Backends via pydantic-settings

**Context:** Production deployments store credentials in cloud secrets managers (AWS Secrets Manager, GCP Secret Manager) rather than environment variables or `.env` files. The framework uses pydantic-settings for config, which has a documented source-chain extension point (`settings_customise_sources`).

**Decision:** `BaseSettings` overrides `settings_customise_sources()` to inject a cloud secrets source when `SECRETS_BACKEND` is set in the environment. Supported values:
- `aws` — `AWSSecretsManagerSettingsSource` (requires `fast-agent-stack[secrets-aws]`); reads `SECRETS_AWS_SECRET_ID` and `SECRETS_AWS_REGION` from `os.environ`
- `gcp` — `GoogleSecretManagerSettingsSource` (requires `fast-agent-stack[secrets-gcp]`); reads `SECRETS_GCP_PROJECT_ID` from `os.environ`

The bootstrap variables (`SECRETS_BACKEND`, `SECRETS_AWS_SECRET_ID`, `SECRETS_AWS_REGION`, `SECRETS_GCP_PROJECT_ID`) are read directly from `os.environ` inside `settings_customise_sources` — not from pydantic fields — to break the chicken-and-egg dependency.

**Source priority (highest → lowest):**
1. Constructor kwargs (`init_settings`)
2. Environment variables (`env_settings`)
3. Cloud secrets manager (when `SECRETS_BACKEND != "none"`)
4. `.env` file (`dotenv_settings`)
5. File secrets (`file_secret_settings`)

Env vars always override the secrets manager so local development overrides work without modifying the remote secret.

**Extras:**
- `fast-agent-stack[secrets-aws]` — installs `boto3>=1.34` (required by `AWSSecretsManagerSettingsSource`)
- `fast-agent-stack[secrets-gcp]` — installs `google-cloud-secret-manager>=2.20` (required by `GoogleSecretManagerSettingsSource`)

The `secrets_backend` copier question (default `"none"`) adds the relevant extras to the generated `pyproject.toml`. Runtime behavior is controlled entirely by environment variables, so the same generated project works across dev (`.env`), staging (env vars), and production (secrets manager) with zero code changes.

**Consequences:**
- Zero overhead when `SECRETS_BACKEND` is unset — the default source chain is unchanged
- Missing extras produce a clear `ImportError` at settings construction time (not at first field access)
- The AWS SM secret must be a JSON object whose keys are settings field names (without the project env prefix)
- Rules out per-field secret references (e.g. `@app.get_secret("name")` patterns) — all settings flow through the unified pydantic-settings source chain

---

## ADR-018 — Email Delivery: aiosmtplib + stdlib email

**Context:** Auth flows (password reset, email verification) defined in `spec/SCENARIOS.md` S11 require sending transactional emails. The framework must choose an async-compatible email library and a configuration model without pulling in a new required dependency.

**Decision:** Use `aiosmtplib` as the async SMTP client. Email sending is behind an optional extra (`fast-agent-stack[email-smtp]`). Email is not a core dependency — an app without auth or without email verification does not need it. The framework does not provide a SES or SendGrid backend out of the box; users who need those point the `email_backend` setting to a dotted Python path (same pattern as ADR-012).

**`BaseSettings` fields added:**
```python
email_backend: str = "smtp"           # "smtp" | dotted path for custom
smtp_host: str = "localhost"
smtp_port: int = 587
smtp_username: str | None = None
smtp_password: str | None = None
smtp_use_tls: bool = True
email_from: str = "noreply@example.com"
email_from_name: str = "FastAgentStack"
```

**Extras:**
- `fast-agent-stack[email-smtp]` — installs `aiosmtplib>=3`

**Consequences:**
- Async SMTP — no thread pool required; satisfies I2
- `email_backend = "myproject.email.SESBackend"` allows custom backends via ADR-012 dotted-path pattern
- Email sending is a fire-and-forget coroutine; failures are logged but do not abort the HTTP response
- Rules out Django-style email backends, Celery-based queued email, and synchronous smtplib wrappers
- The `extract-all` bundle and the base install are unaffected — `email-smtp` is its own optional extra

---

## ADR-019 — ASGI Server: Uvicorn via fastapi-cli internals

**Context:** The framework needs a default ASGI server for development and production. Two candidates: Uvicorn (FastAPI's official default, used internally by `fastapi run`) and Granian (Rust-based, newer). The CLI must bind to exactly one default.

**Decision:** Two CLI commands are exposed, both backed by `uvicorn.run()` with no subprocess spawning. App auto-detection uses `fastapi_cli.discover.get_import_data`.

| Command | Default host | Reload | Workers flag |
|---------|-------------|--------|--------------|
| `fastagentstack dev` | `127.0.0.1` | on | no |
| `fastagentstack run` | `0.0.0.0` | off | yes (`--workers`) |

This gives us:
- Auto-detection of the app module (`main.py`, `app.py`, `api.py`, etc.)
- PYTHONPATH manipulation for importability
- `uvicorn.run()` with proper config

**Consequences:**
- Works in any environment where `fast-agent-stack` is installed — generated projects need no separate venv
- Inherits FastAPI CLI's app discovery logic without reimplementing it
- Depends on `fastapi-cli` as an import (already a FastAPI dependency)
- Users who prefer Granian or Hypercorn can run them directly against the generated ASGI app
- Rules out subprocess delegation (fragile PATH dependency) and Granian as default

---

## ADR-020 — Scheduling: periodiq

**Context:** Dramatiq (ADR-005) has no built-in periodic scheduling. A scheduler is needed to run cron-style recurring tasks. Options: APScheduler (general-purpose), periodiq (Dramatiq-native), dramatiq-crontab (Django-only), OS cron.

**Decision:** periodiq — a lightweight Dramatiq-native scheduler that uses SIGALRM with zero additional dependencies beyond Dramatiq itself.

```python
from dramatiq import actor
from periodiq import cron

@actor(periodic=cron("0 */6 * * *"))
def sync_embeddings():
    ...
```

Run via: `fastagentstack scheduler` (starts the periodiq worker process that checks schedules and enqueues matching actors).

**Consequences:**
- No additional framework — periodic schedules are declared inline on actors via `@cron` decorator
- Single lightweight process (`periodiq` worker) checks schedules and enqueues matching actors
- No job store or database required — schedules are defined in code
- `include_scheduler` copier question controls whether the periodiq dependency and CLI command are generated
- Rules out APScheduler (heavier, separate job store, not Dramatiq-native) and OS cron (not portable)

---

## ADR-021 — LLM Providers: Direct SDKs Behind a Protocol

**Context:** The AI module needs to support multiple LLM providers. Two approaches: (A) wrap everything through LiteLLM as a universal adapter, or (B) write thin direct SDK wrappers behind a shared protocol, with LiteLLM as just another backend option.

**Decision:** Direct SDK backends behind an `LLMBackend` protocol. Each provider is an optional extra (`fast-agent-stack[bedrock]`, `[openai]`, `[anthropic]`, `[litellm]`).

```python
class LLMBackend(Protocol):
    model_id: str
    async def complete(self, messages: list[Message], **kwargs) -> CompletionResult: ...
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]: ...
    async def count_tokens(self, messages: list[Message]) -> int: ...
```

**Note:** The `CompletionResult` return type for `complete()` and the full streaming contract for `stream()` are defined by ADR-036, which amends this ADR. The signature shown above reflects the post-ADR-036 state.

**Consequences:**
- Minimal dependency footprint — only the SDK you use gets installed
- Full control over each provider's features (Bedrock's converse API, OpenAI's function calling, Anthropic's tool use) without LiteLLM's abstraction leaking
- LiteLLM available as a backend for users who want its proxy/routing features, registered via ADR-012 dotted-path
- Custom backends follow the same ADR-012 pattern: `llm_backend = "myproject.llm.MyBackend"`
- Rules out LiteLLM-as-sole-adapter (adds a heavy transitive dep tree, obscures provider-specific features, breaks when LiteLLM lags behind provider API changes)

---

## ADR-022 — Version Source: `__version__.py` + Hatchling Dynamic Version

**Context:** The version string must be readable at runtime (`fast_agent_stack.__version__`) and also drive the `pyproject.toml` package metadata. Two patterns exist: (A) hardcode version in `pyproject.toml` and duplicate it in `__init__.py`; (B) keep one canonical `__version__.py` and read it from both places. Pattern A creates two places to update on every release, which will drift.

**Decision:** Single source of truth in `fast_agent_stack/__version__.py`:

```python
__version__ = "0.1.0"
```

`pyproject.toml` reads it dynamically via Hatchling (the build backend):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
dynamic = ["version"]

[tool.hatch.version]
path = "fast_agent_stack/__version__.py"
```

`fast_agent_stack/__init__.py` imports it:

```python
from fast_agent_stack.__version__ import __version__
```

**Consequences:**
- One file to edit on every release — no drift between runtime `__version__` and the installed package metadata
- Hatchling is the build backend (replaces any setuptools assumption in ADR-011); uv is compatible with hatchling out of the box
- `importlib.metadata.version("fast-agent-stack")` also works at runtime as an alternative read path
- Rules out `[project] version = "..."` static field (requires duplicate update); rules out `importlib.metadata`-only approaches (version unreadable before install)

---

## ADR-023 — Lifespan Hook Interface: Async Context Manager (`__aenter__` / `__aexit__`)

**Context:** `LifespanHook` objects need to run code at application startup and shutdown. Two interfaces were considered:

- **Callback pair** (`on_startup() / on_shutdown()`): explicit, easy to read, mirrors Django signals and some ASGI frameworks.
- **Async context manager** (`__aenter__` / `__aexit__`): standard Python async resource protocol; directly composable with `AsyncExitStack`.

The callback pair has two failure-safety problems: (1) if `on_startup` raises, partially initialised hooks must be cleaned up manually; (2) teardown order must be implemented explicitly with `reversed(hooks)`. Both are solved for free by `AsyncExitStack`, which guarantees LIFO teardown and propagates exceptions through `__aexit__` correctly.

The context manager form also aligns with FastAPI's own lifespan pattern (`@asynccontextmanager`) and means any class that already implements `async with` (e.g., `httpx.AsyncClient`, `aiohttp.ClientSession`) can be used as a hook directly or as a delegate inside one.

**Decision:** `LifespanHook` is an async context manager protocol:

```python
class LifespanHook(Protocol):
    async def __aenter__(self) -> None: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None: ...
```

`FastAgentStack` drives hooks via `contextlib.AsyncExitStack`:

```python
async with AsyncExitStack() as stack:
    for hook in hooks:
        await stack.enter_async_context(hook)
    yield
```

**Consequences:**
- Exception safety is provided by `AsyncExitStack` at no cost — partial startup failures clean up already-entered contexts automatically
- Teardown order (LIFO) is guaranteed without explicit `reversed()` logic
- Any async context manager is a valid hook with zero boilerplate
- Rules out the `on_startup / on_shutdown` callback pair — existing code using that interface must migrate to `__aenter__ / __aexit__`

---

## ADR-024 — Frontend Serving: `app.frontend()` for Static SPA

**Context:** AI applications typically need a user-facing frontend (chat UI, dashboard, etc.) alongside the API. Options considered:

- **Separate deployment** (Vercel, Cloudflare Pages, S3+CloudFront): adds infrastructure complexity, CORS config, separate CI/CD pipeline.
- **`StaticFiles` mount**: works but doesn't handle SPA fallback routing (client-side routes return 404).
- **`app.frontend()`** (FastAPI >=0.138.0): purpose-built for serving static SPA builds with automatic fallback routing. API routes take priority; unmatched paths serve `index.html`.

`app.frontend()` gives a Django-like single-deployment experience — one container serves both API and UI — while still allowing split deployments in production via a CDN in front.

SQLAdmin remains the admin console (server-rendered, auto-generated from models). `app.frontend()` serves the user-facing application.

**Decision:** Use `app.frontend("./frontend/dist")` for serving the static frontend build. Optional feature gated by `include_frontend` in the scaffolder.

**Consequences:**
- Single deployable artifact for API + frontend
- No CORS configuration needed between frontend and API (same origin)
- SPA client-side routing works out of the box (fallback to `index.html`)
- `fastagentstack new` generates a `frontend/` directory stub when enabled
- Production deployments can optionally serve frontend via CDN instead
- Requires `fastapi>=0.138.0`

---

## ADR-025 — SQLAlchemy and Alembic as Core Dependencies

**Context:** ADR-002 established SQLAlchemy async and Alembic as the fixed ORM and migration tool. A separate question remained open: should `sqlalchemy[asyncio]` and `alembic` live in `project.dependencies` (always installed) or behind a `db` extras group (opt-in)? The async database drivers (`asyncpg`, `aiosqlite`, `aiomysql`) were already placed in `db-*` extras groups because they are engine-specific. The question is whether the ORM layer itself follows the same pattern.

**Decision:** `sqlalchemy[asyncio]` and `alembic` belong in `project.dependencies` — always installed. The async engine drivers (`asyncpg`, `aiosqlite`, `aiomysql`) remain in optional `db-postgres`, `db-sqlite`, and `db-mysql` extras groups and must continue to be import-guarded (I3).

**Rationale:**
- The database layer is not a pluggable backend family. ADR-002 is a fixed choice: SQLAlchemy is the ORM and Alembic is the migration tool. There is no supported path to swap either of them out without violating ADR-002.
- Because users cannot choose a different ORM, there is no scenario where fast-agent-stack is deployed without SQLAlchemy. Gating it behind an extra would create a spurious install step with no corresponding user choice.
- The CLI commands `migrate` and `makemigrations` (Phase 2) call Alembic directly. These commands must work after `pip install fast-agent-stack` with no additional extras. Requiring `pip install fast-agent-stack[db]` before `fastagentstack migrate` can run would be confusing and undocumented behaviour.
- NFR Modularity (lines 17–19) explicitly names AI, vector, storage, and task-queue as the categories excluded from the core install. ORM and migration tooling are conspicuously absent from that exclusion list — this is intentional.

**Rejected alternatives:**
- **`db` extras group containing `sqlalchemy[asyncio]` and `alembic`** — rejected because it implies these are optional, which they are not. It would also gate the `migrate`/`makemigrations` CLI commands behind an extras install, degrading DX from day one.
- **`db-core` extras group separate from `db-postgres` / `db-sqlite`** — rejected for the same reason; it adds installation friction with no benefit, since neither ORM nor migrations are optional.

**Consequences:**
- `sqlalchemy[asyncio]>=2.0` and `alembic>=1.13` are present in `project.dependencies` in `pyproject.toml`. No change required — they are already there.
- The `db-postgres`, `db-sqlite`, and `db-mysql` extras groups contain only the async engine driver for that database. They do not re-bundle SQLAlchemy or Alembic.
- I3 (extras gate) applies to the async drivers in `db-*` extras but does not apply to SQLAlchemy or Alembic imports, which are always available after install.
- The NFR Modularity section must explicitly note that ORM (`sqlalchemy[asyncio]`) and migrations (`alembic`) are part of the core install and are not subject to the AI/vector/storage/task-queue exclusion rule.
- `spec/ARCHITECTURE.md` Extras Reference table must note that `db-*` extras contain drivers only, not the ORM.
- Any future agent or reviewer must not raise a NEEDS-DECISION flag on SQLAlchemy or Alembic being in `project.dependencies` — this ADR is the decision record.

## ADR-026 — App Registration: Dual Mechanism (INSTALLED_APPS + install_app)

**Context:** The framework needs a way to register route modules and full app modules. Django uses `INSTALLED_APPS` for everything, but FastAPI's ecosystem typically uses `include_router()` directly. Two use cases emerged:

1. **Simple route modules** — a file with a `router: APIRouter`. No models, no admin views. Just routes.
2. **Full app modules** — provide routes, models, and admin views as a cohesive unit.

A single mechanism can't serve both well: forcing the `AppModule` protocol on simple route files adds ceremony; using only string-based imports loses the ability to collect models and admin views.

**Decision:** Two registration paths:

- **`INSTALLED_APPS`** — a list of dotted strings (e.g., `"apps.chat.routes"`). The framework imports the module and includes its `router: APIRouter` attribute. Router-only; models and admin views are NOT auto-discovered via this path.
- **`app.install_app(module: AppModule)`** — calls the `AppModule` protocol: `get_router()`, `get_models()`, `get_admin_views()`. Full discovery; `AdminLifespanHook` collects admin views only from modules registered this way.

**Consequences:**
- Simple route modules stay simple — just define `router` and add to `INSTALLED_APPS`
- Full app modules get first-class model and admin registration
- `AdminLifespanHook` only sees modules registered via `install_app()` — not `INSTALLED_APPS` string imports
- All `install_app()` calls must complete before lifespan begins (see I9)
- Generated `app.py` uses `install_app()` for the main app module (since it has models)

## ADR-027 — CLI Alias: `fas` as shorthand for `fastagentstack`

**Context:** `fastagentstack` is verbose for frequent use. A shorter alias improves DX for daily commands like `fas migrate`, `fas dev`, `fas new`.

Checked for conflicts: no standard Unix/macOS/Linux utility named `fas`. `fasd` (directory autojump, archived) exists but is a different name. No Homebrew formula, no PyPI package installs a `fas` binary.

**Decision:** Register `fas` as an additional entry point alongside `fastagentstack`.

```toml
[project.scripts]
fastagentstack = "fast_agent_stack.cli.main:app"
fas = "fast_agent_stack.cli.main:app"
```

**Consequences:**
- Both `fas dev` and `fastagentstack dev` work identically
- Documentation uses `fas` for brevity, mentions `fastagentstack` as the canonical name
- Minimal collision risk — no known conflicting tool

## ADR-028 — Authorization Model: Django-style Users, Groups & Permissions

**Context:** The framework needs RBAC. Options considered:

- **Casbin/OPA** — powerful but external policy engines add deployment complexity and latency for simple cases.
- **Django's auth model** — battle-tested, universal naming (AWS IAM, Atlassian, Django all use User/Group). Simple relational model, easy to reason about.
- **Role-only (no permissions table)** — too coarse; forces role-per-action workarounds.

**Decision:** Django-inspired relational RBAC with Users, Groups, and Permissions.

Tables:

| Table | Key fields |
|---|---|
| `users` | id, email, password_hash, is_active, is_verified, is_staff, is_superuser, date_joined |
| `groups` | id, name, description |
| `permissions` | id, resource, action (e.g. `"posts"`, `"delete"`) |
| `user_groups` | user_id, group_id |
| `group_permissions` | group_id, permission_id |
| `user_permissions` | user_id, permission_id (direct grants) |

Key differences from Django:
- No ContentType framework (Django-specific ORM coupling, not applicable)
- `resource` + `action` instead of Django's `codename` — more explicit, easier to query
- `is_verified` added (Django doesn't have email verification built-in)
- Uses "Group" not "Role" — matches Django, AWS IAM, Atlassian convention

`user_permissions` provides direct grants without forcing single-user groups. `is_superuser` bypasses all permission checks (same as Django).

**Consequences:**
- Permission check: `user.is_superuser OR permission in user_permissions OR permission in any of user's group_permissions`
- Framework provides `require_permission("resource.action")` dependency for route protection. Argument is a single dot-separated string (split on first `.` to get resource and action).
- Groups are optional — direct `user_permissions` work for simple cases
- Auth models are part of core (always present when `include_auth` is enabled), not gated behind any extra
- SQLAdmin panel (separate `admin` extra) provides UI to manage users/groups/permissions

## ADR-029 — JWT Library: PyJWT

**Context:** Two main Python JWT libraries:

- **PyJWT** — JWT (JWS) encode/decode only. Actively maintained, simple API, used in FastAPI docs.
- **python-jose** — full JOSE spec (JWE, JWK, JWS, JWT). Larger surface area.

The framework only needs JWT signing/verification. JWE and JWK are out of scope.

**Decision:** `pyjwt[crypto]>=2.8`. The `[crypto]` extra adds `cryptography` for RS256.

Default algorithm: HS256 (single `secret_key`). RS256 available via config for asymmetric deployments.

**Consequences:**
- Minimal dependency — only what's needed
- Rules out python-jose
- `auth-jwt` extras: `pyjwt[crypto]>=2.8`, `pwdlib[argon2]>=0.3`, `redis>=5`

---

## ADR-030 — Password Hashing: pwdlib + Argon2id

**Context:** `passlib` is unmaintained (last release 2020, Python 3.14 issues). Alternatives:

- **pwdlib** — modern replacement by fastapi-users author. Active (2025). Supports argon2 + bcrypt with built-in `needs_rehash` detection.
- **bcrypt** / **argon2-cffi** — raw bindings, no high-level API (hash/verify/rehash).

Argon2id is the 2026 OWASP recommendation: memory-hard, resistant to GPU/ASIC attacks. Bcrypt has 72-byte password truncation and no memory-hardness.

**Decision:** `pwdlib[argon2]>=0.3` with Argon2id as the default algorithm.

Parameters (OWASP 2024 minimum): time_cost=3, memory_cost=65536 (64MB), parallelism=4.

Re-hash policy: on successful login, if `hasher.needs_rehash(stored_hash)` returns True (parameters changed in config), transparently re-hash and persist.

**Consequences:**
- Stronger than bcrypt against modern GPU attacks
- Built-in re-hash detection — cost upgrades happen transparently on login
- No 72-byte password truncation
- Rules out passlib as a dependency
- Legacy bcrypt hashes (if migrating) can be verified via `pwdlib[bcrypt]` and re-hash to argon2 on next login

---

## ADR-031 — API Key Format & Storage

**Context:** API keys need identifiability and secure at-rest storage.

**Decision:**

Format: `fas_<32-byte-urlsafe-base64>` (prefix + 43 random chars).

Storage:
- Show-once: full key returned only in `POST /api-keys` response, never stored in plaintext.
- SHA-256 hash stored in `api_keys` table (high-entropy input makes bcrypt unnecessary).

Table schema:

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| user_id | FK → users | owner |
| name | str | human label |
| key_hash | str | SHA-256 hex digest |
| key_prefix | str(8) | first 8 chars for UI identification |
| scopes | JSON | optional permission scopes |
| expires_at | datetime | nullable |
| created_at | datetime | |
| last_used_at | datetime | nullable, updated on each use |
| revoked_at | datetime | nullable |

Lookup: SHA-256 hash incoming key, query by `key_hash`. Header: `Authorization: Bearer fas_...` (prefix discriminates from JWT).

**Consequences:**
- Show-once — key never retrievable after creation
- SHA-256 is O(1) per request (no bcrypt latency)
- `key_prefix` allows identification without exposing full key
- Revocation is instant (`revoked_at` set)

## ADR-032 — Session Auth: Cookie Transport & Redis Storage

**Context:** The session auth backend needs binding decisions on cookie semantics, session ID generation, TTL behavior, and Redis storage schema.

**Decision:**

Cookie flags:
- `HttpOnly: true` — prevents XSS access to session ID
- `SameSite: Lax` — protects against CSRF while allowing top-level navigation
- `Secure: true` in production (when `settings.debug is False`)
- Cookie name: `fas_session`

Session ID: `secrets.token_urlsafe(32)` — 256 bits of entropy (43 chars).

TTL: Sliding window. Default 24 hours, configurable via `settings.session_ttl_seconds`. Each request resets the TTL (Redis `EXPIRE` on access).

Redis key schema: `fas:session:{session_id}` — value is JSON-serialized session data (`user_id`, `created_at`, metadata).

**Consequences:**
- HttpOnly prevents client-side JS from reading session — mitigates XSS token theft
- SameSite=Lax balances CSRF protection with UX (GET navigations work)
- Sliding TTL means active users stay logged in; idle sessions expire
- Redis key prefix `fas:session:` avoids collision with other subsystems (see ADR-033)
- Session invalidation: delete the Redis key (immediate, no denylist needed)

---

## ADR-033 — Redis DB Index Assignment

**Context:** Multiple framework subsystems share a single Redis instance. Without namespace separation, key collisions are possible. Redis supports 16 databases (0-15) and key prefixes.

**Decision:** Use key prefixes on a single DB (index 0) rather than separate DB indices.

| Subsystem | Key prefix | Example key |
|---|---|---|
| Sessions | `fas:session:` | `fas:session:abc123...` |
| JWT denylist | `fas:jti:deny:` | `fas:jti:deny:550e8400-e29b...` |
| Refresh tokens | `fas:refresh:` | `fas:refresh:abc123...` |
| Rate limiting | `fas:rl:` | `fas:rl:192.168.1.1:/api/users` |
| Task broker (Dramatiq) | `dramatiq:` | (Dramatiq's own prefix, unchanged) |

Rationale for prefixes over DB indices:
- `SELECT <db>` doesn't work with connection pooling (pool returns connections to arbitrary DBs)
- Prefixes work with Redis Cluster (which only supports DB 0)
- Easier to inspect/debug with `KEYS fas:session:*`
- Dramatiq already uses its own prefix convention — no conflict

**Consequences:**
- All subsystems use `redis_url` pointing to DB 0 (single connection pool)
- No `SELECT` commands needed — simpler connection management
- Key prefixes are framework-internal; users don't configure them
- Compatible with Redis Cluster deployments
- `FLUSHDB` flushes everything — use prefix-scoped `SCAN + DEL` for selective cleanup

---

## ADR-034 — Auth Backends as an Ordered List (Django-style Multi-Backend Support)

- **Decision:** Replace `auth_mode: str` in `FasSettings` with `auth_backends: list[str]`. Each entry is either a built-in alias (`"jwt"`, `"session"`) or a dotted Python path to a custom class implementing the `AuthBackend` Protocol (per ADR-012). The factory `get_auth_backend()` instantiates each backend and wraps them in a private internal chain that is not exported and carries no public name. `CombinedAuthBackend` is deleted entirely.

  Chain delegation rules:
  - `authenticate(request)` — try each backend in order; return the first non-`None` result
  - `verify_token(token)` — try each backend in order; return the first non-`None` result
  - `create_token(user, response)` — primary (first) backend only
  - `refresh_token(refresh_tok)` — primary (first) backend only
  - `revoke_token(request, response, refresh_tok)` — run on ALL backends (cleanup on logout)

  Single-backend deployments pass a list of one entry and incur no overhead from the chain wrapper.

- **Rationale:** Mirrors Django's `AUTHENTICATION_BACKENDS` — a known, well-understood pattern. Eliminates `CombinedAuthBackend` as a premature named concept that hardcodes ordering and token-issuance strategy. Supports future backends (API key bearer, OAuth token introspection) without adding new factory modes. Revoke-all on logout is correct: if a user can authenticate via multiple methods, all should be invalidated.

- **Rejected:**
  - Keep `CombinedAuthBackend` — rejected: hardcodes JWT-first ordering and always issues JWT tokens, which is wrong when session is the primary backend.
  - Split Protocol into authenticator + token-lifecycle interfaces — rejected: the primary-backend delegation pattern is simpler and avoids doubling the Protocol surface area.

- **Consequences:**
  - `auth_mode` setting key is removed; `auth_backends: list[str]` replaces it in `FasSettings`.
  - `CombinedAuthBackend` class (`core/auth/backends/combined.py`) is deleted.
  - `get_auth_backend()` factory signature is unchanged externally — it still returns an `AuthBackend`-conforming object — but internally it builds a chain for any list length.
  - `core/auth/backends/` directory: `combined.py` is removed; `factory.py` is updated to accept `list[str]` and produce the internal chain.
  - I11 (startup secrets validation) is updated: references to `auth_backend` being `"jwt"` or `"both"` become `"jwt" in auth_backends` / `"session" in auth_backends`.
  - NFR Security section is updated to use the new setting name.
  - DX.md scaffolder prompt is updated: `? Auth method?` options change from `(JWT / Session / Both)` to `(JWT / Session / JWT + Session)`, and generated settings examples use `auth_backends = ["jwt"]`.
  - GLOSSARY.md gains a new term: **auth backend chain**.
  - Supersedes ADR-008.

## ADR-035 — Token Usage Metering: Per-Request Event Log

**Context:** AI applications need token usage tracking for cost attribution, budgeting, and rate enforcement. Design decisions:

1. **Granularity:** per-request (every LLM call logged individually) vs. pre-aggregated counters (only totals stored).
2. **Attribution:** per-user, per-API-key, per-agent, per-conversation — or all of them?
3. **Storage:** same database as the app, separate analytics DB, or Redis counters?

Per-request logging gives maximum flexibility — aggregation can be done after the fact by any dimension. Pre-aggregated counters are faster to query but lose detail.

**Decision:** Per-request event log in the application database.

Table: `token_usage_log`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| user_id | UUID | nullable, soft reference to users (no FK — AI tables must work without auth tables) |
| api_key_id | UUID | nullable, soft reference to api_keys |
| agent_name | str | which agent handled the request |
| model | str | model identifier (e.g., `claude-sonnet-4-20250514`) |
| prompt_tokens | int | input tokens |
| completion_tokens | int | output tokens |
| total_tokens | int | computed: prompt + completion |
| cost_microcents | int | nullable, estimated cost in 1/10000 cents |
| conversation_id | UUID | nullable, for thread-level attribution |
| created_at | datetime | indexed for time-range queries |

Key design choices:
- **Per-request rows** — no pre-aggregation. Dashboards and billing aggregate via SQL (`GROUP BY user_id, date_trunc('day', created_at)`).
- **Multi-dimensional attribution** — user_id, api_key_id, agent_name, conversation_id all captured. Query by any dimension.
- **cost_microcents** — optional, computed at write time from a model pricing table. Nullable because not all providers expose cost immediately.
- **Same database** — simpler ops, no separate analytics store needed at framework scale. Users can replicate to a data warehouse if needed.

The `LLMBackend.complete()` and `LLMBackend.stream()` methods return token counts in their response. Token count delivery is specified by ADR-036: `complete()` returns a `CompletionResult`; `stream()` emits a trailing `CompletionResult` as its final item. The framework's SSE streaming helper intercepts the trailing item and calls `UsageService.log_usage()`.

**Consequences:**
- Every LLM call produces one row — high-volume apps may need table partitioning (by month)
- No Redis counters needed — DB is the source of truth for usage
- Rate limiting by token budget is possible: `SELECT SUM(total_tokens) WHERE user_id = ? AND created_at > now() - interval '1 day'`
- Framework provides a `UsageService` with `log_usage()` (Phase 4c) and `get_usage(user_id, period)` (Phase 6) methods
- The table is a framework migration (`0002_fas_ai_token_usage.py`) — auto-applied when AI extras are installed
- Users who don't need metering can ignore it (rows accumulate but don't affect performance until millions+)
- Token count carrier type (`CompletionResult`) and the streaming sentinel pattern are defined in ADR-036

---

## ADR-036 — CompletionResult Type and LLMBackend Streaming Contract

- **Decision:** Define `CompletionResult` as the canonical return type for `LLMBackend.complete()` and as the terminal sentinel item in `LLMBackend.stream()`. Update the `LLMBackend` Protocol to reflect these return types. Clarify the agent dispatcher contract for streaming handlers.

  **`CompletionResult` dataclass** (defined in `core/ai/llm/__init__.py`):

  ```python
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class CompletionResult:
      content: str          # generated text (empty string for the streaming sentinel)
      model: str            # model identifier used for the call
      prompt_tokens: int
      completion_tokens: int
      total_tokens: int
      cost: float | None    # None when the backend cannot compute cost (e.g., self-hosted)
  ```

  **Updated `LLMBackend` Protocol** (amends ADR-021):

  ```python
  class LLMBackend(Protocol):
      @property
      def model_id(self) -> str: ...
      async def complete(
          self, messages: list[Message], **kwargs
      ) -> CompletionResult: ...
      async def stream(
          self, messages: list[Message], **kwargs
      ) -> AsyncIterator[str | CompletionResult]: ...
      async def count_tokens(self, messages: list[Message]) -> int: ...
  ```

  **Streaming sentinel contract:** `stream()` is an async generator that yields `str` chunks for content, then yields exactly one `CompletionResult` as its final item. The `CompletionResult` sentinel has `content=""` and carries the full token counts for the streaming call. No content chunks may follow the sentinel.

  **SSE streaming helper contract** (`core/ai/streaming.py`):
  - Iterates `backend.stream(...)`.
  - Each `str` item is written as an SSE `data:` event to the response.
  - The trailing `CompletionResult` item is intercepted: it is **not** written to SSE; instead it is passed to `UsageService.log_usage()`.
  - Write failures in `UsageService.log_usage()` must be logged and swallowed — they must not abort or delay the streaming response (see I21).
  - **Error-before-sentinel:** If `stream()` raises an exception before the `CompletionResult` sentinel is emitted (e.g., a network error from the LLM provider after some chunks), `stream_sse` must propagate the exception to the client (resulting in a 500 response or connection drop). `UsageService.log_usage()` must NOT be called — there is no usage data to record. This is a distinct failure path from I21 (which covers only `log_usage()` write failures, not upstream LLM errors).

  **Agent dispatcher contract** (`core/ai/agents.py`):
  - Non-streaming handlers: `async def handler(...) -> str` — called, result passed to `complete()`, returned `CompletionResult` logged via `UsageService.log_usage()`.
  - Streaming handlers: `async def handler(...) -> AsyncIterator[str]` (detected via `inspect.isasyncgenfunction`) — iterated, each `str` chunk emitted as SSE, trailing `CompletionResult` intercepted and logged.

- **Rationale:**
  - Cleanest design: each backend already has full token-count knowledge at call time; embedding it as the final stream item avoids a separate callback or metadata channel.
  - The terminal-sentinel pattern is established (used by LangChain, LiteLLM). It keeps `stream()` return type informative without requiring a parallel channel.
  - `isinstance(item, CompletionResult)` is the single dispatch predicate — simple to implement and test.
  - ADR-035 metering middleware can intercept the sentinel without any additional framework machinery.

- **Rejected:**
  - **Separate `last_stream_usage()` method on backends** — rejected: stateful, breaks concurrent requests sharing a backend instance.
  - **Context variable (`contextvars.ContextVar`) for streaming usage** — rejected: implicit, hard to test in isolation, requires careful propagation across async boundaries.
  - **Ignore token counts for streaming** — rejected: ADR-035 requires metering on all LLM calls, including streaming ones.
  - **`AsyncIterator[str]` only, pull usage separately** — rejected: introduces a two-step API that callers must always pair correctly.

- **Consequences:**
  - `CompletionResult` is defined in `core/ai/llm/__init__.py` and exported from `fast_agent_stack.core.ai.llm`.
  - All `LLMBackend` implementations (Bedrock, OpenAI, Anthropic, LiteLLM) must emit a trailing `CompletionResult` as the final item of their `stream()` async generator.
  - `core/ai/streaming.py` (`stream_sse` helper) is responsible for splitting `str` chunks (→ SSE) from the trailing `CompletionResult` (→ `UsageService.log_usage()`).
  - ADR-021 is amended by this ADR (not superseded) — it adds return-type specificity to the previously undefined `CompletionResult` reference and corrects the `stream()` return type annotation.
  - ADR-035 is updated to reference `CompletionResult` as the token count carrier for both `complete()` and `stream()` paths.
  - Invariant I21 is added: token usage log write failures must not abort or delay the LLM response.
  - `spec/GLOSSARY.md` gains three terms: `CompletionResult`, `UsageService`, `ConversationLog`.
  - `spec/ARCHITECTURE.md` Module 9 (LLM Provider Abstraction) and Module 10 (Agent Lifecycle) are updated to document the type definitions and dispatcher contract.

## ADR-037 — Redis Integration: fastapi-redis-sdk

**Phase:** 8 (deferred — Phases 3c through Phase 6 remain on `redis.asyncio` directly)

**Context:** The framework needs Redis for sessions, JWT denylist, rate limiting, and response caching. Options:

- **`redis.asyncio` (raw)** — manual connection pool lifecycle, lifespan hook, DI wiring. Used in Phases 3c–6.
- **`fastapi-redis-sdk`** — official Redis org library for FastAPI (PyPI: `fastapi-redis-sdk`, import: `redis_fastapi`). Manages connection pools via lifespan, provides `AsyncRedisDep` for DI, includes response caching with ETag/304/Cache-Control. Published by Redis Inc, v0.7.0 available (Jun 2026). Requires redis-py 6.0+, Redis server 7.4+, Python 3.10+.

**Decision:** Migrate to `fastapi-redis-sdk` as the Redis integration layer in Phase 8, after all Redis usage patterns (auth, rate-limit, caching) are established.

**Current state (Phases 3c–6):** `redis>=5` (`redis.asyncio`) used directly. `AuthLifespanHook` manages pool lifecycle. Backends (`JWTAuthBackend`, `SessionAuthBackend`) take `Redis` at construction time.

```toml
# Phase 8 target — in auth-jwt, auth-session, rate-limit extras
"fastapi-redis-sdk>=0.7"
```

Usage:
```python
from redis_fastapi import FastAPIRedis, AsyncRedisDep

# In app setup
FastAPIRedis(app).lifespan().caching()

# In routes/services — raw Redis client via DI
async def get_session(redis: AsyncRedisDep):
    return await redis.get("fas:session:abc123")
```

**Phase 8 migration scope:**
- Replace `redis>=5` with `fastapi-redis-sdk>=0.7` across `auth-jwt`, `auth-session`, `rate-limit` extras
- Migrate `AuthLifespanHook` pool lifecycle to `FastAPIRedis(app).lifespan()` — amend I9 accordingly
- Migrate `JWTAuthBackend` and `SessionAuthBackend` constructors from `Redis`-at-init to `AsyncRedisDep` request-time DI
- Update rate-limit middleware to use `AsyncRedisDep`
- Update I3 import guards: `redis_fastapi` replaces `redis.asyncio` guards
- Update all affected tests

**Consequences:**
- Eliminates custom Redis lifespan hook — pool lifecycle managed by the SDK
- `AsyncRedisDep` provides the raw `redis.asyncio.Redis` client as a FastAPI dependency
- Response caching (`cache()`, `cache_evict()`, `cache_put()`) available as optional DI decorators
- Pydantic-validated config (REDIS_URL, TLS, cluster mode) from env — aligns with our settings pattern
- Cluster-ready out of the box
- Sessions, denylist, rate-limiting logic stays ours — built on top of `AsyncRedisDep`
- Replaces `redis>=5` in extras with `fastapi-redis-sdk>=0.7` (which depends on redis-py internally)
- I9 must be amended atomically with the Phase 8 code changes (see amendment text below)

**I9 amendment to apply atomically with Phase 8 implementation:**

Replace the I9 body in `spec/INVARIANTS.md` with the following. `INVARIANTS.md` must not be updated
before the code lands — doing so would create a spec/implementation mismatch while the codebase still
uses `redis.asyncio` directly.

```
## I9 — Lifespan Hook Registration Order

`DatabaseLifespanHook` must be registered before any hook that depends on the database. When Redis is
required (auth, rate-limit, or caching enabled), `FastAPIRedis(app).lifespan()` must be registered
immediately after `DatabaseLifespanHook` and before any hook that accesses the pool. The canonical
registration order is:

1. `DatabaseLifespanHook` — initialises engine and session factory
2. `FastAPIRedis(app).lifespan()` — initialises Redis connection pool (SDK-managed; I11 connectivity
   check); conditional — only registered when Redis is needed (auth, rate-limit, or caching enabled)
3. `AuthLifespanHook` — constructs auth backends; no Redis I/O; backends acquire the client via
   `AsyncRedisDep` at request time
4. `RateLimitLifespanHook` — wires `RateLimitMiddleware`; middleware acquires Redis via
   `request.app.state` (SDK-managed pool reference)
5. `TracingLifespanHook` — initialises OpenTelemetry exporters
6. `AdminLifespanHook` — mounts SQLAdmin; requires the engine to already exist

Projects that do not use Redis (minimal preset, database-only) omit step 2 entirely. The ordering
constraint on DatabaseLifespanHook is unconditional; the Redis step is conditional.

**I11 connectivity check:** `FastAPIRedis(app).lifespan()` performs the startup Redis connectivity
check (ping + timeout). `AuthLifespanHook` no longer manages a Redis pool and no longer owns the I11
check.

Any hook that reads `db_module._engine` or calls `get_async_session()` at startup will raise
`RuntimeError` if registered before `DatabaseLifespanHook`. The generated `{{project_name}}/app.py`
template must enforce this order. Agents must BLOCK any template or code change that violates it.

**`install_app()` ordering contract:** All `install_app()` calls must complete before the lifespan
sequence begins (i.e., before `__aenter__` is called on the first hook). `AdminLifespanHook`
collects admin views from previously-installed modules — calling `install_app()` after lifespan
start results in views not appearing in the admin panel.
```

---

## ADR-038 — Phase 5 Protocol Signatures: StorageProtocol, VectorStoreProtocol, EmbeddingProtocol

**Phase:** 5

**Context:** ARCHITECTURE.md listed only method names for Phase 5 backend families — no parameter types or return types. Without full signatures, I1 (Full Protocol Conformance) cannot be enforced.

**Decision:** Define complete typed signatures for all three protocols. Key choices:
- `StorageProtocol.upload(key: str, data: bytes, *, content_type: str) -> str` — takes `bytes` not `IO[bytes]`
- `VectorStoreProtocol.search(collection, vector: list[float], *, top_k, filter) -> list[VectorSearchResult]` — takes pre-computed vector, not text
- `EmbeddingProtocol.embed(text: str) -> list[float]` — returns `list[float]` not `numpy.ndarray`
- Metadata constrained to `dict[str, str | int | float | bool]` (intersection of all backend capabilities)
- `VectorSearchResult` dataclass: `id`, `score`, `metadata`, `content`

**Consequences:**
- I1 conformance enforceable across all implementations
- `VectorSearchResult` exported from `core/vector/__init__.py`
- `KeyNotFoundError` from `core/storage/__init__.py`, `CollectionNotFoundError` from `core/vector/__init__.py`
- Full signatures documented in ARCHITECTURE.md Protocol methods table

See `spec/adr/ADR-038.md` for complete Protocol definitions.

---

## ADR-039 — Embedding-Local Backend: fastembed

**Phase:** 5

**Context:** ARCHITECTURE.md claimed `embedding-local` uses "no extra deps" — this is incorrect. A real local embedding model requires a library.

**Decision:** `embedding-local` extras installs `fastembed>=0.8` (ONNX Runtime, ~50MB, CPU-first). Default model: `BAAI/bge-small-en-v1.5` (384 dimensions, ~33MB download). Sync inference wrapped in `run_in_executor` for I2 compliance. Settings: `embedding_model`, `embedding_cache_dir`.

**Consequences:**
- ARCHITECTURE.md extras table corrected
- ~50MB install vs ~2GB for sentence-transformers
- Rules out sentence-transformers (too heavy) and stubs (useless)
- GPU via `fastembed-gpu` available but not in framework extras

See `spec/adr/ADR-039.md` for full rationale.

---

## ADR-040 — RagService API and Composition Model

**Phase:** 5

**Context:** ARCHITECTURE.md Module 11 listed RAG as a "Composable retrieval service" with no API, protocol, or composition model defined.

**Decision:** `RagService` is a concrete service (not a Protocol). Takes `EmbeddingProtocol` + `VectorStoreProtocol` at construction via DI. Public API:
- `ingest(collection, content, *, document_id, metadata) -> IngestResult`
- `ingest_file(collection, data, *, filename, content_type, document_id, metadata) -> IngestResult`
- `retrieve(collection, query, *, top_k, filter) -> list[RagChunk]`
- `delete_document(collection, document_id) -> int`

Chunking strategies: `fixed` (default, 512 tokens / 64 overlap) and `paragraph`. Chunk IDs: `{document_id}:{chunk_index}`. `ExtractionProtocol` defined for file → text conversion.

**Consequences:**
- Not pluggable via ADR-012 (variability is in the backends, not the orchestrator)
- Users needing different RAG patterns compose directly from EmbeddingProtocol + VectorStoreProtocol
- Settings: `rag_chunk_size`, `rag_chunk_overlap`, `rag_chunking_strategy`

See `spec/adr/ADR-040.md` for complete API definitions.

---

## ADR-041 — EmailProtocol Interface

**Phase:** 6

**Context:** ADR-018 defined email delivery via aiosmtplib with a custom backend dotted-path escape hatch, but never defined an `EmailProtocol`. I1 explicitly noted this as a known gap.

**Decision:** Define `EmailProtocol` with a single method:

```python
class EmailProtocol(Protocol):
    async def send(
        self, *, to: str, subject: str, body_text: str, body_html: str | None = None
    ) -> None: ...
```

Built-in: `SmtpEmailBackend` (extras-gated: `email-smtp`). Factory: `get_email_backend(settings)`. Exception: `EmailDeliveryError`. Module location: `core/email/` (not under `core/auth/` — email is a general-purpose service).

Fire-and-forget at the route level: delivery failures are logged and swallowed (prevents email enumeration attacks). No batch sending, no attachments at protocol level.

**Consequences:**
- Resolves I1 known gap
- I1 `Applies to` section amended to include `core/email/`
- Auth verification routes use `get_email_backend(settings).send(...)` for token delivery
- Custom backends (SES, SendGrid) via ADR-012 dotted-path: `email_backend = "myproject.email.SESBackend"`

See `spec/adr/ADR-041.md` for full interface definition.

---

## ADR-042 — UsageService.get_usage() Query API

**Phase:** 6

**Context:** ADR-035 promises `get_usage(user_id, period)` in Phase 6 but defines no signature or return type.

**Decision:** Two query methods on `UsageService`:

```python
async def get_usage(
    self, *, user_id=None, api_key_id=None, agent_name=None,
    period_start=None, period_end=None, db: AsyncSession,
) -> UsageSummary | None: ...

async def get_usage_by_model(
    self, *, user_id=None, api_key_id=None, agent_name=None,
    period_start=None, period_end=None, db: AsyncSession,
) -> list[UsageByModel]: ...
```

`UsageSummary`: `total_tokens`, `prompt_tokens`, `completion_tokens`, `total_cost_microcents`, `request_count`, `period_start`, `period_end`.

`UsageByModel`: per-model breakdown with the same fields plus `model: str`.

Filters are ANDed. At least one filter required (prevents full-table scans). Default period: last 24h. Returns `None` when no rows match (distinguishes "no activity" from "activity with zero tokens"). I21 does NOT apply to reads — exceptions propagate normally.

**Consequences:**
- `UsageSummary` and `UsageByModel` exported from `fast_agent_stack.core.ai.usage`
- Budget enforcement is user-code: call `get_usage()`, compare, reject if over
- Single SQL aggregate query per call — efficient with existing `created_at` index

See `spec/adr/ADR-042.md` for full API definition.

---

## ADR-043 — Integration Test Strategy: Two-Tier Scaffolder Verification

**Phase:** 9

**Context:** Template errors are silent — Copier produces broken projects with no error. Unit tests mock everything and can't catch these.

**Decision:** Two test tiers:

- **Tier 1 (every PR, ~10s, no Docker):** Scaffold each preset → `py_compile` all generated `.py` files → verify `pyproject.toml` parseable → `pip install -e .` → app module imports without error.
- **Tier 2 (release gate, ~60s, Docker):** Testcontainers (Postgres + Redis) → scaffold → `fas migrate` → start app → hit endpoints → verify responses.

Tier 2 uses `testcontainers[postgres,redis]>=4.0` in dev deps. Not a hard block on PRs — only on releases.

**Consequences:**
- Template regressions caught every PR (no Docker needed)
- Integration bugs caught before release (Docker required)
- New presets/copier questions must add assertions to both tiers
- CI: `ci.yml` runs Tier 1; `e2e.yml` runs Tier 2 on tag push / nightly / manual dispatch

See `spec/adr/ADR-043.md` for full CI config and test layout.

---

## ADR-044 — Alembic Branches for Framework Migrations

**Phase:** Post-release fix (supersedes I16 migration architecture)

**Context:** The current multi-instance migration system (separate env.py per module, shared version table) has a correctness bug: when auth migrations stamp their revision, the AI migration instance can't find it in its own script directory. Additionally, cross-module dependencies (AI depends on auth tables) cannot be expressed.

**Decision:** Replace with Alembic branches. One Alembic instance, multiple `version_locations` discovered dynamically at runtime via gate-on-importability. Framework migrations declare `branch_labels` and optional `depends_on`. `fas migrate` becomes `command.upgrade(cfg, "heads")`.

Key changes:
- Delete `core/auth/migrations/env.py` and `core/ai/migrations/env.py`
- Delete `_run_framework_migrations()` from `cli/db.py`
- Generated `alembic/env.py.jinja` discovers framework version locations dynamically
- Single `alembic_version` table (standard Alembic default) replaces `fas_alembic_version`
- Framework migrations gain `branch_labels` and `depends_on` declarations

**Consequences:**
- I16 amended: framework migrations are branches, not separate instances
- Cross-module dependencies expressible via `depends_on`
- `alembic history` shows full graph; `alembic downgrade` works correctly
- Gate-on-importability preserved (version dirs only added if gate package importable)

See `spec/adr/ADR-044.md` for full architecture.

---

## ADR-045 — RerankerProtocol: Post-Retrieval Reranking

**Phase:** 10 (tutorial prerequisite)  
**Amends:** ADR-040

**Context:** ADR-040 deferred reranking. Production RAG pipelines universally include reranking between retrieval and generation. The tutorial needs it to demonstrate best-practice agentic RAG.

**Decision:** Add `RerankerProtocol` with a single method: `rerank(query, documents, top_k) -> list[RerankResult]`. Two built-in backends: Ollama cross-encoder and OpenAI-compatible (covers Jina, Cohere via proxy). `RagService` gains optional `reranker` parameter; when provided, retrieve over-fetches then reranks.

Settings: `reranker_provider`, `reranker_model`, `reranker_url`, `reranker_timeout`.

**Consequences:**
- Backwards compatible (reranker is optional, defaults to None)
- New extras: `reranker-ollama`, `reranker-openai`
- Module: `core/ai/reranker/`
- I1, I22, I3 all apply

See `spec/adr/ADR-045.md` for full protocol definition.

---

## ADR-046 — Agent Tool Calling

**Phase:** 10 (tutorial prerequisite)  
**Amends:** Phase 4c agent lifecycle

**Context:** The current `@app.agent()` handler has no mechanism for tool use. Agentic behavior (decide to search, call tool, feed results back to LLM) requires a tool-call loop.

**Decision:**
- `@tool` decorator: defines tools from async functions, auto-generates OpenAI-compatible schemas from signatures
- `agent_loop(backend, messages, tools, max_iterations)`: dispatch loop that handles LLM -> tool call -> result -> LLM cycles
- `ToolCallResult` / `ToolCall` dataclasses for LLM responses requesting tool invocation
- `LLMBackend.complete()` and `.stream()` gain optional `tools` kwarg (backwards compatible)
- `Message` dataclass gains optional `tool_call_id` and `tool_calls` fields

Module: `core/ai/tools/`. All four LLM backends updated to handle tools parameter.

**Consequences:**
- Lightweight built-in tool loop (no LangChain/external dependency)
- `max_iterations` safety cap prevents infinite loops
- Backwards compatible (tools=None = existing behavior)
- Tutorial Part 5 uses this for agentic document Q&A

See `spec/adr/ADR-046.md` for full protocol and module design.