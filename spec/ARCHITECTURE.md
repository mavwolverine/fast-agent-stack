# Architecture

## Core Modules

### 1. App Factory & Conventions
- Opinionated FastAPI app setup (CORS, error handling, health checks, lifespan)
- **Two app module registration paths** — these are distinct mechanisms with different capabilities:
  - `INSTALLED_APPS` string list (e.g. `"apps.chat.routes"`) — imports the module and includes
    its `router: APIRouter` attribute. Router-only; models and admin views are NOT auto-discovered
    via this path.
  - `app.install_app(module: AppModule)` — calls the `AppModule` Protocol: `get_router()`,
    `get_models()`, and `get_admin_views()`. Full discovery; `AdminLifespanHook` collects admin
    views only from modules registered this way.
- Use `INSTALLED_APPS` for simple route modules. Use `install_app()` for full app modules that
  also contribute models and admin views.

### 2. Settings & Configuration
- Built on pydantic-settings
- Environment-based config with secrets backend support (AWS Secrets Manager, GCP Secret Manager, env files) — see ADR-017. HashiCorp Vault is out of scope.
- Single settings class users extend

### 3. Database & ORM
- SQLAlchemy async + Alembic preconfigured
- Base model with common fields (id, created_at, updated_at)
- Repository pattern (optional)
- CLI commands: `migrate`, `makemigrations`, `seed` (looks for `seeds.py` with a `run()` entry point)
- Session dependencies: `get_async_session` (standard) and `get_async_session_for_schema(schema)` (schema-per-tenant, satisfies I8)
- **Multi-tenancy note:** `get_async_session_for_schema(schema)` issues `SET search_path TO {schema}, public` and returns a FastAPI dependency. Schema name validated against `[a-zA-Z_][a-zA-Z0-9_]*` to prevent injection.

### 4. Authentication & User Management
- User model (hashed passwords, email, is_active, is_verified, is_staff, is_superuser)
- JWT + session-based auth (pluggable backends)
- Core auth routes: `POST /auth/token`, `POST /auth/refresh`, `POST /auth/logout` (ADR-015)
- API key management: `POST /api-keys`, `GET /api-keys`, `DELETE /api-keys/{id}`, `POST /api-keys/{id}/revoke` (S8)
- Permissions and groups
- Password reset flow: `POST /auth/forgot-password` → `POST /auth/reset-password`
- Email verification flow: `POST /auth/send-verification` → `POST /auth/verify-email`
- Tokens stored in `auth_verification_token` table (TTL: 24h reset, 72h verification)
- Email delivery via `aiosmtplib` (async SMTP) — requires `fast-agent-stack[email-smtp]`; custom backend via dotted path in `email_backend` setting (ADR-018)
- `createsuperuser` CLI command

### 5. Admin Console
- SQLAdmin integration, auto-registered from models
- User activity and model usage monitoring

### 6. Background Tasks & Scheduling
- Dramatiq integration with Redis/Valkey broker
- periodiq for cron-style periodic tasks
- CLI: `worker`, `scheduler` commands

### 7. Observability
- Jaeger tracing auto-instrumented via OpenTelemetry
- Structured logging
- Health check endpoints (liveness, readiness)

### 8. CLI
- Built on Typer
- Commands: `new`, `dev`, `run`, `migrate`, `makemigrations`, `createsuperuser`, `seed`, `update`, `worker`, `scheduler`, `version`
- Plugin system for custom commands

## AI-Specific Modules

### 9. LLM Provider Abstraction
- `LLMBackend` protocol with `complete()` and `stream()` methods
- Direct SDK backends: Bedrock (`boto3`), OpenAI (`openai`), Anthropic (`anthropic`)
- LiteLLM backend for users who prefer a unified proxy (ADR-012 dotted-path registration)
- Each backend is an optional extra: `fast-agent-stack[bedrock]`, `[openai]`, `[anthropic]`, `[litellm]`
- Token usage metering middleware
- **Future (post-Phase 4):** model routing, fallback on error, A/B testing

### 10. Agent Lifecycle
- Agent registration via `@app.agent(name, model)` decorator
- Agent handlers may be `async def` coroutines returning `str | AsyncIterator[str]`, or async
  generator functions that `yield` string chunks. The framework detects the form at dispatch time
  (`inspect.isasyncgenfunction`) and routes non-streaming results to JSON and streaming results
  to SSE automatically.
- Conversation/thread persistence (built-in model)
- Session management (Valkey/Redis)
- Streaming response helpers (SSE wired into auth/middleware stack)

