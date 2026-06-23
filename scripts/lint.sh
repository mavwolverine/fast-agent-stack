#!/bin/bash
set -e
cd "$(dirname "$0")/.."
uv run ruff check fast_agent_stack/ tests/
uv run ruff format --check fast_agent_stack/ tests/
