# Testing the CLI (manual)

## Install (from source)

```bash
uv pip install -e "/Volumes/X10Pro/Work/open_source/fast-agent-stack[db-sqlite,auth-jwt,admin]"
```

## Scaffold a project

```bash
mkdir /tmp/fas-test && cd /tmp/fas-test
uv init && uv pip install -e "/Volumes/X10Pro/Work/open_source/fast-agent-stack[db-sqlite,auth-jwt,admin]"

fas new myproject --preset minimal --db sqlite
fas new myproject --preset standard --db postgres
fas new myproject --preset agent --db postgres
```

## Run the scaffolded app

```bash
fas run              # default main:app
fas run --reload     # with auto-reload
```

## Database + Auth (Phase 2 & 3a)

```bash
fas makemigrations -m "initial"
fas migrate

# Verify — auth tables auto-included when auth-jwt extra is installed
sqlite3 myproject.db ".tables"
# Should show: users, groups, permissions, user_groups, group_permissions,
#              user_permissions, auth_verification_tokens, api_keys,
#              alembic_version

# Create superuser
fas createsuperuser

# Seed (if seeds.py exists)
fas seed
```

## Auth Routes (Phase 3b)

```bash
# Get a token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "yourpassword"}'

# Refresh
curl -X POST http://localhost:8000/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"

# Logout
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

## API Keys & Admin (Phase 3c)

```bash
# Create API key (authenticated as superuser)
curl -X POST http://localhost:8000/api-keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-integration"}'

# Use API key
curl http://localhost:8000/some-endpoint \
  -H "Authorization: Bearer fas_<key>"

# Admin panel (requires admin extra)
# Visit http://localhost:8000/admin
```

## Health checks

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
# /health/ready checks DB + Redis (if configured)
```

## Other commands

```bash
fas version
fas -V
fas update    # re-apply template changes (requires .copier-answers.yml)
```
