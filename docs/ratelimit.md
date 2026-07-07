# Rate Limiting & Observability

## Rate Limiting

fast-agent-stack provides Redis-backed fixed-window rate limiting via `fastapi-redis-sdk`.

```bash
pip install "fast-agent-stack[rate-limit]"
```

### Enable Rate Limiting

```python
class Settings(BaseSettings):
    include_rate_limit: bool = True
    rate_limit_requests: int = 100    # max requests per window
    rate_limit_period: int = 60       # window size in seconds
    redis_url: str = "redis://localhost:6379"
```

Rate limiting is applied globally to all routes when enabled. The limit is per client IP, enforced via a Redis Lua script (atomic INCR + EXPIRE).

### Response Headers

Clients receive standard rate-limit headers on every response:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1751836800
```

When the limit is exceeded, the server returns `429 Too Many Requests`.

## Observability (OpenTelemetry)

fast-agent-stack auto-instruments with OpenTelemetry. Every request generates a trace span with HTTP metadata.

```bash
pip install "fast-agent-stack[tracing]"
```

### Enable Tracing

```python
class Settings(BaseSettings):
    tracing_enabled: bool = True
    otel_exporter_endpoint: str = "http://localhost:4317"   # OTLP gRPC
```

### Jaeger (default backend)

```bash
docker run -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one
```

Open `http://localhost:16686` to view traces.

### Custom Exporter

Set `otel_exporter_endpoint` to any OTLP-compatible backend (Grafana Tempo, Honeycomb, Datadog OTLP endpoint, etc.).

### What Gets Traced

- Every HTTP request (method, path, status code, duration)
- Database queries (SQLAlchemy instrumentation)
- External service calls via the `tracer` context manager

### Adding Custom Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def my_handler():
    with tracer.start_as_current_span("my-operation") as span:
        span.set_attribute("user.id", user_id)
        result = await do_work()
    return result
```
