# Scaffolder Implementation

The primary entry point is an interactive CLI that generates a project tailored to the user's choices. No dead code, no unused dependencies.

## Implementation: Copier + Typer

```
fast_agent_stack/
├── cli/
│   ├── new.py               # fastagentstack new — interactive prompts + copier
│   └── ...
└── template/                # Copier template (Jinja2)
    ├── copier.yml
    ├── {{project_name}}/
    │   ├── pyproject.toml.jinja
    │   ├── settings.py.jinja
    │   ├── manage.py
    │   ├── apps/
    │   │   └── {{default_app}}/
    │   │       ├── routes.py.jinja
    │   │       ├── models.py.jinja
    │   │       ├── schemas.py.jinja
    │   │       ├── agents.py.jinja   # {% if llm_provider != "none" %}
    │   │       └── tasks.py.jinja    # {% if task_broker != "none" %}
    │   ├── alembic/
    │   │   ├── env.py.jinja
    │   │   └── versions/
    │   ├── docker-compose.yml.jinja  # {% if include_docker_compose %}
    │   ├── Dockerfile.jinja          # {% if include_dockerfile %}
    │   ├── k8s/                      # {% if include_k8s %}
    │   └── .env.example.jinja
    └── .copier-answers.yml
```

## Key Behaviors

- Files only generated when the feature is selected
- `pyproject.toml` only includes chosen dependencies
- `docker-compose.yml` only includes chosen services (postgres, qdrant, redis, etc.). When
  `task_broker != "none"`, a `worker` service must also be included that runs
  `fastagentstack worker apps.{default_app}.tasks` and depends on the broker service.
- Settings class only has fields for enabled features
- The generated `Dockerfile` uses `python:{python_version}-slim` — the version matches the
  `python_version` copier answer, not a hardcoded value.
- **Lifespan hook registration order** (see Invariant I9): the generated `app.py` always registers
  hooks in this sequence: `DatabaseLifespanHook` → `AuthLifespanHook` (if `include_auth`) →
  `AdminLifespanHook` (if `include_admin`) → `TracingLifespanHook` (if `tracing == "jaeger"`) →
  `RateLimitLifespanHook` (if `include_rate_limit`). Any hook that depends on the database must
  follow `DatabaseLifespanHook`.

## copier.yml Question Definitions

```yaml
project_name:
  type: str
  help: Project name

description:
  type: str
  help: Short project description (used in pyproject.toml)
  default: ""

default_app:
  type: str
  help: Name of the default app module (e.g. chat, api, main)
  default: chat

db:
  type: str
  choices:
    PostgreSQL: postgres
    MySQL: mysql
    SQLite: sqlite
    MSSQL: mssql
  default: postgres

llm_provider:
  type: str
  choices:
    AWS Bedrock: bedrock
    OpenAI: openai
    Anthropic: anthropic
    LiteLLM Proxy: litellm
    None: none
  default: bedrock

vector_db:
  type: str
  choices:
    Qdrant: qdrant
    pgvector: pgvector
    OpenSearch: opensearch
    Weaviate: weaviate
    None: none
  default: qdrant

embedding_provider:
  type: str
  choices:
    AWS Bedrock: bedrock
    OpenAI: openai
    Local: local
    None: none
  default: bedrock
  when: "{{ vector_db != 'none' }}"

storage_backend:
  type: str
  choices:
    S3: s3
    Local filesystem: local
    MinIO: minio
    None: none
  default: s3

task_broker:
  type: str
  choices:
    Redis/Valkey: redis
    None: none
  default: redis

include_scheduler:
  type: bool
  default: true
  when: "{{ task_broker != 'none' }}"

include_auth:
  type: bool
  default: true

auth_method:
  type: str
  choices:
    JWT: jwt
    Session: session
    Both: both
  default: jwt
  when: "{{ include_auth }}"

include_email:
  type: bool
  default: false
  when: "{{ include_auth }}"
  help: Include SMTP email support (password reset, email verification) — requires fast-agent-stack[email-smtp]

include_admin:
  type: bool
  default: true

tracing:
  type: str
  choices:
    Jaeger + OpenTelemetry: jaeger
    None: none
  default: jaeger

include_rate_limit:
  type: bool
  default: false
  help: Add Redis-backed per-IP rate limiting (requires redis_url)

secrets_backend:
  type: str
  choices:
    None: none
    AWS Secrets Manager: aws
    GCP Secret Manager: gcp
  default: none
  help: Cloud secrets manager backend (adds extras to pyproject.toml; runtime config via SECRETS_BACKEND env var)

include_dockerfile:
  type: bool
  default: true

include_docker_compose:
  type: bool
  default: true

include_k8s:
  type: bool
  default: false

python_version:
  type: str
  choices:
    - "3.11"
    - "3.12"
    - "3.13"
  default: "3.12"
  help: Python version for the generated Dockerfile
```

## Preset Definitions

```python
PRESETS = {
    "ai-full": {
        "default_app": "chat",
        "db": "postgres",
        "llm_provider": "bedrock",
        "vector_db": "qdrant",
        "embedding_provider": "bedrock",
        "storage_backend": "s3",
        "task_broker": "redis",
        "include_scheduler": True,
        "include_auth": True,
        "auth_method": "jwt",
        "include_email": False,
        "include_admin": True,
        "include_rate_limit": False,
        "secrets_backend": "none",
        "tracing": "jaeger",
        "include_dockerfile": True,
        "include_docker_compose": True,
        "include_k8s": False,
    },
    "api": {
        "default_app": "api",
        "db": "postgres",
        "llm_provider": "none",
        "vector_db": "none",
        "embedding_provider": "none",
        "storage_backend": "none",
        "task_broker": "none",
        "include_auth": True,
        "auth_method": "jwt",
        "include_email": False,
        "include_admin": True,
        "include_rate_limit": False,
        "secrets_backend": "none",
        "tracing": "none",
        "include_dockerfile": True,
        "include_docker_compose": True,
        "include_k8s": False,
    },
    "minimal": {
        "default_app": "main",
        "db": "sqlite",
        "llm_provider": "none",
        "vector_db": "none",
        "embedding_provider": "none",
        "storage_backend": "local",
        "task_broker": "none",
        "include_auth": False,
        "include_email": False,
        "include_admin": False,
        "include_rate_limit": False,
        "secrets_backend": "none",
        "tracing": "none",
        "include_dockerfile": False,
        "include_docker_compose": False,
        "include_k8s": False,
    },
}
```
