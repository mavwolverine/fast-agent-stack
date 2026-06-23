# Developer Guide

## Setup

```bash
uv sync --group dev
```

## Tests

```bash
uv run pytest                  # run all tests
uv run pytest -x               # stop on first failure
uv run pytest --cov            # with coverage (fails under 80%)
uv run pytest tests/test_cli.py  # single file
```

## Linting & Formatting

```bash
./scripts/lint.sh              # check (ruff check + format --check)
./scripts/format.sh            # auto-fix (ruff check --fix + format)
```

Or manually:

```bash
uv run ruff check fast_agent_stack/ tests/
uv run ruff format fast_agent_stack/ tests/
```

## Type Checking

```bash
uv run mypy fast_agent_stack/
```

## Multi-version Testing (tox)

```bash
uv run tox
```
