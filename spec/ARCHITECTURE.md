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
- Pluggable auth backends via `auth_backends: list[str]` in settings (ADR-034). Each entry is a
  built-in alias (`"jwt"`, `"session"`) or a dotted Python path to a custom `AuthBackend`
  implementation. `get_auth_backend()` wraps all configured backends in a private internal chain:
  - `authenticate` / `verify_token` — first non-`None` result wins (backends tried in order)
  - `create_token` / `refresh_token` — primary (first) backend only
  - `revoke_token` — runs on ALL backends (logout must invalidate every auth path; see I20)
  Single-backend deployments pass a list of one entry and incur no chain overhead.
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
- Admin login authenticates against the user table (`is_staff` or `is_superuser` required); shared-secret login removed (ADR-049)
- `fas createsuperuser` is the single entry point for both API (`/auth/token`) and admin panel (`/admin`) access
- `AdminLifespanHook(app, secret_key=_settings.secret_key)` — `secret_key` signs the session cookie only, not used as a credential

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

- `LLMBackend` Protocol with `complete()` and `stream()` methods (ADR-021, amended by ADR-036, ADR-046)
- Direct SDK backends: Bedrock (`aioboto3`), OpenAI (`openai`), Anthropic (`anthropic`)
- LiteLLM backend for users who prefer a unified proxy (ADR-012 dotted-path registration)
- Each backend is an optional extra: `fast-agent-stack[bedrock]`, `[openai]`, `[anthropic]`, `[litellm]`
- Token usage metering middleware (ADR-035, ADR-036)
- **Future (post-Phase 4):** model routing, fallback on error, A/B testing

#### Result types (defined in `core/ai/llm/__init__.py`)

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class CompletionResult:
    content: str          # generated text; empty string ("") for the streaming sentinel
    model: str            # model identifier used for the call
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None    # None when the backend cannot compute cost (e.g., self-hosted)

@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass(frozen=True)
class ToolCallResult:
    """Returned by LLMBackend when the model requests tool invocation instead of text."""
    tool_calls: list[ToolCall]
```

#### Message type (defined in `core/ai/llm/__init__.py`)

```python
@dataclass(frozen=True)
class Message:
    role: str                            # "user" | "assistant" | "system" | "tool"
    content: str
    tool_call_id: str | None = None      # for role="tool" responses
    tool_calls: list[ToolCall] | None = None  # for role="assistant" with tool use
```

#### LLMBackend Protocol (post-ADR-036, amended by ADR-046)

```python
class LLMBackend(Protocol):
    @property
    def model_id(self) -> str: ...

    async def complete(
        self, messages: list[Message], *, tools: list[dict] | None = None, **kwargs
    ) -> CompletionResult | ToolCallResult: ...

    async def stream(
        self, messages: list[Message], *, tools: list[dict] | None = None, **kwargs
    ) -> AsyncIterator[str | CompletionResult | ToolCallResult]: ...

    async def count_tokens(self, messages: list[Message]) -> int: ...
