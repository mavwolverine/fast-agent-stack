# Part 7 - Background Tasks

> **Series:** [Tutorial index](index.md) · [Part 6](06-chat-ui.md) · **You are here:** Part 7 · [Part 8](08-production.md)

In Part 4 you wired PDF ingestion into a FastAPI `BackgroundTask`. That runs in the same process as the web server - if ingestion is slow or crashes, it blocks the event loop and takes the web server down with it. In Part 7 you replace it with a Dramatiq actor running in a separate worker process. The web server stays responsive; the worker can be restarted independently; and you get a periodic task that re-checks stale documents on a schedule.

**By the end of this part** uploads enqueue a Dramatiq message and return immediately. A separate worker process handles extraction, embedding, and vector storage. A periodiq scheduler fires a re-index check every hour.

---

## Prerequisites

- Part 6 complete (chat UI working)
- Valkey/Redis running on port 6379 (the same instance from Part 0)

---

## 1. Install the scheduler extra

The `agent` preset already includes `fast-agent-stack[tasks]` (Dramatiq) in the generated `pyproject.toml`, so it was installed when you ran `uv pip install -r pyproject.toml` in Part 1. You only need to add `periodiq` for the scheduler:

```bash
uv pip install "fast-agent-stack[scheduler]"
```

---

## 2. Replace the scaffold placeholder in `docqa/tasks.py`

The `agent` preset already generated `docqa/tasks.py` with an `example_task` stub. Replace the entire file with the ingestion actor and periodic re-index task:

```python
import asyncio
import logging
import os
import uuid

import dramatiq
from periodiq import PeriodiqMiddleware, cron

from fast_agent_stack.database import configure_engine, get_async_session
from fast_agent_stack.rag import RagService, get_embedding_provider, get_vector_store
from fast_agent_stack.tasks import configure_broker

from .ingestion import COLLECTION
from .models import Document
from .settings import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

# Wire Dramatiq to Redis and initialize the database engine once, when the
# worker process imports this module.
_broker = configure_broker(_settings)
_broker.add_middleware(PeriodiqMiddleware(skip_delay=30))
configure_engine(_settings.database_url)


@dramatiq.actor(queue_name="ingestion")
def ingest_document(doc_id: str, file_path: str, filename: str, content_type: str) -> None:
    """Dramatiq actor: extract, embed, and store a PDF in Qdrant."""
    asyncio.run(_ingest_async(doc_id, file_path, filename, content_type))


async def _ingest_async(doc_id: str, file_path: str, filename: str, content_type: str) -> None:
    rag = RagService(
        embedding=get_embedding_provider(_settings),
        vector_store=get_vector_store(_settings),
    )

    with open(file_path, "rb") as f:
        data = f.read()
    os.unlink(file_path)

    status = "ingested"
    vector_doc_id = None
    try:
        result = await rag.ingest_file(
            COLLECTION,
            data,
            filename=filename,
            content_type=content_type,
            document_id=doc_id,
            metadata={"filename": filename},
        )
        vector_doc_id = result.document_id
    except Exception:
        logger.exception("Ingestion failed for document %s", doc_id)
        status = "failed"

    async for session in get_async_session():
        doc = await session.get(Document, uuid.UUID(doc_id))
        if doc is not None:
            doc.status = status
            doc.vector_doc_id = vector_doc_id
            await session.commit()


@dramatiq.actor(periodic=cron("0 * * * *"))
def reindex_stale() -> None:
    # Exercise for the reader: query documents with status="pending"
    # older than one hour and re-enqueue them via ingest_document.send().
    logger.info("Periodic re-index check triggered")
```

A few things to notice:

- **`configure_broker` and `configure_engine` at module level**: both are called once when the worker imports `docqa.tasks`. By the time `_ingest_async` runs, the database engine is already initialized and `get_async_session()` is ready to use.
- **Why `asyncio.run()` in the actor**: Dramatiq actors are plain synchronous functions - the worker process is not inside any async event loop. `asyncio.run()` creates a fresh event loop for each actor invocation, which is the correct pattern.
- **`file_path` not `bytes`**: Dramatiq serializes actor arguments as JSON. Raw `bytes` are not JSON-serializable. Instead the route saves the file to a temp path and passes the path string; the actor reads the file and deletes it after use.
- **`PeriodiqMiddleware`**: required for the `@dramatiq.actor(periodic=...)` decorator to work. `skip_delay=30` lets the scheduler fire the first run 30 seconds after startup instead of waiting for the first cron interval.

---

## 3. Update the upload route

Open `docqa/routes.py`. The upload endpoint loses two parameters compared to Part 4: `BackgroundTasks` (no longer needed - the actor handles it) and `rag: RagService = Depends(get_rag_service)` (the worker constructs its own `RagService` directly, since FastAPI dependencies only work inside request handlers). It saves the uploaded file to a temp path and enqueues the actor:

```python
import tempfile

from .tasks import ingest_document


@router.post("/documents/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    file: UploadFile,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Document:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are supported")

    data = await file.read()
    doc = Document(title=file.filename or "Untitled", status="pending")
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    ingest_document.send(str(doc.id), tmp_path, file.filename or "upload.pdf", file.content_type or "application/pdf")
    return doc
```

Also remove from `routes.py`: the `BackgroundTasks` import, the `get_rag_service` import, and the `_ingest` helper function - all replaced by `docqa/tasks.py`.

---

## 4. Run three processes

You now need three terminal windows:

```bash
# Terminal 1 - web server
fas dev
```

```bash
# Terminal 2 - Dramatiq worker
fas worker docqa.tasks
```

```bash
# Terminal 3 - periodiq scheduler (optional in development)
fas scheduler docqa.tasks
```

`fas worker docqa.tasks` imports `docqa.tasks`, which calls `configure_broker` to connect to Redis, then processes messages from the `ingestion` queue. `fas scheduler docqa.tasks` imports the same module and fires actors marked with `periodic=cron(...)` on schedule.

---

## 5. Test the flow

Open `http://127.0.0.1:8000` in a browser, log in, and upload a PDF using the chat UI from Part 6.

The upload returns immediately - the document card shows `"pending"`. Switch to Terminal 2 and watch the worker log; you will see the ingestion run and `"ingested"` written back to the database. Switch back to the browser and ask a question about the PDF - the agent should retrieve relevant chunks and stream an answer.

**Decoupling in action:** stop the worker (`Ctrl-C` in Terminal 2) and upload another PDF. The upload still returns 202 immediately - the message is sitting in Redis. Restart the worker; it picks up the queued message and ingests the file without any intervention from the web server. The web server never stalled.

---

## What you built

- `fast_agent_stack/tasks/__init__.py` (already part of the framework) - public `configure_broker` that wires Dramatiq to Redis
- `docqa/tasks.py` with an `ingest_document` Dramatiq actor and a `reindex_stale` periodic task
- Updated `POST /documents/upload` that enqueues via `.send()` instead of running ingestion in-process
- `fas worker` and `fas scheduler` CLI commands to run the worker and scheduler processes

---

## Next steps

[Part 8 - Production](08-production.md)

In Part 8 you will add rate limiting to the chat endpoint, wire up OpenTelemetry tracing with Jaeger, and package everything in a Docker Compose file ready for deployment.
