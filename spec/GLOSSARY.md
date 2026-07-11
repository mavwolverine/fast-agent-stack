# Glossary

**Auth backend chain** — the private internal object produced by `get_auth_backend()` when
`auth_backends` contains more than one entry (ADR-034). It is not exported and has no public
name. Delegation rules: `authenticate` and `verify_token` return the first non-`None` result
across backends in order; `create_token` and `refresh_token` delegate to the primary (first)
backend only; `revoke_token` runs on all backends so every authentication path is invalidated on
logout (I20). Single-entry lists return the backend directly with no wrapper.

**Backend family** — a category of pluggable service with a shared Protocol/ABC. The four families are: LLM provider, vector store, embedding, and storage. Each family has multiple implementations shipped as extras.

**CompletionResult** — a frozen dataclass defined in `core/ai/llm/__init__.py` that carries the
output of a single LLM call: `content: str`, `model: str`, `prompt_tokens: int`,
`completion_tokens: int`, `total_tokens: int`, and `cost: float | None`. Returned directly by
`LLMBackend.complete()`. Also emitted as the final (sentinel) item by `LLMBackend.stream()`,
in which case `content` is `""` and the token counts reflect the full streaming call. The SSE
streaming helper (`stream_sse`) intercepts the sentinel and passes it to `UsageService.log_usage()`
without writing it to the SSE response. See ADR-036.

**ConversationLog** — the SQLAlchemy model (defined in `core/ai/conversation.py`) that persists a
conversation thread and its messages. Stores metadata such as `agent_name`, `user_id`,
`conversation_id`, and timestamps. Referenced by `token_usage_log.conversation_id` for
thread-level usage attribution (ADR-035).

**Custom backend** — a user-supplied backend implementation that lives in the user's project (not in the fastagentstack package). Registered by setting the relevant settings field to a dotted Python path (e.g., `"myproject.backends.AzureStorage"`). Must fully implement the family's Protocol. See ADR-012.

**EmbeddingProtocol** — the Protocol for embedding backends (ADR-038). Methods: `embed(text) -> list[float]`, `embed_batch(texts) -> list[list[float]]`, `dimensions` (property). Returns `list[float]` (not numpy). Built-in implementations: Bedrock, OpenAI, local (fastembed). See ADR-039 for the local backend.

**EmailDeliveryError** — exception raised by `EmailProtocol.send()` when delivery fails (ADR-041). Auth routes catch this, log it, and return success to the user (fire-and-forget; prevents email enumeration).

**EmailProtocol** — the Protocol for email delivery backends (ADR-041). Single method: `send(*, to, subject, body_text, body_html) -> None`. Built-in: `SmtpEmailBackend` (aiosmtplib). Custom backends via ADR-012 dotted-path in `email_backend` setting. Located in `core/email/`.

**ExtractionProtocol** — the Protocol for document text extraction (ADR-040). Single method: `extract(data: bytes) -> str`. Built-in implementations: PDF (pdfplumber), DOCX (python-docx), XLSX (openpyxl), EML (stdlib). Each is extras-gated (I3).

**Extras gate** — a guard around an optional import that raises a clear error pointing to the correct install command:
```python
try:
    import qdrant_client
except ImportError:
    raise ImportError("pip install fast-agent-stack[vector-qdrant]")
```

**Factory function** — a `get_<service>()` function that reads settings and returns the configured backend instance. Each backend family has one factory. Users never instantiate backends directly.

**Installed apps** — two distinct mechanisms for registering app modules with FastAgentStack:
- `INSTALLED_APPS` string list in settings (e.g. `"apps.chat.routes"`) — imports the module and
  includes its `router: APIRouter` attribute. Router only; models and admin views are not
  auto-discovered via this path.
- `app.install_app(module: AppModule)` — uses the full `AppModule` Protocol: `get_router()`,
  `get_models()`, and `get_admin_views()`. Admin views collected via this path are automatically
  registered by `AdminLifespanHook`.

Use the string form for simple route modules. Use `install_app()` for full app modules that also
contribute models and admin views. See `spec/ARCHITECTURE.md` Module 1.

**Invariant** — a non-negotiable rule defined in `spec/INVARIANTS.md`. No implementation may violate an invariant; agents treat any violation as a BLOCK.

**Lifespan hook** — a class implementing `async __aenter__` / `async __aexit__` that is registered with FastAgentStack's lifespan. Used to open and close database connections, broker connections, etc. on startup/shutdown.

**Preset** — a named set of copier answers that bypasses the interactive CLI. Defined in `spec/SCAFFOLDER.md`. Current presets: `minimal`, `standard`, `full`, `agent`.

**Protocol/ABC** — the abstract interface all backends of a family must fully implement. Defined in code; documented in `spec/ARCHITECTURE.md`. Partial implementation is forbidden (see Invariant I1).

