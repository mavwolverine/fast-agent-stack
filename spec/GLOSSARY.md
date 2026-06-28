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

**Escape hatch** — direct access to the underlying third-party object (e.g., `app.fastapi_app`, the raw SQLAlchemy engine). Every wrapped component must expose one.

**Group** — a named collection of users that share permissions. Equivalent to Django's Group and AWS IAM Group. Users can belong to multiple groups. Permissions are assigned to groups via the `group_permissions` join table. See ADR-028.

**Permission** — a `(resource, action)` pair granting the ability to perform an operation (e.g., `"posts"`, `"delete"`). Assigned to groups or directly to users. See ADR-028.

**RBAC (Role-Based Access Control)** — the authorization model used by the framework. Users gain permissions through group membership (`user_groups` → `group_permissions`) or direct grants (`user_permissions`). `is_superuser` bypasses all permission checks. See ADR-028.

**UsageService** — the framework service (injected as a FastAPI dependency or called directly from
`stream_sse`) responsible for writing token usage records to `token_usage_log`. Exposes
`log_usage(result: CompletionResult, *, user_id, api_key_id, agent_name, conversation_id)`
and `get_usage(user_id, period)`. Write failures in `log_usage()` must be caught, logged, and
swallowed — they must never propagate to the LLM caller (I21). See ADR-035 and ADR-036.

**copier.yml** — the Copier question definition file that drives interactive project generation. Variable names defined here are the only valid names for template conditionals.

**Deprecation cycle** — the process for removing or changing a public API surface covered by I6.
A deprecated symbol must emit a `DeprecationWarning` for at least one minor version before removal.
The warning message must name the replacement (if any) and the version in which removal will occur.
Removal may only happen in the next minor version after the warning was introduced (e.g., deprecated
in 0.5.0, removable in 0.6.0). CLI commands follow the same policy: `--help` output notes the
deprecation and the replacement command.