### 11. RAG Pipeline
- Composable retrieval service
- Pluggable vector store backends: Qdrant, pgvector, OpenSearch, Weaviate
- Pluggable embedding backends: Bedrock, OpenAI, local
- Document extraction: PDF (`extract-pdf`), DOCX (`extract-docx`), XLSX (`extract-xlsx`), EML (stdlib `email` module — no extra required)
- Chunking strategies

### 12. Storage
- Pluggable backends: S3, local filesystem, MinIO
- File upload handling with hash deduplication

## Pluggable Backend Architecture

Inspired by Django's database backends. Each service type has:
- A Protocol/ABC defining the interface
- Multiple implementations shipped as extras
- Factory function that reads config and returns the right backend

### Extras Reference

| Extra | Key packages | ADR |
|---|---|---|
| `db-postgres` | `asyncpg>=0.29` (driver only — SQLAlchemy and Alembic are core) | ADR-002, ADR-025 |
| `db-sqlite` | `aiosqlite>=0.19` (driver only — SQLAlchemy and Alembic are core) | ADR-002, ADR-025 |
| `db-mysql` | `aiomysql>=0.2` (driver only — SQLAlchemy and Alembic are core) | ADR-002, ADR-025 |
| `auth-jwt` | `pwdlib[argon2]>=0.3`, `pyjwt[crypto]>=2.8`, `redis>=5` | ADR-015, ADR-029, ADR-030 |
| `auth-session` | `pwdlib[argon2]>=0.3`, `redis>=5` | ADR-015, ADR-030 |
| `admin` | `sqladmin>=0.16` | ADR-007 |
| `bedrock` | `aioboto3>=12` | ADR-021 |
| `openai` | `openai>=1.0` | ADR-021 |
| `anthropic` | `anthropic>=0.25` | ADR-021 |
| `litellm` | `litellm>=1.30` | ADR-021 |
| `vector-qdrant` | `qdrant-client>=1.7` | — |
| `vector-pgvector` | `pgvector>=0.2` | — |
| `vector-opensearch` | `opensearch-py[async]>=2.3` | — |
| `vector-weaviate` | `weaviate-client>=4` | — |
| `embedding-bedrock` | `aioboto3>=12` | — |
| `embedding-openai` | `openai>=1.0` | — |
| `embedding-local` | *(no extra deps — uses local model)* | — |
| `storage-s3` | `aioboto3>=12` | — |
| `storage-local` | `aiofiles>=23` | — |
| `storage-minio` | `aioboto3>=12` | — |
| `tasks` | `dramatiq[redis]>=1.15` | ADR-005, ADR-020 |
| `scheduler` | `periodiq>=0.9` | ADR-005 |
| `rate-limit` | `redis>=5` | ADR-016 |
| `email-smtp` | `aiosmtplib>=3` | ADR-018 |
| `extract-pdf` | `pdfplumber>=0.10` | — |
| `extract-docx` | `python-docx>=1.1` | — |
| `extract-xlsx` | `openpyxl>=3.1` | — |
| `secrets-aws` | `boto3>=1.34` | ADR-017 |
| `secrets-gcp` | `google-cloud-secret-manager>=2.20` | ADR-017 |
| `tracing` | `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-jaeger` | — |

Bundle extras: `ai-full` (all AI backends + vector + storage + embedding), `all` (everything).

**Note on `db-*` extras:** These groups contain only the async engine driver for the chosen database. `sqlalchemy[asyncio]` and `alembic` are in `project.dependencies` (core, always installed) per ADR-025. I3 (extras gate) applies to the async drivers in `db-*` extras; it does not apply to SQLAlchemy or Alembic imports.

## Custom Backends (Bring Your Own)

All four pluggable backend families — LLM provider, vector store, embedding, storage — support user-supplied implementations via a dotted Python path in settings. The factory checks: if the value is a known alias → use built-in; if it contains a `.` → import and instantiate the class.

```python
# settings.py
storage_backend: str = "myproject.backends.AzureStorage"
vector_db: str = "myproject.backends.PineconeStore"
llm_provider: str = "myproject.backends.PrivateLLM"
embedding_provider: str = "myproject.backends.CustomEmbedder"
```

The user's class receives the full `Settings` object at instantiation and must fully implement the family's Protocol (Invariant I1). No extras gate is needed — the user owns their own dependencies.

```python
# myproject/backends.py (user writes, lives in their project)
from fast_agent_stack.storage import StorageProtocol

class AzureStorage:
    def __init__(self, settings) -> None:
        self._client = BlobServiceClient(settings.azure_storage_url)

    async def upload(self, key: str, data: bytes) -> None: ...
    async def download(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def url(self, key: str) -> str: ...
```

### Factory dispatch logic (inside fastagentstack)

```python
def get_storage(settings) -> StorageProtocol:
    backend = settings.storage_backend
    match backend:
        case "s3":    return S3Storage(settings)
        case "local": return LocalStorage(settings)
        case "minio": return MinIOStorage(settings)
        case _:       return _import_dotted_path(backend)(settings)
```

