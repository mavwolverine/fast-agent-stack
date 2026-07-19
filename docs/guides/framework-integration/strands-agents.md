# Strands Agents Guide

> See [Framework Integration Guides](index.md) for when to reach for a dedicated agent framework at all, and how it fits alongside `@app.agent()`. This page covers what's specific to [AWS Strands Agents](https://strandsagents.com): its multi-agent primitives (`GraphBuilder`, `Swarm`), tool-calling loop, and Valkey-backed session management.

!!! note "Strands API surface"
    Strands is a fast-moving external SDK. The import paths and method names below reflect `strands-agents` at the time of writing - check the [Strands documentation](https://strandsagents.com) for the exact current signatures before copying code verbatim.

This guide does not add anything to fast-agent-stack itself. Strands is wired directly into a plain FastAPI route, alongside (not through) `@app.agent()`, sharing the same database, vector store, storage, and Redis/Valkey instance.

## Getting Started

After [scaffolding your project](index.md), add Strands as a dependency:

```bash
uv add "strands-agents[litellm]" strands-valkey-session-manager
```

Your Strands code lives in the scaffolded `ai/` package - `ai/agents/`, `ai/tools/`, and `ai/prompts/`.

The scaffolder pre-populates `ai/agents/__init__.py` with a `register_agents()` stub for fast-agent-stack's built-in `@app.agent()`. Since Strands replaces that, clear it out:

```python
# myproject/ai/agents/__init__.py
"""Agent definitions for myproject."""
```

## Wiring Strands to FastAPI

A Strands agent is invoked from a plain `APIRouter` route, not `@app.agent()`. Streaming goes through Starlette's `StreamingResponse` directly.

### 1. Create the search tool

This tool searches your Qdrant vector store using fast-agent-stack's `RagService` - the same retrieval pipeline the built-in tutorial uses, just with Strands' `@tool` decorator instead:

```python
# myproject/ai/tools/search.py
from strands import tool

from fast_agent_stack.rag import RagService, get_embedding_provider, get_vector_store

from myproject.ai.tools.ingestion import COLLECTION
from myproject.settings import get_settings

_settings = get_settings()
_rag = RagService(
    embedding=get_embedding_provider(_settings),
    vector_store=get_vector_store(_settings),
)


@tool
async def search_docs(query: str) -> str:
    """Search uploaded documents for information relevant to the query."""
    try:
        chunks = await _rag.retrieve(COLLECTION, query, top_k=5)
    except Exception as e:
        return f"Error searching documents: {e}"
    if not chunks:
        return "No relevant documents found."
    return "\n\n".join(c.content for c in chunks)
```

### 2. Create the agent

The agent uses `LiteLLMModel` (reads LLM settings from your `.env`) and `ValkeySessionManager` (maintains conversation history in Valkey so the frontend only sends the latest message):

```python
# myproject/ai/agents/chat.py
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands_valkey_session_manager import ValkeySessionManager

import json
import valkey
from collections.abc import AsyncIterator

from myproject.ai.tools.search import search_docs
from myproject.settings import get_settings

_settings = get_settings()
_valkey_client = valkey.Valkey.from_url(_settings.redis_url, decode_responses=True)


def build_chat_agent(conversation_id: str) -> Agent:
    model = LiteLLMModel(
        model_id=f"openai/{_settings.llm_model}",
        params={
            "api_key": _settings.llm_api_key,
            "api_base": _settings.llm_base_url,
        },
    )
    session_manager = ValkeySessionManager(
        session_id=conversation_id,
        client=_valkey_client,
    )
    return Agent(
        model=model,
        tools=[search_docs],
        system_prompt="You are a helpful assistant for the document Q&A app.",
        session_manager=session_manager,
    )


async def stream_chat(prompt: str, conversation_id: str) -> AsyncIterator[str]:
    """Run the chat agent and format its events as SSE data lines."""
    agent = build_chat_agent(conversation_id)
    async for event in agent.stream_async(prompt):
        if "data" in event:
            yield f"data: {json.dumps(event['data'])}\n\n"
```

### 3. Add the schema and route

```python
# myproject/schemas.py (add these classes)
from pydantic import BaseModel


class _MessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[_MessageIn]
    conversation_id: str | None = None
```

```python
# myproject/routes.py (add this route)
from fastapi import Depends
from fastapi.responses import StreamingResponse

from fast_agent_stack.auth import get_current_user
from .ai.agents.chat import stream_chat
from .schemas import ChatRequest


@router.post("/agents/chat")
async def chat(body: ChatRequest, _=Depends(get_current_user)) -> StreamingResponse:
    prompt = body.messages[-1].content if body.messages else ""
    return StreamingResponse(
        stream_chat(prompt, body.conversation_id or "default"),
        media_type="text/event-stream",
    )
```

This route doesn't use `@app.agent()`, `stream_sse`, or `agent_loop` - Strands owns the entire request/response cycle.

### 4. Test it

Restart the dev server and send a question:

```bash
fas dev
```

```bash
TOKEN="eyJhbGci..."  # your access_token from Part 3

curl -s -X POST http://127.0.0.1:8000/agents/chat \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"messages": [{"role": "user", "content": "What topics are covered in the uploaded documents?"}], "conversation_id": "test-session-1"}' \
     --no-buffer
```

You'll see SSE events streaming as the agent responds. If the agent decides to search your documents, it calls `search_docs` automatically - you'll see the tool invocation in the dev server logs.

---

## Using fast-agent-stack Infra from Strands Tools

A Strands `@tool`-decorated function is a plain async function. It is **not** a FastAPI route handler, so it has no request-scoped dependency injection - anything gated behind `Depends(...)` is unreachable from inside a tool. Each infra type below needs its own access pattern.

### Database

If you haven't set up database models yet, follow [Part 2 - Database & Models](../../tutorial/02-database-models.md). Then generate and apply the migration:

```bash
fas makemigrations -m "add-documents"
fas migrate
```

If you need to access the database from inside a Strands tool, use `get_async_session()` as an async generator (not as a FastAPI `Depends()`). `DatabaseLifespanHook` initializes the engine automatically at startup in the web process. In a worker process (see [Background Processing](#background-processing-with-dramatiq)), call `configure_engine(settings.database_url)` explicitly at module import time.

### Vector Store

The `search_docs` tool shown above demonstrates vector store access via `RagService`. It uses `get_embedding_provider` and `get_vector_store` from `fast_agent_stack.rag` - there is no top-level `fast_agent_stack.vector` package.

### Storage

```python
from strands import tool

from fast_agent_stack.storage import get_storage, KeyNotFoundError
from myproject.settings import get_settings

_settings = get_settings()


@tool
async def read_uploaded_file(key: str) -> str:
    """Read the raw bytes of an uploaded file by storage key."""
    storage = get_storage(_settings)
    try:
        data = await storage.download(key)
    except KeyNotFoundError:
        return ""
    return data.decode("utf-8", errors="replace")
```

### Redis / Valkey

`AsyncRedisDep` is a FastAPI dependency - it resolves through `request.app.state`, which a Strands tool doesn't have access to. Use a plain, module-level client instead, built from the same `redis_url` setting:

```python
from functools import lru_cache

from redis.asyncio import Redis

from myproject.settings import get_settings


@lru_cache
def _redis() -> Redis:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("redis_url must be set in Settings")
    return Redis.from_url(settings.redis_url)
```

This is the same `settings.redis_url` field used for the Dramatiq broker, the `ValkeySessionManager` client, and all of fast-agent-stack's own Redis features - one setting, shared everywhere.

---

## Multi-Agent Patterns

For orchestration beyond a single agent, Strands provides `GraphBuilder` (fixed, parallelizable pipelines) and `Swarm` (runtime handoffs between specialists). Neither requires anything special on the fast-agent-stack side: a `Graph` or `Swarm` object is wired into a route and reaches your infra from its tools the exact same way a plain `Agent` does, everywhere else in this guide. See the [Strands documentation](https://strandsagents.com) for constructing and running them.

---

## Background Processing with Dramatiq

A Strands agent runs inside a Dramatiq actor the same way any other async workload does - no special handling needed. See [Part 7 - Background Tasks](../../tutorial/07-background-tasks.md) for the full pattern.

---

## Valkey Requirements

`ValkeySessionManager` requires the **Valkey JSON module** (`JSON.GET` / `JSON.SET` commands). A plain Redis or Valkey image does not include this. Use `valkey/valkey-extensions` in your docker-compose:

```yaml
valkey:
  image: valkey/valkey-extensions:latest
  ports:
    - "6379:6379"
  healthcheck:
    test: ["CMD", "valkey-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 5
```

The connection URL (`redis://localhost:6379`) stays the same - Valkey is wire-compatible with Redis.
