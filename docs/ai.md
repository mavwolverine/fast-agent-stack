# AI Module & Agents

fast-agent-stack provides a thin, protocol-based abstraction over LLM providers. Each provider is behind an optional extra; swap backends by changing a setting, not your code.

## The `@app.agent()` Decorator

Register a handler function as an agent endpoint:

```python
from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend
from fast_agent_stack.core.ai.llm import Message

_llm = AnthropicLLMBackend(model_id="claude-haiku-4-5-20251001")

# Non-streaming: return a string
@app.agent("ask", backend=_llm)
async def ask(messages: list[Message], *, user_id, api_key_id, conversation_id) -> str:
    result = await _llm.complete(messages)
    return result.content

# Streaming: yield strings → SSE stream
@app.agent("stream", backend=_llm)
async def stream_chat(messages: list[Message], *, user_id, api_key_id, conversation_id):
    async for chunk in _llm.stream(messages):
        yield chunk
```

Both are reachable at `POST /agents/{name}`.

## LLM Backends

### Anthropic

```bash
pip install "fast-agent-stack[anthropic]"
```

```python
from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend

llm = AnthropicLLMBackend(model_id="claude-sonnet-4-6")
result = await llm.complete(messages)
```

### OpenAI

```bash
pip install "fast-agent-stack[openai]"
```

```python
from fast_agent_stack.core.ai.llm.openai import OpenAILLMBackend

llm = OpenAILLMBackend(model_id="gpt-4o-mini")
```

### AWS Bedrock

```bash
pip install "fast-agent-stack[bedrock]"
```

```python
from fast_agent_stack.core.ai.llm.bedrock import BedrockLLMBackend

llm = BedrockLLMBackend(model_id="anthropic.claude-haiku-4-5-20251001-v1:0")
```

### LiteLLM Proxy

```bash
pip install "fast-agent-stack[litellm]"
```

```python
from fast_agent_stack.core.ai.llm.litellm import LiteLLMLLMBackend

llm = LiteLLMLLMBackend(model_id="gpt-4o")
```

## Message Format

```python
from fast_agent_stack.core.ai.llm import Message

messages = [
    Message(role="system", content="You are a helpful assistant."),
    Message(role="user", content="What is fast-agent-stack?"),
]
```

## Streaming SSE

Agents that use `yield` automatically return `text/event-stream` responses. The client receives incremental chunks as SSE events, with a final `CompletionResult` sentinel.

```javascript
const es = new EventSource("/agents/stream", {method: "POST", ...});
es.onmessage = (e) => console.log(e.data);
```

## Token Metering

Token usage is logged automatically per agent call. Query it:

```python
from fast_agent_stack.core.ai.usage import UsageService

svc = UsageService(db_session)
stats = await svc.get_usage(user_id=42, period="day")
# {"total_input_tokens": 1234, "total_output_tokens": 567, "total_cost": 0.002}
```

## Escape Hatch (I4)

Access the underlying provider client directly via `backend._client`.
