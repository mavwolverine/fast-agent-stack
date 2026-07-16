# Scenarios

Concrete use cases that validate the framework design. Module briefs and implementation decisions must hold up against these scenarios.

---

## S1 — RAG Chatbot

**User goal:** Ship a document Q&A chatbot with auth, vector search, and streaming responses.

**Stack:** postgres + bedrock (LLM) + qdrant (vector) + bedrock (embedding) + jwt auth

**Flow:**
1. `fastagentstack new chatbot --preset agent`
2. Drop PDFs into storage; extraction pipeline chunks and embeds them into Qdrant
3. User authenticates via JWT; sends a message
4. Agent retrieves top-k chunks from Qdrant, calls Bedrock, streams response via SSE
5. Conversation thread persisted to postgres

**What this validates:**
- LLM provider abstraction (streaming + token metering via `CompletionResult` sentinel — ADR-036)
- `stream_sse` helper correctly separates `str` chunks (→ SSE) from the trailing `CompletionResult`
  (→ `UsageService.log_usage()`); a `token_usage_log` row is written after each streaming call
- Usage log write failure does not abort or delay the SSE response (I21)
- Vector store + embedding backend integration
- RAG pipeline composability
- Auth middleware wired into streaming responses
- Conversation persistence model (`ConversationLog`)

---

## S2 — Plain REST API

**User goal:** Build a standard CRUD API with auth and admin — no AI involved.

**Stack:** postgres + jwt auth + sqladmin + no LLM/vector/storage

**Flow:**
1. `fastagentstack new myapi --preset standard`
2. Define models, routes, schemas in the project root
3. `fastagentstack migrate` + `fastagentstack createsuperuser`
4. Admin panel auto-registers models; `createsuperuser` account grants both API and `/admin` access (ADR-049 — no separate `admin_secret_key`)

**What this validates:**
- Framework works as a non-AI FastAPI wrapper (AI-native, not AI-only)
- Zero AI deps in the lockfile for this preset
- SQLAdmin auto-registration
- Health checks and middleware work independently of AI modules

---

## S3 — Custom Backend (Any Family)

**User goal:** Integrate a provider not supported by built-in backends — e.g., Azure Blob Storage, Pinecone, a private LLM endpoint, or an in-house embedding model.

**Applies to:** all four pluggable families — storage, vector store, embedding, LLM provider.

**Flow:**
1. User implements the family's Protocol in their project (`myproject/backends.py`)
2. Points the relevant settings field to the dotted path:
   ```python
   storage_backend = "myproject.backends.AzureStorage"
   vector_db = "myproject.backends.PineconeStore"
   llm_provider = "myproject.backends.PrivateLLM"
   embedding_provider = "myproject.backends.CustomEmbedder"
   ```
3. Framework factory imports and instantiates the class; treats it identically to built-ins
4. User adds their own dependencies to their project's `pyproject.toml` — no changes to fastagentstack needed

**Database:** not extensible this way — change `DATABASE_URL` to switch engines (postgres, mysql, sqlite). Swapping the ORM violates ADR-002.

**What this validates:**
- Dotted-path factory resolution works for all four families (ADR-012)
- Protocol/ABC is complete enough to implement externally
- Custom backends receive `Settings` at instantiation and can read user-defined fields
- Extras gate doesn't interfere with custom backends
- Invariant I1 (full Protocol conformance) is testable from outside the package
- Custom `LLMBackend` implementations must emit a trailing `CompletionResult` in `stream()` (ADR-036, I1)

---

## S4 — Schema-Per-Tenant SaaS

**User goal:** Run a multi-tenant SaaS where each tenant gets an isolated Postgres schema.

**Flow:**
1. Middleware resolves tenant from subdomain or JWT claim
2. Injects schema name into the session factory on each request
3. Alembic migrations run per-schema on tenant provisioning

**What this validates:**
- Session factory schema override (Invariant I8 and Architecture note in module 3)
- No hard-coded schema assumptions in `Base` or session setup
- Middleware escape hatch — user can inject into the request lifecycle without forking the framework

