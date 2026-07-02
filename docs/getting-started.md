# Getting Started

## Installation

```bash
pip install fast-agent-stack
```

For extras:

```bash
pip install "fast-agent-stack[anthropic,auth-jwt,db-postgres]"
```

## Create a Project

```bash
mkdir myproject && cd myproject
uv venv && source .venv/bin/activate
uv pip install fast-agent-stack

fastagentstack new myproject --preset standard
```

The interactive prompt covers database, auth, LLM provider, and deployment options. Use `--preset` to skip prompts for CI environments.

## Run the Dev Server

```bash
cp .env.example .env
# fill in DATABASE_URL, SECRET_KEY, REDIS_URL

fastagentstack migrate
fastagentstack dev      # auto-reload, binds to 127.0.0.1:8000
```

## Production

```bash
fastagentstack run      # multi-worker, binds to 0.0.0.0:8000
```

Or via Docker Compose (generated when `include_docker_compose=true`):

```bash
docker compose up
```

## Adding an Agent

```python
# myproject/agents.py
from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend
from fast_agent_stack.core.ai.llm import Message

_backend = AnthropicLLMBackend(model_id="claude-haiku-4-5-20251001")

def register_agents(app):
    @app.agent("chat", backend=_backend)
    async def chat(messages: list[Message], *, user_id, api_key_id, conversation_id) -> str:
        return f"Echo: {messages[-1].content}"
```

Then in `app.py`:

```python
from .agents import register_agents
register_agents(_stack)
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `fastagentstack new <name>` | Scaffold a new project |
| `fastagentstack dev` | Development server (127.0.0.1, reload) |
| `fastagentstack run` | Production server (0.0.0.0, multi-worker) |
| `fastagentstack migrate` | Apply framework + user migrations |
| `fastagentstack makemigrations` | Generate migration from model changes |
| `fastagentstack worker <module>` | Start Dramatiq worker |
| `fastagentstack scheduler <module>` | Start Periodiq scheduler |
| `fastagentstack createsuperuser` | Create a superuser account |
| `fastagentstack version` | Print version |
