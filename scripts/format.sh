#!/bin/bash
set -e
cd "$(dirname "$0")/.."
uv run ruff check --fix fast_agent_stack/ tests/
uv run ruff format fast_agent_stack/ tests/