---

## S5 — Background Document Processing

**User goal:** Upload PDFs via API; process them asynchronously (extract, chunk, embed, store).

**Stack:** s3 storage + dramatiq + qdrant + bedrock embedding

**Flow:**
1. API endpoint receives PDF upload → stores in S3 → enqueues Dramatiq task
2. Worker extracts text, chunks, embeds via Bedrock, upserts into Qdrant
3. Task status visible in admin panel

**What this validates:**
- Storage backend (upload/download)
- Dramatiq task definition and worker CLI command
- Embedding backend pipeline
- Vector store upsert
- All three background-task-related modules working end-to-end

---

## S6 — Template Update (`fastagentstack update`)

**User goal:** A project generated 6 months ago needs to pick up new framework features (e.g., a
new CLI command, updated docker-compose service, new settings field).

**Flow:**
1. User runs `fastagentstack update` inside their project directory
2. Copier reads `.copier-answers.yml` to recall the original answers
3. Copier re-renders the template with those answers and the new template version
4. Files that the user has not modified are updated automatically
5. Files where the user has local changes trigger a diff/conflict prompt
6. User resolves conflicts; framework-owned files (Dockerfile, docker-compose, alembic env) get
   updated; user-owned files (models, routes, agents) are preserved

**Protected files** (user-owned — never overwritten without prompt):
- `models.py`, `routes.py`, `agents.py`, `tasks.py`
- `alembic/versions/` (all migration files)
- `seeds.py`

**Framework-owned files** (updated silently on version bump):
- `Dockerfile`, `docker-compose.yml`, `alembic/env.py`, `.github/workflows/ci.yml`
- `alembic.ini`, `.pre-commit-config.yaml`

**What this validates:**
- `.copier-answers.yml` contract is stable across framework versions
- Copier update flow works without destroying user code
- Framework-owned vs user-owned file distinction is enforced in the template

**User-modified files behavior:**
- If the user has modified a framework-owned file (e.g., `Dockerfile`), `copier update` presents
  a 3-way merge diff. User chooses: accept upstream, keep local, or manual merge.
- Copier's `--conflict rej` flag writes `.rej` files for unresolved conflicts — the CLI prints a
  summary of `.rej` files at the end with guidance to resolve them.
- If a new template version adds a copier question that didn't exist before (e.g., a new boolean
  flag), and the user runs in `--defaults` mode, the question's `default` value is used silently.
  In interactive mode, the user is prompted for the new question only.

---

## S7 — Multi-Agent Orchestration

**User goal:** Build a support bot where a routing agent delegates to specialised sub-agents
(billing, technical, escalation) based on the user's intent.

**Stack:** postgres + bedrock (LLM) + jwt auth

**Flow:**
1. `fastagentstack new support-bot --preset agent`
2. Three agent handlers registered: `billing`, `technical`, `escalation`
3. A `router` agent handler receives the message, calls the LLM to classify intent, then calls
   the appropriate sub-agent handler directly (function call, not HTTP)
4. Sub-agent returns a streaming response; router streams it through to the client
5. Full conversation (user → router classification → sub-agent response) persisted to one thread

**What this validates:**
- `@app.agent()` registry supports multiple named agents
- Agent handlers can call other agent handlers as plain async functions
- A single conversation thread can contain messages from multiple logical agents
- Streaming pass-through works when an outer handler delegates to an inner async generator
- `AgentHandler` Protocol is flexible enough for orchestration patterns

---

## S8 — API Key Authentication

**User goal:** Expose the API to a third-party integration (e.g., a Slack bot, a mobile app) that
authenticates with a long-lived API key instead of a user login session.

**Stack:** postgres + jwt auth (for human users) + API key auth (for programmatic clients)

