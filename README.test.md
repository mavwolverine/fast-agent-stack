# Testing the CLI (manual)

## Install (from source)

```bash
uv pip install -e /Volumes/X10Pro/Work/open_source/fast-agent-stack
```

## Scaffold a project

```bash
mkdir /tmp/fas-test && cd /tmp/fas-test
uv init && uv pip install -e /Volumes/X10Pro/Work/open_source/fast-agent-stack

fastagentstack new myproject --preset minimal
fastagentstack new myproject --preset api
fastagentstack new myproject --preset ai-full
```

## Run the scaffolded app

```bash
# Default — uses main:app (reads main.py)
fastagentstack run

# Explicit import string
fastagentstack run main:app

# With reload
fastagentstack run --reload
```

**Note:** Don't pass the package dir directly (`fastagentstack run myproject`) — use import strings.

## Other commands

```bash
fastagentstack version
fastagentstack -V
```
