# Background Tasks & Scheduling

## Background Tasks (Dramatiq)

fast-agent-stack uses Dramatiq with a Redis broker for background task processing.

```bash
pip install "fast-agent-stack[tasks]"
```

### Configure the Broker

```python
from fast_agent_stack.core.tasks import configure_broker
from myproject.settings import get_settings

broker = configure_broker(get_settings())
```

`configure_broker` reads `tasks_broker_url` from settings, falling back to `redis_url`.

### Define Tasks

```python
import dramatiq
from fast_agent_stack.core.tasks import configure_broker

configure_broker(settings)

@dramatiq.actor
def send_welcome_email(user_id: int) -> None:
    ...

@dramatiq.actor(queue_name="high-priority")
def process_document(doc_id: str) -> None:
    ...
```

### Enqueue Tasks

```python
send_welcome_email.send(user_id)
process_document.send_with_options(args=(doc_id,), delay=5000)
```

### Start a Worker

```bash
fastagentstack worker myproject.tasks
```

Or via the CLI alias:

```bash
fas worker myproject.tasks
```

## Scheduling (Periodiq)

Periodiq adds cron-style scheduling on top of Dramatiq.

```bash
pip install "fast-agent-stack[scheduler]"
```

### Define Periodic Tasks

```python
import periodiq

@dramatiq.actor
@periodiq.cron("*/15 * * * *")   # every 15 minutes
def refresh_cache() -> None:
    ...
```

### Start the Scheduler

```bash
fastagentstack scheduler myproject.tasks
```

## Settings

```python
class Settings(BaseSettings):
    tasks_broker_url: str | None = None   # defaults to redis_url
    redis_url: str = "redis://localhost:6379"
```

## Worker Concurrency

Pass Dramatiq worker flags via the CLI:

```bash
fas worker myproject.tasks --processes 2 --threads 8
```