**Flow:**
1. Admin creates an API key for the integration via `POST /api-keys` (authenticated as superuser)
2. Framework returns the raw key once (`fas_<token>`) — show-once, then only the hash is stored
3. Integration sends `Authorization: Bearer fas_<token>` on each request
4. A custom dependency resolves the API key: `APIKeyService.authenticate(raw_key)` → `APIKey`
5. Route uses `APIKey.scopes` to enforce access control on the endpoint
6. Superuser revokes the key via `POST /api-keys/{id}/revoke`

**What this validates:**
- `APIKeyService.create`, `authenticate`, `revoke`, `list_for_user` all work end-to-end
- Key is hashed at rest; raw key never stored or logged
- `last_used_at` is updated on each authenticated request
- Scopes field is readable by application logic for fine-grained access control
- API key auth coexists with JWT auth on the same app (both wired via the same auth backend)

---

## S9 — Horizontal Scaling / Multi-Worker

**User goal:** Deploy the app with 4 Gunicorn workers (or 3 Kubernetes replicas) and verify that
auth, sessions, and rate limiting behave correctly across processes.

**Stack:** postgres + redis + jwt auth + rate limiting

**Flow:**
1. App deployed with `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app`
2. User logs in on worker A, receives a JWT access token and refresh token
3. User makes requests; requests are load-balanced across all 4 workers
4. User logs out on worker B → refresh token deleted from Redis, JTI added to denylist in Redis
5. Subsequent requests with the old access token are rejected by all workers (denylist in Redis)
6. Rate limiter counts are consistent across workers (Redis-backed, not in-process)
7. Session auth users: session data in Redis is readable by all workers

**What this validates:**
- JWT denylist stored in Redis, not in-process (NFR Security, ADR-015)
- Refresh token stored in Redis and deleted on logout
- `RateLimiter` Redis backend is used (not in-memory fallback) when `redis_url` is set
- Session auth does not use in-memory fallback in multi-worker deployments
- Key collision between sessions, JWT denylist, and rate limiting is prevented by namespaced prefixes
  (`fas:session:`, `fas:jti:deny:`, `fas:rl:`) — all on DB 0 (ADR-033)

**Failure mode — Redis unreachable at runtime:**
- If Redis becomes unreachable after startup, authenticated requests that require denylist
  checking must fail closed (return 503, not silently allow). Silent open-fail would let revoked
  tokens through.
- Rate limiter failing to reach Redis: fail open (allow request) with a warning log — rate
  limiting is a soft protection, not a security boundary.
- Health check `/health/ready` returns 503 naming Redis as the failing service.

---

## S10 — Worker Operational Pattern

**User goal:** Run the full `agent` stack locally and in production: web server + Dramatiq
worker + periodiq, all sharing the same Postgres and Redis.

**Stack:** postgres + redis + dramatiq + periodiq

**Flow:**
1. `docker-compose up` starts: `app` (web), `worker` (Dramatiq), `postgres`, `redis`
2. The `worker` service runs `fastagentstack worker apps.chat.tasks`
3. The `app` service runs `fastagentstack run` (web server)
4. An API request enqueues a task via `task.send(...)` — the web process returns immediately
5. The `worker` process picks up the task, processes it, writes results to Postgres
6. The `app` service exposes a status endpoint that reads the result from Postgres
7. On `docker-compose down`, the worker receives SIGTERM, finishes the in-flight task, and exits
   cleanly — no messages are lost because the task is still in Redis until ACKed

**Scaling:**
- Running `fastagentstack worker --processes 4` forks 4 Dramatiq worker processes
- All 4 processes connect to the same Redis broker and same Postgres — no additional config needed
- The `scheduler` service (`fastagentstack scheduler`) runs as a singleton — only one replica
  should run it to avoid duplicate job execution

**What this validates:**
- Generated `docker-compose.yml` includes a `worker` service when `task_broker != "none"`
- `fastagentstack worker` command accepts `--processes N` for multi-process workers
- SIGTERM handling: in-flight tasks complete before worker exits
- Web and worker can share the same `.env` file — no worker-specific config required
- Scheduler must not be replicated; the generated `docker-compose.yml` sets `replicas: 1` for
  the scheduler service

