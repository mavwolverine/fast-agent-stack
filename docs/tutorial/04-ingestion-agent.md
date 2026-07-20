# Part 4 - Ingestion Agent

> **Series:** [Tutorial index](index.md) · [Part 3](03-authentication.md) · **You are here:** Part 4 · [Part 5](05-chat-agent.md)

In Part 3 you protected the document routes with JWT auth. In Part 4 you'll add PDF ingestion: upload a file, extract its text, embed it with a local model, and store the chunks in Qdrant. A FastAPI `BackgroundTask` handles the heavy work so the upload returns immediately.

**By the end of this part** `POST /documents/upload` accepts a PDF, returns a document with `status="pending"`, and asynchronously fills Qdrant with searchable chunks. In Part 5 you'll query those chunks via a chat agent.

---

## Prerequisites

- Part 3 complete (JWT auth protecting document routes)
- Docker services running: PostgreSQL on 5432, Valkey/Redis on 6379, Qdrant on 6333
- All three from the Part 0 `docker-compose.yml`

---

## 1. Install the PDF extraction extra

The `agent` preset already includes the LLM, embedding, and vector store extras. You only need to add PDF extraction:

```bash
uv add "fast-agent-stack[extract-pdf]"
```

This installs `pymupdf` for text extraction from uploaded PDF files.

---

## 2. Update the Document model

Open `docqa/models.py`. Add `status` and `vector_doc_id` fields:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from fast_agent_stack.database import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending")
    vector_doc_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

`status` tracks where the document is in the ingestion pipeline: `"pending"` when uploaded, `"ingested"` when chunks are in Qdrant, `"failed"` if something went wrong. `vector_doc_id` is the ID used to group all chunks for this document in Qdrant - it matches the document's UUID so you can delete chunks by document later.

---

## 3. Update the schema

Open `docqa/schemas.py`. Add the new fields to `DocumentResponse`:

```python
import uuid

from pydantic import BaseModel


class DocumentCreate(BaseModel):
    title: str


class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    status: str
    vector_doc_id: str | None
```

---

## 4. Run a migration

```bash
fas makemigrations -m "add-ingestion-fields"
fas migrate
```

This generates an Alembic revision that adds `status` (with a `server_default` so existing rows get `"pending"` automatically) and `vector_doc_id` to the `documents` table.

---

## 5. Wire the RagService

Create `docqa/ai/tools/ingestion.py`. This file constructs the `RagService` - combining a local embedding model with the Qdrant vector store - and exposes it as a FastAPI dependency:

```python
from fastapi import Depends
from fast_agent_stack.rag import RagService, get_embedding_provider, get_vector_store

from ...settings import Settings, get_settings

COLLECTION = "docqa-documents"


def get_rag_service(settings: Settings = Depends(get_settings)) -> RagService:
    embedding = get_embedding_provider(settings)
    vector_store = get_vector_store(settings)
    return RagService(embedding=embedding, vector_store=vector_store)
```

`get_embedding_provider` reads `settings.embedding_provider`. Since you set `DOCQA_EMBEDDING_PROVIDER=openai` in Part 0, it routes to the OpenAI-compatible backend and picks up `DOCQA_EMBEDDING_BASE_URL` and `DOCQA_EMBEDDING_MODEL` to call Ollama's `nomic-embed-text`. `get_vector_store` reads `settings.vector_db` - the default is `"qdrant"` pointing at `http://localhost:6333` from the Part 0 Docker setup.

`COLLECTION` is the Qdrant collection name. Qdrant creates it automatically on first upsert.

---

## 6. Add the upload endpoint

Open `docqa/routes.py`. Add the upload endpoint and the ingestion background task:

```python
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fast_agent_stack.auth import User, get_current_user
from fast_agent_stack.database import get_async_session
from fast_agent_stack.rag import RagService

from .ai.tools.ingestion import COLLECTION, get_rag_service
from .models import Document
from .schemas import DocumentCreate, DocumentResponse
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)
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


@router.post("/documents/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    rag: RagService = Depends(get_rag_service),
) -> Document:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are supported")

    data = await file.read()
    doc = Document(title=file.filename or "Untitled", status="pending")
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    background_tasks.add_task(
        _ingest,
        doc.id,
        data,
        file.filename or "upload.pdf",
        file.content_type or "application/pdf",
        rag,
    )
    return doc


async def _ingest(
    doc_id: uuid.UUID,
    data: bytes,
    filename: str,
    content_type: str,
    rag: RagService,
) -> None:
    status = "ingested"
    vector_doc_id = None
    try:
        result = await rag.ingest_file(
            COLLECTION,
            data,
            filename=filename,
            content_type=content_type,
            document_id=str(doc_id),
            metadata={"filename": filename},
        )
        vector_doc_id = result.document_id
    except Exception:
        logger.exception("Ingestion failed for document %s", doc_id)
        status = "failed"

    async for session in get_async_session():
        doc = await session.get(Document, doc_id)
        if doc is not None:
            doc.status = status
            doc.vector_doc_id = vector_doc_id
            await session.commit()
```

A few things to notice:

- The endpoint returns 202 and the `Document` record immediately, before any extraction or embedding has happened. The client polls `GET /documents/{id}` to know when ingestion is done.
- `_ingest` runs after the response is sent. It calls `rag.ingest_file()` which extracts text from the PDF, splits it into chunks, embeds each chunk with fastembed, and upserts the vectors into Qdrant.
- If ingestion fails for any reason, `status` is set to `"failed"` and the error is logged. The document record remains so the user can retry.
- `async for session in get_async_session()` opens a fresh database session inside the background task - the request session is closed by the time the background task runs.

---

## 7. Test the flow

Restart the dev server, then upload a PDF:

```bash
fas dev
```

In a second terminal:

```bash
TOKEN="eyJhbGci..."  # paste your access_token from Part 3

curl -s -X POST http://127.0.0.1:8000/documents/upload \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/your.pdf" | python -m json.tool
```

You'll see a response like:

```json
{
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "your.pdf",
    "status": "pending",
    "vector_doc_id": null
}
```

Poll the document until `status` changes:

```bash
DOC_ID="3fa85f64-5717-4562-b3fc-2c963f66afa6"

curl -s http://127.0.0.1:8000/documents/$DOC_ID \
     -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

When ingestion completes you'll see `"status": "ingested"` and a `vector_doc_id` matching the document ID. Qdrant is now holding searchable chunks.

If you see `"status": "failed"`, check the dev server log - the error will be printed there with a full traceback.

---

## What you built

- `status` and `vector_doc_id` columns on `Document`, with an Alembic migration to add them
- `docqa/ai/tools/ingestion.py` wiring `RagService` with local fastembed embeddings and Qdrant as a FastAPI dependency
- `POST /documents/upload` accepting PDF files (multipart), protected with JWT, returning 202 immediately
- An `_ingest` background task that extracts text, chunks, embeds, and stores vectors in Qdrant - then writes `"ingested"` or `"failed"` back to the database
- A polling pattern via `GET /documents/{id}` to track ingestion status

---

## Next steps

[Part 5 - Chat Agent with Tools](05-chat-agent.md)

In Part 5 you'll add a chat endpoint: the agent receives a question, searches Qdrant for relevant chunks, and asks the LLM to synthesize an answer - streaming the response back via SSE.