**RagChunk** — a frozen dataclass returned by `RagService.retrieve()` (ADR-040). Fields: `content: str`, `score: float`, `metadata: dict`, `document_id: str | None`, `chunk_index: int`. Represents a single retrieved chunk with relevance score and source traceability.

**RagService** — the concrete RAG orchestration service (ADR-040) in `core/ai/rag/`. Takes `EmbeddingProtocol` + `VectorStoreProtocol` at construction and an optional `RerankerProtocol`. Not a Protocol — not pluggable via ADR-012. Public API: `ingest()`, `ingest_file()`, `retrieve()`, `delete_document()`. When a reranker is provided, `retrieve()` over-fetches then reranks before returning results (ADR-045).

**RerankerProtocol** — the Protocol for post-retrieval reranking backends (ADR-045). Single async method: `rerank(query, documents, *, top_k) -> list[RerankResult]`. Built-in implementations: `OllamaReranker` (`reranker-ollama` extra), `OpenAIReranker` (`reranker-openai` extra, compatible with Jina and Cohere endpoints). Custom backends supported via ADR-012 dotted path in `reranker_provider` setting. Located in `core/ai/reranker/`.

**RerankResult** — a frozen dataclass returned by `RerankerProtocol.rerank()` (ADR-045). Fields: `content: str`, `score: float`, `index: int`. `index` is the original position of the document in the input list, enabling traceability back to the source retrieval results. Results are ordered by `score` descending (highest relevance first).

**StorageProtocol** — the Protocol for object storage backends (ADR-038). Methods: `upload`, `download`, `delete`, `exists`, `url`. Built-in implementations: S3, local filesystem, MinIO. Takes `bytes` input (not streams); returns pre-signed URLs for remote backends.

**VectorSearchResult** — a frozen dataclass returned by `VectorStoreProtocol.search()` (ADR-038). Fields: `id: str`, `score: float`, `metadata: dict[str, str|int|float|bool]`, `content: str | None`. Defined in `core/vector/__init__.py`.

**VectorStoreProtocol** — the Protocol for vector store backends (ADR-038). Methods: `create_collection`, `upsert`, `search`, `delete`, `close`. Search takes a pre-computed `vector: list[float]`, not a text query (embedding is a separate concern). Built-in implementations: Qdrant, pgvector, OpenSearch, Weaviate.

**Escape hatch** — direct access to the underlying third-party object (e.g., `app.fastapi_app`, the raw SQLAlchemy engine). Every wrapped component must expose one.

**Group** — a named collection of users that share permissions. Equivalent to Django's Group and AWS IAM Group. Users can belong to multiple groups. Permissions are assigned to groups via the `group_permissions` join table. See ADR-028.

**Permission** — a `(resource, action)` pair granting the ability to perform an operation (e.g., `"posts"`, `"delete"`). Assigned to groups or directly to users. See ADR-028.

**RBAC (Role-Based Access Control)** — the authorization model used by the framework. Users gain permissions through group membership (`user_groups` → `group_permissions`) or direct grants (`user_permissions`). `is_superuser` bypasses all permission checks. See ADR-028.

**UsageService** — the framework service (injected as a FastAPI dependency or called directly from
`stream_sse`) responsible for writing token usage records to `token_usage_log`. Exposes
`log_usage(result: CompletionResult, *, user_id, api_key_id, agent_name, conversation_id)`
and `get_usage(*, user_id, api_key_id, agent_name, period_start, period_end, db) -> UsageSummary | None`.
Write failures in `log_usage()` must be caught, logged, and swallowed — they must never propagate
to the LLM caller (I21). Read failures in `get_usage()` propagate normally. See ADR-035, ADR-036,
and ADR-042.

**UsageSummary** — frozen dataclass returned by `UsageService.get_usage()` (ADR-042). Fields:
`total_tokens`, `prompt_tokens`, `completion_tokens`, `total_cost_microcents`, `request_count`,
`period_start`, `period_end`. Represents aggregated token usage for a filtered time period.

**UsageByModel** — frozen dataclass returned by `UsageService.get_usage_by_model()` (ADR-042).
Same fields as `UsageSummary` plus `model: str`. One entry per model with activity in the period.

**copier.yml** — the Copier question definition file that drives interactive project generation. Variable names defined here are the only valid names for template conditionals.

**Deprecation cycle** — the process for removing or changing a public API surface covered by I6.
A deprecated symbol must emit a `DeprecationWarning` for at least one minor version before removal.
The warning message must name the replacement (if any) and the version in which removal will occur.
Removal may only happen in the next minor version after the warning was introduced (e.g., deprecated
in 0.5.0, removable in 0.6.0). CLI commands follow the same policy: `--help` output notes the
deprecation and the replacement command.