---

## S11 — Password Reset and Email Verification

**User goal:** Allow users to recover their account via a password-reset email and verify their
email address after registration.

**Stack:** postgres + jwt auth + email backend (SMTP or SES)

**Flow (password reset):**
1. User submits `POST /auth/forgot-password` with their email address
2. Framework generates a single-use reset token (`secrets.token_urlsafe(32)`), stores it in
   Postgres as `auth_verification_token` with a 24-hour TTL and `type="password_reset"`
3. Framework sends an email containing the reset link `https://app/reset?token=<token>`
4. User follows the link and submits `POST /auth/reset-password` with the token and new password
5. Framework validates: token exists, is unused, has not expired; sets new password hash; marks
   token as used; invalidates all existing refresh tokens for the user (forces re-login)
6. After TTL: expired tokens are cleaned up by a periodic task or on next lookup

**Flow (email verification):**
1. After registration, framework generates a verify token with a 72-hour TTL and `type="email_verify"`
2. User clicks the verify link; `POST /auth/verify-email` with the token
3. Framework marks `User.is_active = True` and the token as used
4. Unverified users are blocked from protected routes (configurable via `require_verified_email`)

**What this validates:**
- `auth_verification_token` table: single-use enforcement, TTL expiry, type discrimination
- Token expiry check returns 410 Gone (not 404), confirming the token existed but expired
- Re-using a consumed token returns 400 (not 404)
- Password reset invalidates all active refresh tokens for the user
- Email verification gate blocks unverified users when `require_verified_email = True`
- Concurrent reset requests: only the most recent token is valid; previous tokens are superseded

---

## S12 — Logout and Token Revocation

**User goal:** Log out from one device without affecting other active sessions; ensure the access
token cannot be reused after logout even within its remaining TTL.

**Stack:** postgres + redis + jwt auth (two-token model)

**Flow:**
1. Client holds an access token (30-min JWT) and a refresh token (30-day opaque)
2. Client calls `POST /auth/logout` with `Authorization: Bearer <access_token>` header and
   `{"refresh_token": "<refresh_token>"}` in the body
3. Framework:
   - Decodes the access token, extracts its `jti` claim
   - Writes `fas:jti:deny:{jti}` to Redis with TTL = remaining access token lifetime
   - Deletes `fas:refresh:{refresh_token}` from Redis
4. Any subsequent request with the old access token hits the denylist check and is rejected (401)
5. Any attempt to call `POST /auth/refresh` with the old refresh token returns 401
6. Other sessions (different refresh tokens issued to other devices) are unaffected

**Partial logout (access token only):**
- Client sends `POST /auth/logout` with no body (or `{"refresh_token": null}`)
- Only the access token JTI is denied; the refresh token remains valid
- Client can obtain a new access token via `POST /auth/refresh`

**Refresh token rotation:**
1. Client calls `POST /auth/refresh` with a valid refresh token
2. Framework validates the token, revokes it immediately (before issuing the new pair)
3. Framework issues a new access token + new refresh token
4. If an attacker replays the old refresh token after rotation, they receive 401
5. The new token pair is returned to the legitimate client

**Redis is required in all environments:**
- There is no in-process fallback; `redis_url` must be configured even for local development
- Developers should run Redis via `docker run -p 6379:6379 redis:7` or equivalent
- The application must refuse to start if `redis_url` is unset when token revocation is enabled (see I10)

**What this validates:**
- JTI denylist check occurs on every authenticated request (not just token creation)
- Refresh token revocation removes the Redis key; replay returns 401
- Logout is idempotent: calling it twice does not error (second call is a no-op for expired keys)
- The private `_AuthBackendChain` calls `revoke_token()` on ALL backends in order so every
  authentication path is invalidated on logout (I20); there is no public `CombinedAuthBackend`
- Session auth backends return 501 for `POST /auth/refresh` (no refresh tokens issued)
- Access token TTL check and denylist check are both required: a denied token with time remaining
  must still be rejected

