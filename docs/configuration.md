# Configuration

All settings are defined by subclassing `BaseSettings` in your project's `settings.py`. Values are read from environment variables (prefixed by your project name) and `.env` files.

## Example

```python
from fast_agent_stack.config import BaseSettings
from pydantic_settings import SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYPROJECT_")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str | None = None
    auth_backends: list[str] = ["jwt"]
```

## Core Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `app_name` | `str` | `"fast-agent-stack"` | Application name |
| `debug` | `bool` | `False` | Enable debug mode |
| `database_url` | `str \| None` | `None` | SQLAlchemy async URL |
| `redis_url` | `str \| None` | `None` | Redis/Valkey URL |
| `secret_key` | `str \| None` | `None` | JWT signing key (required when using JWT auth) |
| `auth_backends` | `list[str]` | `[]` | Auth backends: `["jwt"]`, `["session"]`, or `["jwt", "session"]` |

## AI Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `llm_backend` | `str` | `"bedrock"` | LLM backend alias or dotted path |
| `llm_model` | `str` | `"claude-haiku-4-5-20251001"` | Default model ID |
| `llm_timeout` | `float` | `30.0` | Request timeout (seconds) |

## Rate Limiting

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `include_rate_limit` | `bool` | `False` | Enable Redis fixed-window rate limiting |
| `rate_limit_requests` | `int` | `100` | Max requests per window |
| `rate_limit_period` | `int` | `60` | Window size (seconds) |

## Observability

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tracing_enabled` | `bool` | `False` | Enable OpenTelemetry tracing |
| `otel_exporter_endpoint` | `str` | `"http://localhost:4317"` | OTLP gRPC endpoint |

## Email

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `email_backend` | `str` | `"smtp"` | Backend alias or dotted path |
| `smtp_host` | `str` | `"localhost"` | SMTP server host |
| `smtp_port` | `int` | `587` | SMTP server port |
| `smtp_use_tls` | `bool` | `True` | Use STARTTLS |
| `email_from` | `str` | `"noreply@example.com"` | From address |

## Secrets Backend

Controlled by the `SECRETS_BACKEND` environment variable (not a settings field):

| Value | Description |
|-------|-------------|
| `none` (default) | Use environment variables / `.env` only |
| `aws` | AWS Secrets Manager (requires `SECRETS_AWS_SECRET_ID`) |
| `gcp` | GCP Secret Manager (requires `SECRETS_GCP_PROJECT_ID`) |
