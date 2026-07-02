# API Reference

## FastAgentStack

```python
from fast_agent_stack import FastAgentStack

app = FastAgentStack()
```

### `add_lifespan_hook(hook)`

Register an async context manager as a lifespan hook. Hooks run in registration order on startup and in reverse order on shutdown.

See `spec/INVARIANTS.md` I9 for the required registration order.

### `@app.agent(name, backend)`

Register an AI agent handler. The decorated function receives `messages: list[Message]` plus keyword arguments `user_id`, `api_key_id`, `conversation_id`.

Return a `str` for non-streaming; `yield str` for server-sent event streaming.

### `app.fastapi_app`

The underlying `FastAPI` instance (I4 escape hatch).

## Lifespan Hooks

### `DatabaseLifespanHook(database_url)`
Initialises the async engine and session factory.

### `AuthLifespanHook(settings)`
Connects Redis and wires the auth backend chain.

### `RateLimitLifespanHook(settings, *, app=None)`
Connects Redis for rate limiting. Pass `app` to auto-wire `RateLimitMiddleware` during startup.

### `TracingLifespanHook(settings)`
Initialises the OpenTelemetry tracer provider. No-op when `settings.tracing_enabled=False`.

### `AdminLifespanHook(settings)`
Mounts SQLAdmin. Must be registered after `DatabaseLifespanHook`.

## Auth

```python
from fast_agent_stack.core.auth.dependencies import require_permission

@router.delete("/posts/{id}")
async def delete_post(
    id: int,
    user_id: UUID = Depends(require_permission("posts.delete")),
):
    ...
```

## UsageService

```python
from fast_agent_stack.core.ai.usage import UsageService

svc = UsageService()

summary = await svc.get_usage(user_id=uid, db=session)
by_model = await svc.get_usage_by_model(agent_name="chat", db=session)
```

## Email

```python
from fast_agent_stack.core.email import get_email_backend

backend = get_email_backend(settings)
await backend.send(to="user@example.com", subject="Hello", body_text="World")
```