---

## S13 — Secrets Manager in Production

**User goal:** Run the same generated project in three environments — dev (`.env` file), staging
(raw environment variables), production (AWS Secrets Manager) — without any code changes.

**Stack:** postgres + jwt auth + `fast-agent-stack[secrets-aws]`

**Flow:**
1. `fastagentstack new myapp --preset standard` with `secrets_backend = aws`
2. Generated `pyproject.toml` depends on `fast-agent-stack[secrets-aws]` (boto3 included)
3. **Dev:** `.env` file sets `DATABASE_URL`, `SECRET_KEY`, etc. `SECRETS_BACKEND` is unset.
   `BaseSettings` loads from `.env` — default source chain, no AWS call.
4. **Staging:** CI sets environment variables directly. `SECRETS_BACKEND` is unset.
   `BaseSettings` reads from env — same code, no AWS call.
5. **Production:** `SECRETS_BACKEND=aws`, `SECRETS_AWS_SECRET_ID=myapp/production`,
   `SECRETS_AWS_REGION=us-east-1` are injected by the container runtime.
   `BaseSettings` inserts `AWSSecretsManagerSettingsSource` between env and dotenv in the chain.
   `DATABASE_URL`, `SECRET_KEY`, etc. are pulled from the secret JSON object.
6. An env var set in the container (e.g., `DEBUG=false`) overrides the secret value for that key —
   env vars always win over the secrets manager.

**What this validates:**
- Source priority chain: env > cloud secrets > dotenv (ADR-017)
- Zero code change across dev/staging/prod — behavior entirely controlled by `SECRETS_BACKEND`
- Missing boto3 raises `ImportError` at settings construction time with the install command
- `SECRETS_BACKEND` is read from `os.environ` directly (bootstrap constraint — not a pydantic field)
- The generated project's extras declaration is wired correctly by the copier template

---

## S14 — Rate Limiting Enforcement

**User goal:** Protect API endpoints from abuse with per-IP rate limiting backed by Redis.

**Preconditions:** `include_rate_limit = true`, `redis_url` configured.

**Steps:**
1. Client sends requests to a rate-limited endpoint up to the configured limit (e.g., 60/min)
2. Each request increments a Redis key (`fas:rl:{ip}:{window}`) via atomic Lua script (ADR-016)
3. Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers
4. Request N+1 within the same window receives 429 Too Many Requests with a `Retry-After` header
5. After the window resets, the client can make requests again

**What this validates:**
- Redis fixed-window counter increments atomically (no INCR/EXPIRE race)
- 429 response includes correct headers and `Retry-After`
- Rate limit state is shared across workers (not process-local; consistent with I10 principle)
- Unauthenticated and authenticated requests both respect the limit
- `/health/live` and `/health/ready` are exempt from rate limiting

---

## S15 — Distributed Tracing (Config-Driven, Optional)

**User goal:** Trace a request end-to-end across web server, database, Redis, and external LLM call — enabled purely by configuration.

**Preconditions:** `tracing = "jaeger"` in copier answers, `OTEL_EXPORTER_OTLP_ENDPOINT` set at runtime. When `tracing = "none"`, no OTEL dependencies are installed or imported.

**Steps:**
1. Client sends a request that triggers a DB query, a Redis lookup, and an LLM provider call
2. FastAPI middleware creates a root span with `trace_id` and injects it into the response (`traceparent` header)
3. SQLAlchemy, Redis, and HTTP client instrumentation create child spans automatically
4. All spans are exported to the configured collector via OTLP

**What this validates:**
- A single `trace_id` links all spans from one request (web → DB → Redis → LLM)
- Span attributes include `http.method`, `http.route`, `db.statement` (sanitised), `http.status_code`
- Trace context propagates to outbound HTTP calls (LLM provider) via `traceparent` header
- Tracing adds < 5ms p99 latency overhead (NFR)
- When `tracing = "none"`: zero OTEL packages in the lockfile, no middleware registered, no runtime cost
- Switching from off → on requires only changing the config + installing `fast-agent-stack[tracing]` — no code changes

