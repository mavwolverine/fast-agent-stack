"""Package skeleton tests — 5 families (B/C/A/N/F)."""

import importlib
import importlib.metadata
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI

import fast_agent_stack
from fast_agent_stack import FastAgentStack, __version__
from fast_agent_stack.config import BaseSettings
from fast_agent_stack.core.protocols import AppModule, LifespanHook

# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_package_imports() -> None:
    assert fast_agent_stack is not None


def test_b2_version_nonempty_semver() -> None:
    assert isinstance(__version__, str)
    assert re.match(r"^\d+\.\d+\.\d+", __version__), f"Not semver: {__version__!r}"


def test_b3_app_factory_constructs() -> None:
    app = FastAgentStack()
    assert app is not None


def test_b4_fastapi_app_is_fastapi_instance() -> None:
    app = FastAgentStack()
    assert isinstance(app.fastapi_app, FastAPI)


def test_b5_add_lifespan_hook_registers() -> None:
    class Hook:
        async def __aenter__(self) -> None:
            pass

        async def __aexit__(self, *exc: object) -> None:
            pass

    app = FastAgentStack()
    hook = Hook()
    app.add_lifespan_hook(hook)
    assert hook in app._hooks


def test_b6_install_app_includes_router() -> None:
    router = APIRouter()

    @router.get("/probe")
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    class Module:
        def get_router(self) -> APIRouter:
            return router

        def get_models(self) -> list[Any]:
            return []

        def get_admin_views(self) -> list[Any]:
            return []

    app = FastAgentStack()
    app.install_app(Module())
    from starlette.testclient import TestClient

    client = TestClient(app.fastapi_app)
    resp = client.get("/probe")
    assert resp.status_code == 200


def test_b7_install_app_collects_models_and_admin_views() -> None:
    sentinel_model = object()
    sentinel_view = object()

    class Module:
        def get_router(self) -> APIRouter:
            return APIRouter()

        def get_models(self) -> list[Any]:
            return [sentinel_model]

        def get_admin_views(self) -> list[Any]:
            return [sentinel_view]

    app = FastAgentStack()
    app.install_app(Module())
    assert sentinel_model in app._models
    assert sentinel_view in app._admin_views


def test_b8_install_app_accumulates_across_modules() -> None:
    class ModuleA:
        def get_router(self) -> APIRouter:
            return APIRouter()

        def get_models(self) -> list[Any]:
            return ["model_a"]

        def get_admin_views(self) -> list[Any]:
            return ["view_a"]

    class ModuleB:
        def get_router(self) -> APIRouter:
            return APIRouter()

        def get_models(self) -> list[Any]:
            return ["model_b"]

        def get_admin_views(self) -> list[Any]:
            return ["view_b"]

    app = FastAgentStack()
    app.install_app(ModuleA())
    app.install_app(ModuleB())
    assert app._models == ["model_a", "model_b"]
    assert app._admin_views == ["view_a", "view_b"]


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_fastapi_app_escape_hatch_exists() -> None:
    """I4: wrapped component must expose underlying object."""
    app = FastAgentStack()
    assert hasattr(app, "fastapi_app")
    assert isinstance(app.fastapi_app, FastAPI)


def test_c2_lifespan_hook_is_runtime_checkable() -> None:
    class GoodHook:
        async def __aenter__(self) -> None:
            pass

        async def __aexit__(self, *exc: object) -> None:
            pass

    assert isinstance(GoodHook(), LifespanHook)


def test_c3_app_module_is_runtime_checkable() -> None:
    class GoodModule:
        def get_router(self) -> APIRouter:
            return APIRouter()

        def get_models(self) -> list[Any]:
            return []

        def get_admin_views(self) -> list[Any]:
            return []

    assert isinstance(GoodModule(), AppModule)


def test_c4_base_settings_importable() -> None:
    assert BaseSettings is not None


def test_c5_dunder_all_exports() -> None:
    assert "FastAgentStack" in fast_agent_stack.__all__
    assert "__version__" in fast_agent_stack.__all__


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_py_typed_marker_exists() -> None:
    """PEP 561: py.typed must exist at the package root."""
    pkg_root = Path(fast_agent_stack.__file__).parent
    assert (pkg_root / "py.typed").exists()


def test_a2_installed_metadata_version_matches() -> None:
    installed = importlib.metadata.version("fast-agent-stack")
    assert installed == __version__


def test_a3_fastagentstack_is_asgi_callable() -> None:
    app = FastAgentStack()
    assert callable(app)


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_import_time_under_one_second() -> None:
    """NFR: cold import must not impose heavy startup cost (< 1 s)."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            ("import time; s = time.monotonic(); import fast_agent_stack; print(time.monotonic() - s)"),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    elapsed = float(result.stdout.strip())
    assert elapsed < 1.0, f"Import took {elapsed:.3f}s (limit: 1.0s)"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_lifespan_kwarg_raises_value_error() -> None:
    """FastAgentStack must reject a user-supplied lifespan to avoid silent override."""
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def my_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    with pytest.raises(ValueError, match="lifespan"):
        FastAgentStack(lifespan=my_lifespan)
