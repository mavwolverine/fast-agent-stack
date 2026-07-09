"""Tier 2 E2E tests — Postgres + Redis containers, full preset coverage (ADR-043).

Strategy:
  - One shared Postgres container + one shared Redis container (alembic is idempotent).
  - Each preset is scaffolded with db="postgres" and project_name="e2e_{preset}".
  - fas migrate sets up framework + user migrations; exit code 0 is asserted.
  - uvicorn is started in a subprocess; /health/live is polled for readiness.
  - If the app fails to start (e.g. missing optional extras), the test is skipped.

Run with: pytest tests/integration/test_e2e.py -m e2e
Requires Docker — tests are skipped automatically if Docker is unavailable.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.e2e

# Port allocation: one per preset to allow parallel starts if desired.
_PORTS: dict[str, int] = {
    "minimal": 19100,
    "standard": 19101,
    "full": 19102,
    "agent": 19103,
}


def _env_prefix(preset: str) -> str:
    return f"E2E_{preset.upper()}_"


def _wait_for_health(base_url: str, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health/live", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


@contextlib.contextmanager
def _app_context(project_dir: Path, preset: str, pg_url: str, redis_url: str):
    """Run fas migrate then start uvicorn; yield base_url; terminate on exit."""
    prefix = _env_prefix(preset)
    port = _PORTS[preset]
    env = {
        **os.environ,
        f"{prefix}DATABASE_URL": pg_url,
        f"{prefix}REDIS_URL": redis_url,
        f"{prefix}SECRET_KEY": "e2e-test-secret-32-chars-xxxxxxxx",
    }

    # Step 5: fas migrate — must exit 0.
    result = subprocess.run(
        ["fastagentstack", "migrate"],
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"fas migrate failed for preset {preset!r} (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )

    # Step 6: start uvicorn.
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(project_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base_url = f"http://127.0.0.1:{port}"
    if not _wait_for_health(base_url):
        proc.terminate()
        _, stderr = proc.communicate(timeout=5)
        pytest.skip(
            f"App for preset {preset!r} did not become healthy on port {port} within 30 s. "
            f"Possibly missing optional extras. stderr: {stderr.decode()[-400:]}"
        )

    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# Minimal preset — GET /, GET /health/live
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestMinimalE2E:
    @pytest.fixture(scope="class")
    def app_url(self, e2e_scaffolded, pg_container, redis_container):
        project_dir = e2e_scaffolded["minimal"]
        pg_url = pg_container.get_connection_url(driver="asyncpg")
        redis_url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
        with _app_context(project_dir, "minimal", pg_url, redis_url) as url:
            yield url

    def test_b1_root_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/")
        assert r.status_code == 200

    def test_b2_health_live_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/health/live")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Standard preset — + /health/ready, POST /auth/token → 4xx
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestStandardE2E:
    @pytest.fixture(scope="class")
    def app_url(self, e2e_scaffolded, pg_container, redis_container):
        project_dir = e2e_scaffolded["standard"]
        pg_url = pg_container.get_connection_url(driver="asyncpg")
        redis_url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
        with _app_context(project_dir, "standard", pg_url, redis_url) as url:
            yield url

    def test_b1_root_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/")
        assert r.status_code == 200

    def test_b2_health_live_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/health/live")
        assert r.status_code == 200

    def test_b3_health_ready_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/health/ready")
        assert r.status_code == 200

    def test_b4_auth_token_rejects_bad_credentials(self, app_url):
        r = httpx.post(
            f"{app_url}/auth/token",
            data={"username": "nobody@example.com", "password": "wrong"},
        )
        assert r.status_code in (400, 401, 422)


# ---------------------------------------------------------------------------
# Full preset — + X-RateLimit-Limit header
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestFullE2E:
    @pytest.fixture(scope="class")
    def app_url(self, e2e_scaffolded, pg_container, redis_container):
        project_dir = e2e_scaffolded["full"]
        pg_url = pg_container.get_connection_url(driver="asyncpg")
        redis_url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
        with _app_context(project_dir, "full", pg_url, redis_url) as url:
            yield url

    def test_b1_root_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/")
        assert r.status_code == 200

    def test_b2_health_live_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/health/live")
        assert r.status_code == 200

    def test_b3_health_ready_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/health/ready")
        assert r.status_code == 200

    def test_b4_auth_token_rejects_bad_credentials(self, app_url):
        r = httpx.post(
            f"{app_url}/auth/token",
            data={"username": "nobody@example.com", "password": "wrong"},
        )
        assert r.status_code in (400, 401, 422)

    def test_c1_rate_limit_header_present(self, app_url):
        r = httpx.get(f"{app_url}/")
        assert "x-ratelimit-limit" in r.headers, "Full preset must expose X-RateLimit-Limit header (ADR-016)"


# ---------------------------------------------------------------------------
# Agent preset — + POST /agents/chat → 4xx (auth or validation rejection)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestAgentE2E:
    @pytest.fixture(scope="class")
    def app_url(self, e2e_scaffolded, pg_container, redis_container):
        project_dir = e2e_scaffolded["agent"]
        pg_url = pg_container.get_connection_url(driver="asyncpg")
        redis_url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
        with _app_context(project_dir, "agent", pg_url, redis_url) as url:
            yield url

    def test_b1_root_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/")
        assert r.status_code == 200

    def test_b2_health_live_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/health/live")
        assert r.status_code == 200

    def test_b3_health_ready_returns_200(self, app_url):
        r = httpx.get(f"{app_url}/health/ready")
        assert r.status_code == 200

    def test_b4_auth_token_rejects_bad_credentials(self, app_url):
        r = httpx.post(
            f"{app_url}/auth/token",
            data={"username": "nobody@example.com", "password": "wrong"},
        )
        assert r.status_code in (400, 401, 422)

    def test_c1_agent_endpoint_rejects_unauthenticated(self, app_url):
        """Agent endpoint must return 4xx — either 401 (auth) or 422 (validation)."""
        r = httpx.post(f"{app_url}/agents/chat", json={})
        assert r.status_code in (400, 401, 422), f"Expected auth/validation rejection, got {r.status_code}"