---

## S16 — Startup Validation Failure

**User goal:** Get a clear error at application startup (not at first request time) when required
configuration is missing or an external service is unreachable.

**Stack:** postgres + redis + jwt auth

**Flow (missing secret):**
1. Deploy with `auth_backends = ["jwt"]` but `SECRET_KEY` unset
2. Application raises `RuntimeError("secret_key must be set when \"jwt\" in auth_backends")` before serving any request
3. Process exits with code 1; error message appears in stdout/stderr

**Flow (missing redis_url):**
1. Deploy with `auth_backends = ["jwt"]` but `REDIS_URL` unset
2. Application raises `RuntimeError("redis_url must be set when \"jwt\" in auth_backends or \"session\" in auth_backends")` before serving any request

**Flow (Redis unreachable):**
1. Deploy with `auth_backends = ["jwt"]`, `REDIS_URL = "redis://bad-host:6379"`
2. `FastAPIRedisLifespanHook.__aenter__()` attempts a Redis `PING` with a 5-second timeout (I9, ADR-037)
3. On failure: raises `RuntimeError("Cannot connect to Redis at redis://bad-host:6379 — check that redis_url is correct and Redis is running")` and process exits

**What this validates:**
- Invariant I11 is enforced: missing secrets fail fast at startup
- Redis connectivity is verified during lifespan startup, not at first authenticated request
- Error messages name the specific missing setting or failing service
- The process exits non-zero; orchestrators (Docker, K8s) see the failure and can restart/alert

---

## S17 — RBAC Permission Check

**User goal:** Protect an endpoint so only users with the `posts.delete` permission can access it.

**Setup:**
1. User A belongs to group "editors" which has permission `("posts", "delete")`
2. User B has no groups, no direct permissions
3. User C is `is_superuser=True`
4. User D has `is_active=False` but has the permission via group

**Route:**
```python
@router.delete("/posts/{id}", dependencies=[Depends(require_permission("posts.delete"))])
async def delete_post(id: int): ...
```

**Validation steps:**

| Actor | Expected | HTTP status |
|---|---|---|
| User A (has permission via group) | Allowed | 200 |
| User B (no permission) | Denied | 403 `{"detail": "Permission denied"}` |
| User C (superuser) | Allowed (bypasses all checks) | 200 |
| User D (inactive, has permission) | Denied | 403 `{"detail": "Account inactive"}` |
| No auth header | Denied | 401 `{"detail": "Not authenticated"}` |

**Framework validates:**
- Permission resolution: `user.is_superuser OR perm in user_permissions OR perm in any group_permissions for user's groups`
- `is_active=False` short-circuits before permission check
- `require_permission()` is a reusable FastAPI dependency
- Permission string format: `"resource.action"` (dot-separated)


## S18 — Agent Tool-Call Loop (ADR-046)

**Trigger:** User sends a chat message to an agent endpoint that has tools registered.

**Flow:**

1. Client POSTs `{"messages": [...]}` to `/agents/chat`
2. Handler calls `async for chunk in agent_loop(backend, messages, tools, max_iterations=10)`
3. `agent_loop` calls `backend.stream(messages, tools=tool_schemas)`
4. Backend yields a `ToolCallResult(tool_calls=[ToolCall(id="tc_1", name="search_docs", arguments=...)])` — no text chunks emitted
5. `agent_loop` dispatches: finds the `@tool`-decorated function named `search_docs`, calls it
6. Result appended as `Message(role="tool", content=result_str, tool_call_id="tc_1")`
7. `agent_loop` calls `backend.stream(messages + [tool_msg], tools=tool_schemas)` again
8. Backend yields text chunks (`str`) followed by a trailing `CompletionResult` sentinel — no more tool calls
9. `agent_loop` yields each text chunk (forwarded to SSE) then yields the `CompletionResult` sentinel and returns
10. Handler streams text chunks to the client; `stream_sse` intercepts the sentinel for usage logging