```

When `tools` is `None`, backends behave as before (backwards compatible). When `tools` is provided, backends pass the tool schemas to the LLM and return `ToolCallResult` if the model requests a tool invocation.

#### Streaming sentinel contract

`stream()` is an async generator that:
1. Yields zero or more `str` items — the content chunks sent to the caller via SSE.
2. Yields exactly one `CompletionResult` as its **final** item — the sentinel with `content=""`
   and full token counts for the call. No `str` chunks may follow the sentinel.
3. **When tools are active:** may yield a `ToolCallResult` item instead of text chunks. The
   `agent_loop` in `core/ai/tools/` consumes this and re-invokes the backend; `stream_sse` never
   sees `ToolCallResult` directly.

All built-in backend implementations (Bedrock, OpenAI, Anthropic, LiteLLM) must conform to this
contract. Custom backends (ADR-012) must also conform (I1). All four backends must handle the
optional `tools` kwarg (ADR-046, I1).

#### SSE streaming helper (`core/ai/streaming.py`)

The `stream_sse` helper in `core/ai/streaming.py` is the sole consumer of `backend.stream(...)`.
It is responsible for:
- Writing each `str` chunk as an SSE `data:` event to the HTTP response.
- Intercepting the trailing `CompletionResult` item — it is **not** written to SSE.
- Passing the intercepted `CompletionResult` to `UsageService.log_usage()`.
- Catching and swallowing any exception raised by `UsageService.log_usage()` — write failures
  must not abort or delay the streaming response (I21).

### 10. Agent Lifecycle

- Agent registration via `@app.agent(name, backend, tools=[...])` decorator (ADR-046)
- Agent handlers may be `async def` coroutines or async generator functions. The framework detects
  the handler form at dispatch time using `inspect.isasyncgenfunction` and routes accordingly:

  **Non-streaming handler** (`async def handler(...) -> str`):
  - Called; the returned `str` is passed to `backend.complete(...)`.
  - The returned `CompletionResult` is logged via `UsageService.log_usage()`.
  - Response is a standard JSON body.

  **Streaming handler** (`async def handler(...) -> AsyncIterator[str]`, declared as async generator):
  - Iterated; each `str` chunk is emitted as an SSE `data:` event via `stream_sse`.
  - The trailing `CompletionResult` sentinel from `backend.stream(...)` is intercepted by
    `stream_sse` and passed to `UsageService.log_usage()` (I21 applies).
  - Response is a `text/event-stream` SSE response.

- **Tool use (ADR-046):** Tools are plain async functions decorated with `@tool(description=...)`.
  The decorator extracts the function signature and generates an OpenAI-compatible tool schema.
  `agent_loop(backend, messages, tools, max_iterations)` handles the LLM → tool call → result → LLM
  cycle. Handlers that need agentic behavior delegate to `agent_loop` rather than calling the
  backend directly. `max_iterations` (default 10) caps the loop to prevent runaway tool chains (I23).
- Conversation/thread persistence (built-in `ConversationLog` model)
- Session management (Valkey/Redis)
- Streaming response helpers (SSE wired into auth/middleware stack)

### 11. RAG Pipeline
- Composable retrieval service (`RagService` — concrete, not a Protocol; ADR-040)
- Pluggable vector store backends: Qdrant, pgvector, OpenSearch, Weaviate (ADR-038 signatures)
- Pluggable embedding backends: Bedrock, OpenAI, local/fastembed (ADR-038, ADR-039)
- Optional reranking backends: Ollama cross-encoder (`reranker-ollama`), OpenAI-compatible (`reranker-openai`) (ADR-045)
- Document extraction: PDF (`extract-pdf`), DOCX (`extract-docx`), XLSX (`extract-xlsx`), EML (stdlib `email` module — no extra required)
- Chunking strategies: `fixed` (default, ~512 tokens with 64-token overlap) and `paragraph`
- RagService takes `EmbeddingProtocol` + `VectorStoreProtocol` at construction, and optional `RerankerProtocol` (DI, not factory calls)
- Public API: `ingest()`, `ingest_file()`, `retrieve()`, `delete_document()`
- Chunk IDs: `{document_id}:{chunk_index}` (deterministic, enables idempotent re-ingestion)
- Returns `RagChunk` dataclass (content, score, metadata, document_id, chunk_index)
- When reranker is set, `retrieve()` over-fetches (`top_k * 3`) then reranks to return top `top_k` (ADR-045)

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
| `auth-jwt` | `pwdlib[argon2]>=0.3`, `pyjwt[crypto]>=2.8`, `fastapi-redis-sdk>=0.7` | ADR-015, ADR-029, ADR-030, ADR-037 |
| `auth-session` | `pwdlib[argon2]>=0.3`, `fastapi-redis-sdk>=0.7` | ADR-015, ADR-030, ADR-037 |
| `admin` | `sqladmin>=0.16` | ADR-007 |
| `bedrock` | `aioboto3>=12` | ADR-021 |
| `openai` | `openai>=1.0` | ADR-021 |
| `anthropic` | `anthropic>=0.25` | ADR-021 |
| `litellm` | `litellm>=1.30` | ADR-021 |
| `vector-qdrant` | `qdrant-client>=1.7` | ADR-038 |
| `vector-pgvector` | `pgvector>=0.2` | ADR-038 |
| `vector-opensearch` | `opensearch-py[async]>=2.3` | ADR-038 |
| `vector-weaviate` | `weaviate-client>=4` | ADR-038 |
| `embedding-bedrock` | `aioboto3>=12` | ADR-038 |
| `embedding-openai` | `openai>=1.0` | ADR-038 |
| `embedding-local` | `fastembed>=0.8` | ADR-038, ADR-039 |
| `storage-s3` | `aioboto3>=12` | ADR-038 |
| `storage-local` | `aiofiles>=23` | ADR-038 |
| `storage-minio` | `aioboto3>=12` | ADR-038 |
| `tasks` | `dramatiq[redis]>=1.15` | ADR-005, ADR-020 |
| `scheduler` | `periodiq>=0.9` | ADR-005 |
| `rate-limit` | `fastapi-redis-sdk>=0.7` | ADR-016, ADR-037 |
| `email-smtp` | `aiosmtplib>=3` | ADR-018 |
| `extract-pdf` | `pymupdf>=1.24` | ADR-040 |
| `extract-docx` | `python-docx>=1.1` | ADR-040 |
| `extract-xlsx` | `openpyxl>=3.1` | ADR-040 |
| `secrets-aws` | `boto3>=1.34` | ADR-017 |
| `secrets-gcp` | `google-cloud-secret-manager>=2.20` | ADR-017 |
| `tracing` | `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` | ADR-009 |
| `reranker-ollama` | `httpx>=0.27` | ADR-045 |
| `reranker-openai` | `httpx>=0.27` | ADR-045 |

Bundle extras: `ai-full` (all AI backends + vector + storage + embedding + reranking), `all` (everything).

**Note on `db-*` extras:** These groups contain only the async engine driver for the chosen database. `sqlalchemy[asyncio]` and `alembic` are in `project.dependencies` (core, always installed) per ADR-025. I3 (extras gate) applies to the async drivers in `db-*` extras; it does not apply to SQLAlchemy or Alembic imports.

## Custom Backends (Bring Your Own)

All five pluggable backend families — LLM provider, vector store, embedding, storage, reranker — support user-supplied implementations via a dotted Python path in settings. The factory checks: if the value is a known alias → use built-in; if it contains a `.` → import and instantiate the class.

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

    async def upload(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str: ...
    async def download(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def url(self, key: str, *, expires_in: int = 3600) -> str: ...
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

Same pattern applies to `get_vector_store()`, `get_llm()`, `get_embedding_provider()`, `get_reranker()`. All five factory functions accept a dotted Python path for custom backends (ADR-012). `get_reranker()` returns `None` when `reranker_provider = "none"` (ADR-045). LLM provider constructors receive `settings` (same contract as all other families).

### Auth backend factory (`get_auth_backend`)

`get_auth_backend(settings)` reads `settings.auth_backends: list[str]` and returns a single
`AuthBackend`-conforming object (ADR-034). For a list of one entry it returns the backend
directly with no wrapper. For two or more entries it wraps them in a private internal chain
(not exported, not a named public class). Each entry is resolved the same way as other backend
families: known alias → built-in class; contains `.` → `_import_dotted_path` (ADR-012).

```python
def get_auth_backend(settings) -> AuthBackend:
    backends = [_resolve_auth_backend(alias, settings) for alias in settings.auth_backends]
    if len(backends) == 1:
        return backends[0]
    return _AuthBackendChain(backends)
