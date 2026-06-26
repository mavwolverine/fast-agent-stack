# Testing the CLI (manual)

## Install (from source)

```bash
uv pip install -e "/Volumes/X10Pro/Work/open_source/fast-agent-stack[db-sqlite,auth-jwt]"
```

## Scaffold a project

```bash
mkdir /tmp/fas-test && cd /tmp/fas-test
uv init && uv pip install -e "/Volumes/X10Pro/Work/open_source/fast-agent-stack[db-sqlite,auth-jwt]"

fas new myproject --preset minimal
fas new myproject --preset api
fas new myproject --preset ai-full
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

# Verify — auth tables auto-included when include_auth is enabled in settings
sqlite3 myproject.db ".tables"
# Should show: users, groups, permissions, user_groups, group_permissions,
#              user_permissions, auth_verification_tokens, api_keys,
#              alembic_version

# Create superuser
fas createsuperuser

# Seed (if seeds.py exists)
fas seed
```

## Health checks

```bash
fas run &
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## Other commands

```bash
fas version
fas -V
fas update    # re-apply template changes (requires .copier-answers.yml)
```
