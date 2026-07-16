# Authentication & Authorization

fast-agent-stack ships a complete auth system: JWT tokens, sessions, RBAC (users, groups, permissions), API keys, email verification, and password reset. All backends are pluggable.

## Backends

Configure auth backends in settings:

```python
class Settings(BaseSettings):
    auth_backends: list[str] = ["jwt"]          # JWT only
    # auth_backends: list[str] = ["session"]    # session only
    # auth_backends: list[str] = ["jwt", "session"]  # both
    secret_key: str = "change-me-in-production"
    redis_url: str = "redis://localhost:6379"
```

### JWT Backend

Issues access tokens (15 min TTL) and refresh tokens (30-day TTL). Refresh tokens are stored in Redis and bound to a JTI denylist for secure logout.

```bash
pip install "fast-agent-stack[auth-jwt]"
```

### Session Backend

Cookie-based sessions stored in Redis. Useful for browser-facing UIs.

```bash
pip install "fast-agent-stack[auth-session]"
```

## Routes

All auth routes are mounted automatically when auth is enabled:

| Route | Method | Description |
|-------|--------|-------------|
| `/auth/token` | POST | Issue access + refresh tokens |
| `/auth/refresh` | POST | Exchange refresh token for new access token |
| `/auth/logout` | POST | Revoke refresh token (adds JTI to denylist) |
| `/auth/send-verification` | POST | Send email verification link |
| `/auth/verify-email` | POST | Verify email with token |
| `/auth/forgot-password` | POST | Send password-reset link |
| `/auth/reset-password` | POST | Reset password with token |

## RBAC — Users, Groups, Permissions

```python
from fast_agent_stack.core.auth.dependencies import require_permission

@app.get("/posts/{id}")
async def get_post(id: int, _=Depends(require_permission("posts.read"))):
    ...

@app.delete("/posts/{id}")
async def delete_post(id: int, _=Depends(require_permission("posts.delete"))):
    ...
```

Permissions follow `resource.action` format. Assign them to users directly or via groups.

## API Keys

Long-lived API keys for service-to-service or CLI access:

```bash
POST /api-keys       # create key
GET  /api-keys       # list keys
DELETE /api-keys/{id} # revoke key
```

Pass keys as `Authorization: Bearer <key>` — identical to JWT tokens from the client's perspective.

## Admin UI

The SQLAdmin UI is available at `/admin` when enabled:

```bash
pip install "fast-agent-stack[admin]"
```

```python
class Settings(BaseSettings):
    admin_enabled: bool = True
    secret_key: str = "change-me-in-production"  # signs both JWT tokens and admin sessions (ADR-049)
```

## Custom Auth Backend

Point `auth_backends` at a dotted Python path (ADR-012):

```python
auth_backends: list[str] = ["myproject.auth.MyCustomBackend"]
```

Your class must implement `AuthBackendProtocol`.
