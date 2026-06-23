#!/bin/bash
set -e
cd "$(dirname "$0")/.."
uv run ruff check {{ project_name }}/ tests/
uv run ruff format --check {{ project_name }}/ tests/
