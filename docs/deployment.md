# Deployment

## Docker

The `standard`, `full`, and `agent` presets generate a `Dockerfile` and `docker-compose.yml`.

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[db-postgres,auth-jwt]"
COPY . .
CMD ["fastagentstack", "run"]
```

### Docker Compose

```bash
docker compose up          # starts app + postgres + redis
docker compose exec app fastagentstack migrate
```

## Environment Variables

All settings map to environment variables. Set `DATABASE_URL`, `REDIS_URL`, and `SECRET_KEY` at minimum:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@db/myapp
REDIS_URL=redis://redis:6379
SECRET_KEY=your-secret-key-here
```

Use a `.env` file locally; inject via your platform in production.

## Production Server

```bash
fastagentstack run
# or
uvicorn myproject.main:app --workers 4 --host 0.0.0.0 --port 8000
```

`fastagentstack run` calls `uvicorn.run()` with multi-worker mode and binds to `0.0.0.0`.

## Kubernetes

The `full` and `agent` presets can generate K8s manifests with `include_k8s=true`:

```
k8s/
  deployment.yaml
  service.yaml
  configmap.yaml
```

Update `configmap.yaml` with your environment variables, then:

```bash
kubectl apply -f k8s/
```

## Health Checks

Use the built-in health endpoints for readiness/liveness probes:

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
```

`/health/live` → always 200 (process is up).
`/health/ready` → 200 if DB + Redis are reachable, 503 otherwise.

## Secrets Management

### AWS Secrets Manager

```bash
export SECRETS_BACKEND=aws
export SECRETS_AWS_SECRET_ID=myapp/prod
export SECRETS_AWS_REGION=us-east-1
```

### GCP Secret Manager

```bash
export SECRETS_BACKEND=gcp
export SECRETS_GCP_PROJECT_ID=my-project
```

Secrets are merged with env vars; env vars take precedence.

## Migrations at Deploy Time

Run migrations as a pre-deploy step or init container:

```bash
fastagentstack migrate
```

This is idempotent — safe to run on every deploy.
