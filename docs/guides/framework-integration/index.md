# Framework Integration Guides

fast-agent-stack's built-in `@app.agent()` decorator covers the simple case: one agent, one `LLMBackend`, request in and response out. It's the equivalent of FastAPI's own `BackgroundTasks` - convenient, no extra dependency, fine until your workload outgrows it.

A dedicated agentic framework - multi-agent graphs, swarms with handoffs, a real tool-calling loop, its own session/state management - is a different tool for a different job. When a project needs that, wiring one in is "graduate to a real agent framework," the same move as replacing an in-process `BackgroundTasks` call with a Dramatiq actor once background work gets serious.

These guides do not add anything to fast-agent-stack itself. Each framework is wired directly into a plain FastAPI route, alongside (not through) `@app.agent()`. Everything in them is application code you write in your own project - fast-agent-stack's role is the infrastructure the framework's tools reach into: the database, vector store, storage, and Redis/Valkey it already gives you.

## When to Use Which

| | `@app.agent()` | A dedicated agent framework |
|---|---|---|
| Single agent, one model call per turn | Yes | Overkill |
| Automatic token metering (`UsageService`) | Yes, built in | Manual - map the framework's own usage data onto `CompletionResult` yourself |
| Multi-agent graphs / swarms | No | Yes |
| Own tool-calling loop, iteration control | `agent_loop` (ADR-046) | The framework's own loop |
| Conversation persistence | `ConversationLog` (DB-backed) | The framework's own session manager, pointed at your infra |

## Getting Started

Scaffold a project with an LLM provider configured - the `agent` preset (Bedrock + Qdrant + S3 + everything in `full`) is the fastest path, but any preset with `llm_provider` set to something other than `none` works:

```bash
mkdir myproject && cd myproject
uv venv && source .venv/bin/activate
uv pip install fast-agent-stack

fastagentstack new myproject --preset agent
uv pip install -r pyproject.toml
fas migrate
```

This already scaffolds an `ai/` package inside your generated project, with empty `agents/`, `tools/`, and `prompts/` sub-packages ready to hold your own code:

```
myproject/
└── myproject/               # fast-agent-stack generated package
    ├── app.py
    ├── settings.py
    ├── models.py
    ├── schemas.py
    ├── routes.py
    ├── tasks.py              # generated when task_broker != "none"
    └── ai/                   # generated when llm_provider != "none"
        ├── agents/           # Agent/Graph/Swarm construction
        ├── tools/            # @tool-decorated functions
        └── prompts/          # System prompts, few-shot examples
```

A dedicated agent framework's code lives in these same directories - there's no separate top-level package to create. If a project uses both `@app.agent()` and an external framework, keep them apart by module name (e.g. `ai/agents/chat.py` for the simple case, `ai/agents/strands_chat.py` for a Strands-backed one) rather than by directory. Each framework is not a fast-agent-stack extra - add it to your own project's dependencies the same way you would any other application-level package (see each guide below for the exact package name).

## Guides

| Guide | Framework | Covers |
|---|---|---|
| [Strands Agents](strands-agents.md) | [AWS Strands Agents](https://strandsagents.com) | Multi-agent graphs (`GraphBuilder`), swarms with handoffs (`Swarm`), Valkey-backed sessions |
| [Pydantic AI](pydantic-ai.md) | [Pydantic AI](https://ai.pydantic.dev) | Typed dependency injection (`RunContext`/`deps_type`), agent delegation, programmatic hand-off |

Each guide covers: project structure, wiring the framework to a FastAPI route, using fast-agent-stack's infra (DB sessions, vector store, storage, Redis) from inside the framework's tools, and where the framework's own session/persistence layer fits alongside fast-agent-stack's.

!!! tip "Want a working example?"
    Follow the [Tutorial](../../tutorial/index.md) through Part 4, then come back here for [Part 5](../../tutorial/05-chat-agent.md) to wire up your chosen agent framework with a real project already in place.