```

Chain delegation rules (see ADR-034):
- `authenticate` / `verify_token` — first non-`None` result wins
- `create_token` / `refresh_token` — first backend only
- `revoke_token` — all backends (I20)

### Protocol methods by family

| Family | Protocol | Required methods |
|---|---|---|
| Auth | `AuthBackend` | `authenticate`, `create_token`, `verify_token`, `revoke_token`, `refresh_token` |
| LLM | `LLMBackend` | `complete`, `stream`, `count_tokens`, `model_id` (property); optional `tools` kwarg on `complete`/`stream` (ADR-046) |
| Vector store | `VectorStoreProtocol` | `create_collection`, `upsert`, `search`, `delete`, `close` |
| Embedding | `EmbeddingProtocol` | `embed`, `embed_batch`, `dimensions` (property) |
| Storage | `StorageProtocol` | `upload`, `download`, `delete`, `exists`, `url` |
| Reranker | `RerankerProtocol` | `rerank` |

**LLM return types (ADR-036):** `complete()` returns `CompletionResult`. `stream()` returns
`AsyncIterator[str | CompletionResult]` where the final item is always a `CompletionResult`
sentinel (content="", full token counts). See Module 9 above for the full Protocol definition
and streaming sentinel contract.

**Phase 5 Protocol signatures (ADR-038):** Full typed signatures for Storage, Vector, and Embedding protocols:

| Protocol | Method | Signature |
|---|---|---|
| `StorageProtocol` | `upload` | `async def upload(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str` |
| | `download` | `async def download(self, key: str) -> bytes` |
| | `delete` | `async def delete(self, key: str) -> None` |
| | `exists` | `async def exists(self, key: str) -> bool` |
| | `url` | `async def url(self, key: str, *, expires_in: int = 3600) -> str` |
| `VectorStoreProtocol` | `create_collection` | `async def create_collection(self, name: str, dimensions: int, *, distance_metric: str = "cosine") -> None` |
| | `upsert` | `async def upsert(self, collection: str, id: str, vector: list[float], metadata: dict[str, str\|int\|float\|bool], *, content: str\|None = None) -> None` |
| | `search` | `async def search(self, collection: str, vector: list[float], *, top_k: int = 10, filter: dict[...]\|None = None) -> list[VectorSearchResult]` |
| | `delete` | `async def delete(self, collection: str, id: str) -> None` |
| | `close` | `async def close(self) -> None` |
| `EmbeddingProtocol` | `embed` | `async def embed(self, text: str) -> list[float]` |
| | `embed_batch` | `async def embed_batch(self, texts: list[str]) -> list[list[float]]` |
| | `dimensions` | `@property def dimensions(self) -> int` |

`VectorSearchResult` (dataclass, `core/vector/__init__.py`): `id: str`, `score: float`, `metadata: dict[str, str|int|float|bool]`, `content: str|None`.

`search()` takes a pre-computed `vector: list[float]`, not a text query. Embedding is a separate concern. Metadata is constrained to `dict[str, str|int|float|bool]` (intersection of all four backends). See ADR-038 for full design rationale.

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
    │   ├── backends/         # jwt.py, session.py, factory.py (no combined.py — see ADR-034)
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
    │   ├── llm/              # LLMBackend Protocol, CompletionResult, ToolCall, ToolCallResult, Message
    │   ├── tools/            # @tool decorator, agent_loop, Tool class (ADR-046)
    │   ├── embedding/        # Embedding backends (bedrock, openai, local)
    │   ├── rag/              # RagService, chunking
    │   ├── reranker/         # RerankerProtocol, RerankResult, OllamaReranker, OpenAIReranker (ADR-045)
    │   ├── extraction/       # PDF, DOCX, XLSX extractors (extras); EML (stdlib)
    │   ├── agents.py         # @app.agent registry + /agents/{name} router
    │   ├── conversation.py   # ConversationLog + ConversationMessage models
    │   └── streaming.py      # stream_sse (splits str chunks → SSE, CompletionResult → UsageService)
    ├── storage/              # Storage backends (s3, local, minio)
    └── vector/               # Vector store backends (qdrant, pgvector, opensearch, weaviate)
```

## Frontend Serving

- Uses FastAPI's `app.frontend("./frontend/dist")` to serve a static SPA build
- API routes take priority; frontend files are served only when no path operation matches
- SPA fallback routing handled automatically (client-side routing works)
- Optional — only generated when `include_frontend` is enabled in scaffolder
- Separate from SQLAdmin (admin = server-rendered model CRUD; frontend = user-facing app)
