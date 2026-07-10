#!/bin/bash
set -e
cd "$(dirname "$0")/.."

case "${1:-serve}" in
  serve)
    uv run --group docs zensical serve
    ;;
  build)
    uv run --group docs zensical build
    ;;
  *)
    echo "Usage: $0 [serve|build]"
    exit 1
    ;;
esac
