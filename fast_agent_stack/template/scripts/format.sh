#!/bin/bash
set -e
cd "$(dirname "$0")/.."
uv run ruff check --fix {{ project_name }}/ tests/
uv run ruff format {{ project_name }}/ tests/