Same pattern applies to `get_vector_store()`, `get_llm()`, `get_embedding_provider()`. All four factory functions accept a dotted Python path for custom backends (ADR-012). LLM provider constructors receive `settings` (same contract as all other families).

### Protocol methods by family

| Family | Protocol | Required methods |
|---|---|---|
| Auth | `AuthBackend` | `authenticate`, `create_token`, `verify_token`, `revoke_token`, `refresh_token` |
| LLM | `LLMBackend` | `complete`, `stream`, `count_tokens`, `model_id` (property) |
| Vector store | `VectorStoreProtocol` | `upsert`, `search`, `delete`, `create_collection`, `close` |
| Embedding | `EmbeddingProtocol` | `embed`, `embed_batch`, `dimensions` (property) |
| Storage | `StorageProtocol` | `upload`, `download`, `delete`, `exists`, `url` |

### Database

The database is **not** a pluggable backend family. SQLAlchemy is the ORM (ADR-002 — fixed choice). Users select a different database engine by changing `DATABASE_URL` to any SQLAlchemy-compatible connection string:

```
DATABASE_URL=postgresql+asyncpg://...    # postgres (default)
DATABASE_URL=mysql+aiomysql://...        # mysql
DATABASE_URL=sqlite+aiosqlite:///...     # sqlite
```

`sqlalchemy[asyncio]` and `alembic` are always installed as core dependencies — they are in `project.dependencies`, not in any extras group (ADR-025). Only the async engine driver for the chosen database needs to be added via a `db-*` extras group. Swapping the ORM itself (e.g., Tortoise, SQLModel) violates ADR-002 and is a `plan-guardian` BLOCK.

## Package Structure

### Convention: `lifespan.py` per subpackage

Every `core/` subpackage that needs startup/shutdown behaviour exports a `LifespanHook`
implementor from a `lifespan.py` module. This gives a consistent discovery pattern:

- `core/database/lifespan.py` → `DatabaseLifespanHook`
- `core/auth/lifespan.py` → `AuthLifespanHook`
- `core/ratelimit/lifespan.py` → `RateLimitLifespanHook`
- `core/observability/lifespan.py` → `TracingLifespanHook`
- `core/admin/lifespan.py` → `AdminLifespanHook`

Each hook implements the `LifespanHook` protocol (`__aenter__`/`__aexit__`). The generated app
template imports and registers them in the order defined by I9.

```
fast_agent_stack/
├── cli/
│   ├── main.py
│   ├── new.py
│   ├── run.py
│   ├── db.py
│   ├── auth.py
│   ├── worker.py
│   ├── scheduler_cmd.py
│   ├── seed.py
│   └── update.py
├── config/                  # Public re-export: fast_agent_stack.config.BaseSettings
├── database/                # Public re-export: fast_agent_stack.database.*
├── template/                # Copier template (Jinja2)
│   ├── copier.yml
│   └── {{project_name}}/
└── core/
    ├── app.py
    ├── config.py
    ├── database.py
    ├── middleware.py
    ├── protocols.py          # AppModule, LifespanHook
    ├── auth/
    │   ├── backends/         # jwt.py, session.py, combined.py, factory.py
    │   ├── migrations/       # 0001_fas_auth_initial.py, ...
    │   ├── models.py
    │   ├── tokens.py
    │   ├── routes.py
    │   ├── password.py
    │   ├── dependencies.py
    │   └── lifespan.py
    ├── admin/
    ├── tasks/
    ├── ratelimit/
    ├── observability/
    ├── ai/
    │   ├── llm/              # LLM provider abstraction + 4 built-in providers
    │   ├── embedding/        # Embedding backends (bedrock, openai, local)
    │   ├── rag/              # RagService, chunking
    │   ├── extraction/       # PDF, DOCX, XLSX extractors (extras); EML (stdlib)
    │   ├── agents.py         # @app.agent registry + /agents/{name} router
    │   ├── conversation.py   # Conversation + ConversationMessage models
    │   └── streaming.py      # stream_sse, stream_response
    ├── storage/              # Storage backends (s3, local, minio)
    └── vector/               # Vector store backends (qdrant, pgvector, opensearch, weaviate)
```

## Frontend Serving

- Uses FastAPI's `app.frontend("./frontend/dist")` to serve a static SPA build
- API routes take priority; frontend files are served only when no path operation matches
- SPA fallback routing handled automatically (client-side routing works)
- Optional — only generated when `include_frontend` is enabled in scaffolder
- Separate from SQLAdmin (admin = server-rendered model CRUD; frontend = user-facing app)
