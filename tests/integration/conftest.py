"""Shared fixtures for integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from copier import run_copy

from fast_agent_stack.cli.new import PRESETS, TEMPLATE_DIR


@pytest.fixture(scope="session")
def scaffolded(tmp_path_factory) -> dict[str, Path]:
    """Scaffold all presets once per session; return mapping preset → project dir."""
    results: dict[str, Path] = {}
    for preset, preset_data in PRESETS.items():
        dest = tmp_path_factory.mktemp(f"scaffold_{preset}")
        data = {
            "project_name": f"test_{preset}",
            "description": "Integration test project",
            "db": "sqlite",
            **preset_data,
        }
        run_copy(
            src_path=str(TEMPLATE_DIR),
            dst_path=str(dest),
            data=data,
            defaults=True,
            overwrite=False,
            quiet=True,
            unsafe=True,
        )
        results[preset] = dest
    return results


# ---------------------------------------------------------------------------
# Tier 2 E2E fixtures (ADR-043) — require Docker
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container():
    """Start a shared Postgres container for all E2E presets."""
    pytest.importorskip("testcontainers")
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_container():
    """Start a shared Redis container for all E2E presets."""
    pytest.importorskip("testcontainers")
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.fixture(scope="session")
def e2e_scaffolded(tmp_path_factory) -> dict[str, Path]:
    """Scaffold all presets with Postgres for Tier 2 E2E tests."""
    results: dict[str, Path] = {}
    for preset, preset_data in PRESETS.items():
        dest = tmp_path_factory.mktemp(f"e2e_{preset}")
        data = {
            "project_name": f"e2e_{preset}",
            "description": "E2E test project",
            "db": "postgres",
            **preset_data,
        }
        run_copy(
            src_path=str(TEMPLATE_DIR),
            dst_path=str(dest),
            data=data,
            defaults=True,
            overwrite=False,
            quiet=True,
            unsafe=True,
        )
        results[preset] = dest
    return results
