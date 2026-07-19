# Part 5 - Chat Agent

> **Series:** [Tutorial index](index.md) · [Part 4](04-ingestion-agent.md) · **You are here:** Part 5 · [Part 6](06-chat-ui.md)

In Part 4 you ingested PDFs into Qdrant. Now you'll build the chat endpoint: the user sends a question, the agent retrieves relevant chunks from the vector store, and the LLM synthesizes a streaming answer.

---

## Choose your agent approach

| Approach | What it is | Pick this when |
|----------|-----------|----------------|
| **Built-in** (below) | fast-agent-stack's `@app.agent()`, `agent_loop`, `@tool` | Simple single-agent, no extra deps, quick to wire up |
| [Strands Agents](../guides/framework-integration/strands-agents.md) | AWS Strands SDK with multi-agent graphs and swarms | Multi-agent orchestration, parallel pipelines, runtime handoffs |
| Pydantic AI *(planned)* | - | Structured output, typed dependency injection |

If you're using Strands or Pydantic AI, follow the linked guide and then skip to [Part 6 - Chat UI](06-chat-ui.md) when done. Otherwise, continue below.

---

## Built-in: `@app.agent()` with tool calling

**By the end of this section** `POST /agents/chat` accepts a question, retrieves document chunks, and streams the answer back as SSE events.

### Prerequisites

- Part 4 complete (documents indexed in Qdrant)
- `.env` has `DOCQA_LLM_BASE_URL`, `DOCQA_LLM_MODEL`, and `DOCQA_LLM_API_KEY` set (configured in Part 0)
- Ollama running with `llama3.2` pulled

---

### 1. Create the chat module

Create `docqa/chat.py`. This file defines the search tool and the agent handler:

```python
from collections.abc import AsyncIterator

from fast_agent_stack.ai import Message, agent_loop, tool
from fast_agent_stack.ai.llm import OpenAILLMBackend
from fast_agent_stack.rag import RagService, get_embedding_provider, get_vector_store

from .ai.tools.ingestion import COLLECTION
from .settings import get_settings

_settings = get_settings()
_rag = RagService(
    embedding=get_embedding_provider(_settings),
    vector_store=get_vector_store(_settings),
)
backend = OpenAILLMBackend(model_id=_settings.llm_model, settings=_settings)


@tool(description="Search uploaded documents for information relevant to the query")
async def search_docs(query: str) -> str:
    try:
        chunks = await _rag.retrieve(COLLECTION, query, top_k=5)
    except Exception as e:
        return f"Error searching documents: {e}"
    if not chunks:
        return "No relevant documents found."
    return "\n\n".join(c.content for c in chunks)


async def chat_handler(
    messages: list[Message],
    *,
    user_id,
    api_key_id,
    conversation_id,
) -> AsyncIterator[str]:
    async for item in agent_loop(backend, messages, tools=[search_docs]):
        yield item
```

A few things to notice:

- `_rag` and `backend` are module-level singletons. They read settings once at startup so there is no per-request overhead constructing clients.
- `@tool` extracts the function signature and generates an OpenAI-compatible tool schema automatically. The `query: str` parameter becomes a required string field in the schema the LLM sees.
- `search_docs` closes over `_rag`, so when the LLM calls it the function has everything it needs.
- `chat_handler` is an async generator. The framework detects this and pipes each yielded string to the SSE response. The trailing `CompletionResult` from `agent_loop` is intercepted and used for usage metering (not sent to the client).

---

### 2. Register the agent

The scaffold already generated `docqa/ai/agents/__init__.py` with a `register_agents` function and an echo stub. Replace its contents with the real chat agent:

```python
from fastapi import Depends

from fast_agent_stack.ai import Message
from fast_agent_stack.auth import get_current_user

from .chat import backend, chat_handler, search_docs


def register_agents(app):
    """Mount all agent routes on *app* (called from app.py after stack creation)."""

    @app.agent("chat", backend, tools=[search_docs], dependencies=[Depends(get_current_user)])
    async def chat(
        messages: list[Message],
        *,
        user_id,
        api_key_id,
        conversation_id,
    ):
        async for item in chat_handler(
            messages,
            user_id=user_id,
            api_key_id=api_key_id,
            conversation_id=conversation_id,
        ):
            yield item
```

Then open `docqa/app.py` and add these two lines after `app.include_router(router)`:

```python
from .ai.agents import register_agents

register_agents(_stack)
```

`@app.agent` mounts a `POST /agents/chat` route automatically. The `tools=[search_docs]` argument tells the framework which tools this agent uses (used for documentation and tracing).

---

### 3. Test the flow

Restart the dev server:

```bash
fas dev
```

In a second terminal, send a question:

```bash
TOKEN="eyJhbGci..."  # your access_token from Part 3

curl -s -X POST http://127.0.0.1:8000/agents/chat \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"messages": [{"role": "user", "content": "What topics are covered in the uploaded documents?"}]}' \
     --no-buffer
```

You'll see SSE events arriving as the LLM streams its response:

```
data: "Based"
data: " on"
data: " the"
data: " documents"
data: " you"
data: " uploaded,"
...
```

Each `data:` line contains a JSON-encoded string token. A client consuming SSE parses and concatenates these to display the full response.

### How the agent loop works

When your request arrives:

1. The LLM receives your question and the `search_docs` tool schema.
2. If the LLM decides to search, it returns a tool call request instead of text. `agent_loop` receives this, calls `search_docs(query="...")`, and appends the result as a `tool` message.
3. The LLM receives the retrieved chunks as context and produces a text response.
4. `agent_loop` yields the text tokens, which stream to the client.

If the LLM answers directly without searching (e.g., for a general knowledge question), step 2 is skipped. If the loop reaches the iteration cap (10 by default), it stops and returns whatever it has.

---

## What you built

- `docqa/chat.py` with a `@tool`-decorated `search_docs` function that retrieves chunks from Qdrant
- A `chat_handler` async generator that delegates to `agent_loop` for LLM-tool dispatch
- `POST /agents/chat` mounted via `@app.agent`, streaming SSE responses

---

## Next steps

[Part 6 - Chat UI](06-chat-ui.md)

In Part 6 you'll add a single-page chat interface: a plain HTML file served by the framework that connects to the SSE endpoint and displays the streaming response in real time.
