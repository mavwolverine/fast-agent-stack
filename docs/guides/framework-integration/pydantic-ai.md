# Pydantic AI Guide

> See [Framework Integration Guides](index.md) for when to reach for a dedicated agent framework at all, and how it fits alongside `@app.agent()`. This page covers what's specific to [Pydantic AI](https://ai.pydantic.dev): typed dependency injection via `deps_type`/`RunContext`, and its multi-agent patterns.

!!! note "Pydantic AI API surface"
    Pydantic AI is a fast-moving external SDK. The import paths and method names below reflect `pydantic-ai` at the time of writing - check the [Pydantic AI documentation](https://ai.pydantic.dev) for the exact current signatures before copying code verbatim.

This guide does not add anything to fast-agent-stack itself. Pydantic AI is wired directly into a plain FastAPI route, alongside (not through) `@app.agent()`, sharing the same database, vector store, storage, and Redis/Valkey instance.

## Getting Started

After [scaffolding your project](index.md), add Pydantic AI as a dependency:

```bash
uv add pydantic-ai
```

Your Pydantic AI code lives in the scaffolded `ai/` package - `ai/agents/`, `ai/tools/`, and `ai/prompts/`.

The scaffolder pre-populates `ai/agents/__init__.py` with a `register_agents()` stub for fast-agent-stack's built-in `@app.agent()`. Since Pydantic AI replaces that, clear it out:

```python
# myproject/ai/agents/__init__.py
"""Agent definitions for myproject."""
```

## Wiring Pydantic AI to FastAPI

A Pydantic AI agent is invoked from a plain `APIRouter` route, not `@app.agent()`. Streaming goes through Starlette's `StreamingResponse` directly.

### 1. Create the search tool

This tool searches your Qdrant vector store using fast-agent-stack's `RagService` - the same retrieval pipeline the built-in tutorial uses. Unlike Strands' module-closure `@tool`, Pydantic AI tools receive dependencies through `RunContext` - the typed `deps` object the agent was run with - which is what makes Pydantic AI's dependency injection different from Strands':

```python
# myproject/ai/tools/search.py
from dataclasses import dataclass

from pydantic_ai import RunContext

from fast_agent_stack.rag import RagService
from myproject.ai.tools.ingestion import COLLECTION


@dataclass
class ChatDeps:
    rag: RagService


async def search_docs(ctx: RunContext[ChatDeps], query: str) -> str:
    """Search uploaded documents for information relevant to the query."""
    try:
        chunks = await ctx.deps.rag.retrieve(COLLECTION, query, top_k=5)
    except Exception as e:
        return f"Error searching documents: {e}"
    if not chunks:
        return "No relevant documents found."
    return "\n\n".join(c.content for c in chunks)
```

`search_docs` is a plain function, not decorated - Pydantic AI inspects its signature (the `RunContext[ChatDeps]` first parameter) when the function is passed to `Agent(tools=[...])` below, the same way it would if `@agent.tool` had decorated it directly.

### 2. Create the agent

`OpenAIChatModel` plus `OpenAIProvider` point at any OpenAI-compatible endpoint - Ollama, a LiteLLM proxy, or a real OpenAI-compatible API - using the same `llm_base_url`/`llm_model`/`llm_api_key` settings fields the built-in `get_llm()` factory reads:

```python
# myproject/ai/agents/chat.py
import json
from collections.abc import AsyncIterator

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from fast_agent_stack.rag import get_embedding_provider, get_vector_store, RagService
from myproject.ai.tools.search import ChatDeps, search_docs
from myproject.settings import get_settings

_settings = get_settings()

_model = OpenAIChatModel(
    _settings.llm_model,
    provider=OpenAIProvider(base_url=_settings.llm_base_url, api_key=_settings.llm_api_key),
)

_deps = ChatDeps(
    rag=RagService(
        embedding=get_embedding_provider(_settings),
        vector_store=get_vector_store(_settings),
    )
)

agent = Agent(
    _model,
    deps_type=ChatDeps,
    tools=[search_docs],
    system_prompt="You are a helpful assistant for the document Q&A app.",
)


async def stream_chat(prompt: str, conversation_id: str) -> AsyncIterator[str]:
    """Run the chat agent and format its events as SSE data lines."""
    async with agent.run_stream(prompt, deps=_deps, conversation_id=conversation_id) as response:
        sent = ""
        async for cumulative in response.stream_text():
            yield f"data: {json.dumps(cumulative[len(sent):])}\n\n"
            sent = cumulative
```

`agent` and `_deps` are built once at import time and reused across every request - unlike Strands' `ValkeySessionManager`, which is bound into the agent at construction time and needs a fresh `Agent` per conversation, Pydantic AI keeps conversation state out of the agent entirely (see [Conversation Persistence](#conversation-persistence) below), so one shared instance is correct here.

`response.stream_text()` yields the *cumulative* text so far on each call, not deltas - the loop above tracks what has already been sent (`sent`) and yields only the new suffix. This is deliberate: `stream_text(delta=True)` yields true deltas, but it also means "the final result message will NOT be added to result messages" per Pydantic AI's own docs - it would silently break the persistence in the next section. Using the default (non-delta) form keeps history tracking intact.

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

This route doesn't use `@app.agent()`, `stream_sse`, or `agent_loop` - Pydantic AI owns the entire request/response cycle.

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

## Using fast-agent-stack Infra from Pydantic AI's Tools

A Pydantic AI tool is a plain async function. It has no request-scoped dependency injection of its own - `Depends(...)` is unreachable from inside one, whether or not the function declares a `RunContext` parameter. Each infra type below needs its own access pattern.

### Database

If you haven't set up database models yet, follow [Part 2 - Database & Models](../../tutorial/02-database-models.md). Then generate and apply the migration:

```bash
fas makemigrations -m "add-documents"
fas migrate
```

If you need to access the database from inside a tool, use `get_async_session()` as an async generator (not as a FastAPI `Depends()`). `DatabaseLifespanHook` initializes the engine automatically at startup in the web process. In a worker process (see [Background Processing](#background-processing-with-dramatiq)), call `configure_engine(settings.database_url)` explicitly at module import time:

```python
# myproject/ai/tools/documents.py
import uuid

from fast_agent_stack.database import get_async_session
from myproject.models import Document


async def get_document(document_id: str) -> dict:
    """Look up a document's metadata by id."""
    async for session in get_async_session():
        doc = await session.get(Document, uuid.UUID(document_id))
        return {"id": str(doc.id), "title": doc.title} if doc else {}
```

`get_document` takes no `RunContext` - Pydantic AI only inspects it looking for one, and doesn't require it. Add it to `Agent(tools=[search_docs, get_document])` the same way as `search_docs`.

### Vector Store

The `search_docs` tool shown above demonstrates vector store access via `RagService`. It uses `get_embedding_provider` and `get_vector_store` from `fast_agent_stack.rag` - there is no top-level `fast_agent_stack.vector` package.

### Storage

```python
# myproject/ai/tools/files.py
from fast_agent_stack.storage import get_storage, KeyNotFoundError
from myproject.settings import get_settings

_settings = get_settings()


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

`AsyncRedisDep` is a FastAPI dependency - it resolves through `request.app.state`, which a Pydantic AI tool doesn't have access to. Use a plain, module-level client instead, built from the same `redis_url` setting:

```python
# myproject/ai/tools/cache.py
from functools import lru_cache

from redis.asyncio import Redis

from myproject.settings import get_settings


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("redis_url must be set in Settings")
    return Redis.from_url(settings.redis_url)
```

This is the same `settings.redis_url` field used for the Dramatiq broker and all of fast-agent-stack's own Redis features - one setting, shared everywhere.

---

## Multi-Agent Patterns

Pydantic AI supports two lighter-weight multi-agent patterns directly on `Agent`: **agent delegation**, where one agent calls another agent as a tool and control returns to the caller when the delegate finishes (pass `ctx.usage` into the delegate's run so token usage rolls up correctly), and **programmatic agent hand-off**, where your own application code decides which agent runs next in sequence. For genuinely complex, cyclic control flow, `pydantic-graph` (available as `from pydantic_graph import ...`) provides a typed graph builder with steps, joins, and decisions - it integrates directly with Pydantic AI's agent loop. See the [Pydantic AI multi-agent documentation](https://ai.pydantic.dev/guides/multi-agent-applications/) and the [Graph documentation](https://ai.pydantic.dev/graph/graph/) for constructing these - fast-agent-stack does not wrap or validate them.

---

## Conversation Persistence

Unlike Strands, Pydantic AI has no bundled session manager - persist conversation history in Redis/Valkey instead, reusing the same instance already running for auth and rate limiting.

### Changes to `myproject/ai/agents/chat.py`

Add these imports at the top:

```python
from pydantic_ai.messages import ModelMessagesTypeAdapter

from myproject.ai.tools.cache import get_redis
```

Reuse the `get_redis()` accessor from [Redis / Valkey](#redis-valkey) above rather than opening a second client - add these helpers after the `agent = Agent(...)` block:

```python
async def _load_history(conversation_id: str):
    data = await get_redis().get(f"chat:{conversation_id}")
    if data is None:
        return []
    return ModelMessagesTypeAdapter.validate_json(data)


async def _save_history(conversation_id: str, messages) -> None:
    blob = ModelMessagesTypeAdapter.dump_json(messages)
    await get_redis().set(f"chat:{conversation_id}", blob)
```

Update `stream_chat` to load history before the run and save after:

```python
async def stream_chat(prompt: str, conversation_id: str) -> AsyncIterator[str]:
    history = await _load_history(conversation_id)
    async with agent.run_stream(prompt, deps=_deps, message_history=history, conversation_id=conversation_id) as response:
        sent = ""
        async for cumulative in response.stream_text():
            yield f"data: {json.dumps(cumulative[len(sent):])}\n\n"
            sent = cumulative
    await _save_history(conversation_id, response.all_messages())
```

`conversation_id` is a plain string key into Redis - if every caller that omits it falls back to the same literal value, every one of those conversations reads and writes the same history, corrupting each other. Generate a fresh id server-side instead of defaulting to a shared placeholder:

```python
# myproject/routes.py (updated: generates a conversation_id on the first turn)
import uuid

from fastapi import Depends
from fastapi.responses import StreamingResponse

from fast_agent_stack.auth import get_current_user
from .ai.agents.chat import stream_chat
from .schemas import ChatRequest


@router.post("/agents/chat")
async def chat(body: ChatRequest, _=Depends(get_current_user)) -> StreamingResponse:
    prompt = body.messages[-1].content if body.messages else ""
    conversation_id = body.conversation_id or str(uuid.uuid4())
    response = StreamingResponse(stream_chat(prompt, conversation_id), media_type="text/event-stream")
    response.headers["X-Conversation-Id"] = conversation_id
    return response
```

Omit `conversation_id` on the first request to start a new conversation - read it back from the `X-Conversation-Id` response header and pass it on every follow-up request to continue that same conversation.

---

## Background Processing with Dramatiq

A Pydantic AI agent runs inside a Dramatiq actor the same way any other async workload does - no special handling needed. See [Part 7 - Background Tasks](../../tutorial/07-background-tasks.md) for the full pattern.
