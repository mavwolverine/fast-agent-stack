# Part 3 - Authentication

> **Series:** [Tutorial index](index.md) · [Part 2](02-database-models.md) · **You are here:** Part 3 · [Part 4](04-ingestion-agent.md)

In Part 2 you added a `Document` model and three CRUD routes. Those routes are currently open to anyone. In Part 3 you'll wire up the JWT authentication that the `agent` preset already scaffolded, create a user, and protect the document routes.

**By the end of this part** `POST /documents`, `GET /documents`, and `GET /documents/{id}` require a valid JWT. Unauthenticated requests return 401.

---

## Prerequisites

- Part 2 complete (Document model and CRUD routes in place)
- Docker services running: PostgreSQL on 5432, Valkey/Redis on 6379

---

## 1. What the scaffold already gave you

The `agent` preset set `include_auth=True`. Open `docqa/app.py` and you'll find the auth wiring already present:

```
from fast_agent_stack.core.auth import AuthLifespanHook
from fast_agent_stack.core.auth.routes import router as auth_router
…
_stack.add_lifespan_hook(FastAPIRedisLifespanHook(_settings, app=app))
_stack.add_lifespan_hook(AuthLifespanHook(_settings))
…
app.include_router(auth_router)
```

This registers three routes automatically:
- `POST /auth/token` - login, returns access + refresh tokens
- `POST /auth/refresh` - exchange a refresh token for a new access token
- `POST /auth/logout` - revoke a refresh token

And `docqa/settings.py` already has:

```
auth_backends: list[str] = ["jwt"]
secret_key: str = "change-me-in-production"
redis_url: str = "redis://localhost:6379/0"
```

You need to set the secret key and run migrations.

---

## 2. Set the secret key

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Then replace the placeholder value:

```bash
DOCQA_SECRET_KEY=<generate below>
```

Generate a strong random key:

```bash
python -c "import secrets; print('DOCQA_SECRET_KEY=' + secrets.token_hex(32))"
```

`DOCQA_SECRET_KEY` is used for:
- Signing JWT access and refresh tokens — anyone with this value can forge tokens
- Signing the SQLAdmin session cookie at `/admin` (ADR-049)

A single key serves both purposes. Never commit it to version control. `.env` is in `.gitignore`.

---

## 3. Run migrations

The framework ships its own auth migrations (users, groups, permissions, API keys, verification tokens). They apply automatically alongside your project migrations:

```bash
fas migrate
```

You do not run `fas makemigrations` for auth tables - the framework owns them. `fas migrate` applies all pending migrations in dependency order: framework branches first, then your `docqa` branch.

---

## 4. Create a superuser

```bash
fas createsuperuser --email admin@docqa.local
```

The CLI prompts for a password. The created account has `is_superuser=True`, which bypasses all permission checks.

---

## 5. Obtain a JWT token

Start the dev server in one terminal:

```bash
fas dev
```

In a second terminal, log in:

```bash
curl -s -X POST http://127.0.0.1:8000/auth/token \
     -H "Content-Type: application/json" \
     -d '{"email": "admin@docqa.local", "password": "yourpassword"}' | python -m json.tool
```

Response:

```json
{
    "access_token": "eyJhbGci...",
    "token_type": "bearer",
    "refresh_token": "eyJhbGci..."
}
```

The access token is short-lived (15 minutes by default). The refresh token is stored in Redis and lasts much longer. Use the refresh token to get a new access token without re-entering credentials.

---

## 6. Protect the document routes

Open `docqa/routes.py`. Add the `get_current_user` dependency to each document route:

```python
import uuid

from fast_agent_stack.auth import User, get_current_user
from fast_agent_stack.database import get_async_session
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Document
from .schemas import DocumentCreate, DocumentResponse
from .settings import Settings, get_settings

router = APIRouter()


@router.get("/")
async def root(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"message": "Hello from docqa!"}


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def create_document(
    body: DocumentCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Document:
    doc = Document(**body.model_dump())
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    result = await session.execute(select(Document))
    return list(result.scalars().all())


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Document:
    doc = await session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
```

`get_current_user` extracts the JWT from the `Authorization: Bearer <token>` header, verifies the signature against `DOCQA_SECRET_KEY`, and returns the authenticated `User` object. If the header is missing or the token is invalid, it raises 401 automatically.

The `current_user` parameter is available in the route body if you need it (for example to record who created a document). For now the routes ignore it - they just need the authentication gate.

Import path: `from fast_agent_stack.auth import get_current_user, User` is the public facade. Never import from `fast_agent_stack.core.auth.dependencies` directly.

---

## 7. Test the protected routes

Restart the dev server so the route changes take effect, then:

```bash
TOKEN="eyJhbGci..."   # paste your access_token from step 5

# Authenticated POST - should succeed
curl -s -X POST http://127.0.0.1:8000/documents \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"title": "Protected doc", "content": "Only logged-in users see this."}'

# Authenticated GET - should return your documents
curl -s http://127.0.0.1:8000/documents -H "Authorization: Bearer $TOKEN"

# No token - should return 401
curl -s http://127.0.0.1:8000/documents
```

---

## 8. Refresh and logout

When the access token expires, use the refresh token to get a new one without re-logging in:

```bash
REFRESH_TOKEN="eyJhbGci..."   # paste your refresh_token from step 5

# Get a new access token
curl -s -X POST http://127.0.0.1:8000/auth/refresh \
     -H "Content-Type: application/json" \
     -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

To log out (revoke the refresh token so it cannot be used again):

```bash
curl -s -X POST http://127.0.0.1:8000/auth/logout \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

The refresh token is stored in Redis. If Redis is unreachable during logout, the endpoint returns 503 rather than silently succeeding - a revoked token must not remain usable.

---

## What you built

- `DOCQA_SECRET_KEY` set in `.env` — signs JWT tokens and the admin session cookie
- Framework auth migrations applied (`fas migrate`) — users, groups, permissions, API keys tables created automatically
- Superuser account created via `fas createsuperuser` — grants access to both `/auth/token` and the SQLAdmin panel at `/admin`
- JWT tokens obtained via `POST /auth/token` (short-lived access token + long-lived refresh token)
- Document routes protected with `Depends(get_current_user)` — unauthenticated requests return 401
- Token refresh via `POST /auth/refresh`, revocation via `POST /auth/logout` (Redis-backed, fail-closed)
- SQLAdmin panel at `/admin` authenticates against the user table (`is_staff` or `is_superuser` required)

---

## Next steps

[Part 4 - Ingestion Agent](04-ingestion-agent.md)
