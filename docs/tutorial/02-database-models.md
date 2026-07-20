# Part 2: Database and Models

> **Series:** [Progressive Tutorial](index.md) · [Part 1](01-scaffold.md) · **You are here:** Part 2 · [Part 3](03-authentication.md)

In Part 1 you scaffolded the `docqa` project and hit a live dev server. In Part 2 you'll add a persistent data layer: a `Document` SQLAlchemy model, Pydantic schemas, an Alembic migration, and three CRUD routes.

**By the end of this part** the Document Q&A Assistant can store and retrieve documents via a REST API backed by PostgreSQL.

---

## Prerequisites

- Part 1 complete (`docqa/` project scaffolded with `--preset agent`, PostgreSQL running)
- Dev server confirmed working (`fas dev` shows startup output)

---

## 1. Define the Document model

Open `docqa/models.py` and replace its contents:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from fast_agent_stack.database import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
```

`BaseModel` (from `fast_agent_stack.database`) is a SQLAlchemy abstract base that automatically adds three columns to every subclass: `id` (UUID, auto-generated), `created_at`, and `updated_at`. You define only the columns specific to `Document`.

---

## 2. Define Pydantic schemas

Open `docqa/schemas.py` and replace its contents:

```python
import uuid

from pydantic import BaseModel


class DocumentCreate(BaseModel):
    title: str


class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
```

`DocumentCreate` is the request body. `DocumentResponse` is what the API returns, including `id` assigned by the database. `from_attributes = True` lets Pydantic build a `DocumentResponse` directly from a SQLAlchemy `Document` object.

> **Models vs schemas:** Keep these in separate files. `Document` in `models.py` is ORM state and maps to a database row. `DocumentCreate` and `DocumentResponse` in `schemas.py` are API contract and define what goes over the wire. Mixing them creates tight coupling between your data model and your API surface.

---

## 3. Generate and run the migration

`fas makemigrations` reads your models and generates an Alembic migration file:

```bash
fas makemigrations -m "add-documents"
fas migrate
```

After running these, `alembic/versions/` will contain a file like `20260701_abc123_add_documents.py`. Open it to see the generated `CREATE TABLE documents` statement as plain SQL via Alembic's `op.create_table()`.

`fas migrate` applies all pending migrations including any framework-internal ones. Running it a second time is safe; Alembic tracks which revisions have been applied.

---

## 4. Add CRUD routes

Replace `docqa/routes.py` with the following:

```python
import uuid

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
) -> Document:
    doc = Document(**body.model_dump())
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    session: AsyncSession = Depends(get_async_session),
) -> list[Document]:
    result = await session.execute(select(Document))
    return list(result.scalars().all())


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> Document:
    doc = await session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
```

`get_async_session` is a FastAPI dependency that provides a managed async SQLAlchemy session. It opens, commits (or rolls back on error), and closes automatically at the end of each request.

---

## 5. Start the server and seed data

```bash
fas dev
```

In a second terminal, create a document and confirm it's stored:

```bash
curl -X POST http://127.0.0.1:8000/documents \
     -H "Content-Type: application/json" \
     -d '{"title": "Introduction to RAG"}'

curl http://127.0.0.1:8000/documents
```

Or using Python with `httpx`:

```python
import httpx

base = "http://127.0.0.1:8000"
resp = httpx.post(f"{base}/documents", json={"title": "Test doc"})
print(resp.json())
doc_id = resp.json()["id"]
print(httpx.get(f"{base}/documents/{doc_id}").json())
print(httpx.get(f"{base}/documents").json())
```

The `/health/ready` endpoint now also verifies the database is reachable, useful when switching to an external database server.

---

---

## What you built

- A `Document` model using `fast_agent_stack.database.BaseModel` with UUID primary key and automatic timestamps
- Pydantic schemas (`DocumentCreate`, `DocumentResponse`) keeping ORM state separate from the API contract
- An Alembic migration generated by `fas makemigrations -m "add-documents"`
- Three CRUD routes (`POST /documents`, `GET /documents`, `GET /documents/{id}`) using the `get_async_session` dependency

---

## Next steps

[Part 3: Authentication](03-authentication.md)