**Failure modes:**

| Condition | Behavior |
|---|---|
| `max_iterations` exceeded (I23) | `agent_loop` yields empty `CompletionResult` sentinel (`content=""`); caller treats empty content as a bounded failure and may return 500 |
| Tool function raises exception | Error message returned as tool result, loop continues |
| Tool name not found in registry | Error message returned as tool result, loop continues |
| Backend timeout (I22) | `TimeoutError` propagates, handler returns 504 |

**Invariants enforced:** I22 (timeout), I23 (iteration cap)

## S19 — RAG Retrieval with Reranking (ADR-045)

**Trigger:** User asks a question; RAG pipeline retrieves and reranks document chunks.

**Flow:**

1. Query arrives at `RagService.retrieve(query, top_k=5)`
2. `RagService` embeds the query via `EmbeddingProtocol.embed(query)`
3. `RagService` over-fetches from vector store: `vector_store.search(embedding, top_k=top_k * 3)`
4. Returns 15 candidate `VectorSearchResult` items
5. If `reranker is not None`:
   a. Extracts content strings from candidates
   b. Calls `reranker.rerank(query, documents, top_k=5)`
   c. Returns reranked `RerankResult` list (sorted by relevance score)
6. If `reranker is None`: returns the top 5 vector results as-is (cosine similarity ordering)
7. Chunks are formatted and passed to the LLM as context

**Failure modes:**

| Condition | Behavior |
|---|---|
| Reranker timeout (I22) | Falls back to vector similarity ordering, logs warning |
| Reranker returns empty results | Falls back to vector similarity ordering |
| Vector store timeout (I22) | `TimeoutError` propagates to caller |
| No documents match threshold | Empty context passed to LLM (LLM answers from knowledge) |

**Over-fetch ratio:** 3x (hardcoded, documented in ADR-045). Retrieving `top_k * 3` candidates
gives the reranker enough material to surface genuinely relevant chunks that cosine similarity
may have ranked lower.

**Invariants enforced:** I22 (timeout on both vector store and reranker)


## S20 — User Migration Branch Lifecycle (ADR-048)

**Trigger:** Developer scaffolds a project and creates their first model migration.

**Flow:**

1. Developer runs `fas new docqa --preset agent -y`
2. Scaffolder resolves framework heads filtered by enabled features:
   - `include_auth=True` → includes `fas_auth_0001`
   - `llm_provider != "none"` → includes `fas_ai_0002`
3. Scaffolder generates `alembic/versions/0001_docqa_initial.py`:
   - `revision = "docqa_0001"`, `branch_labels = ("docqa",)`
   - `depends_on = ("fas_auth_0001", "fas_ai_0002")`
   - `upgrade()` is a no-op
4. Developer adds a `Document` model to `docqa/models.py`
5. Developer runs `fas makemigrations -m "add-documents"`
6. CLI reads `project_name` from `.copier-answers.yml` → `"docqa"`
7. CLI calls `command.revision(cfg, head="docqa@head", autogenerate=True, ...)`
8. Alembic generates `alembic/versions/0002_add_documents.py` with `down_revision = "docqa_0001"`
9. Developer runs `fas migrate` → applies all heads (framework + user) in dependency order

**Variant — minimal preset (no auth, no AI):**

1. `fas new api --preset minimal -y`
2. No framework features enabled → `depends_on = None`
3. Seed migration: `branch_labels = ("api",)`, fully independent branch
4. `fas migrate` applies only user branch (no framework migrations in version_locations)

**Failure modes:**

| Condition | Behavior |
|---|---|
| `.copier-answers.yml` missing | `makemigrations` prints error, exits 1 |
| Seed migration deleted by user | `{project_name}@head` resolves to nothing, Alembic error |
| Framework feature added post-scaffold | `fas migrate` still works (heads), but `depends_on` doesn't list it |

**Invariants enforced:** I16 (branched migrations)
