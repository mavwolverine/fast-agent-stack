# Migration & Upgrade Guide

## Upgrading fast-agent-stack

```bash
pip install --upgrade fast-agent-stack
fastagentstack migrate   # always run after upgrading
```

Migrations are append-only and idempotent. Running `migrate` on an up-to-date database is a no-op.

## Database Migrations

fast-agent-stack manages its own tables (users, tokens, conversations, usage logs) via Alembic. Your project's model migrations are separate.

### Framework migrations

Applied automatically by `fastagentstack migrate`. Do not edit these files.

### Project migrations

```bash
# Generate a migration from your model changes
fastagentstack makemigrations "add product table"

# Apply
fastagentstack migrate
```

### Reversing a migration

```bash
alembic downgrade -1
```

All framework migrations include `downgrade()` functions.

## 0.x → 1.0 (future)

This section will document breaking changes when 1.0 is released. No breaking changes are planned for the 0.x series.

## Redis Schema Changes

Redis keys are namespaced by purpose:

| Prefix | Contents |
|--------|---------|
| `fas:jti:` | JWT JTI denylist entries |
| `fas:session:` | Session data |
| `fas:rate:` | Rate limit counters |

Key formats are stable within a minor version. A major version bump may change the prefix.

## Settings Renames

When a setting is renamed between versions, the old name is kept as a deprecated alias for one minor version before removal. Check the CHANGELOG for specifics.

## Template Updates

To update a scaffolded project after upgrading the framework:

```bash
cd myproject
copier update --trust
```

Review the diff carefully — copier will show what changed.
