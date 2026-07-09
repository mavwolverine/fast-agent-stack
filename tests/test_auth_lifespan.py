"""Auth lifespan hook tests — 5 families (B/C/A/N/F), Phase 8 migration.

AuthLifespanHook no longer manages Redis pools (ADR-037). It validates settings
and registers backend settings for the per-request factory.
"""

from __future__ import annotations

from typing import Any

import pytest

from fast_agent_stack.core.auth.lifespan import AuthLifespanHook
from fast_agent_stack.core.config import BaseSettings


def _settings(**kwargs: Any) -> BaseSettings:
    """Build a minimal BaseSettings bypassing env discovery."""
    defaults = {
        "app_name": "test",
        "auth_backends": [],
    }
    defaults.update(kwargs)
    return BaseSettings.model_construct(**defaults)  # type: ignore[call-arg]


# ===========================================================================
# Family 1: Behavior
# ===========================================================================


async def test_b1_hook_no_op_when_auth_backends_empty() -> None:
    s = _settings(auth_backends=[])
    hook = AuthLifespanHook(s)
    await hook.__aenter__()
    await hook.__aexit__(None, None, None)


async def test_b2_hook_sets_backend_settings_on_enter() -> None:
    s = _settings(
        auth_backends=["jwt"],
        secret_key="my-secret-key",
        redis_url="redis://localhost:6379",
    )
    from fast_agent_stack.core.auth.backends import factory as _factory

    hook = AuthLifespanHook(s)
    await hook.__aenter__()
    assert _factory._stored_settings is s
    await hook.__aexit__(None, None, None)


async def test_b3_hook_clears_backend_settings_on_exit() -> None:
    s = _settings(
        auth_backends=["jwt"],
        secret_key="my-secret-key",
        redis_url="redis://localhost:6379",
    )
    from fast_agent_stack.core.auth.backends import factory as _factory

    hook = AuthLifespanHook(s)
    await hook.__aenter__()
    await hook.__aexit__(None, None, None)
    assert _factory._stored_settings is None


async def test_b4_hook_does_not_create_redis_pool() -> None:
    """AuthLifespanHook must not create any Redis connections (pool owned by SDK)."""
    from unittest.mock import patch

    s = _settings(
        auth_backends=["jwt"],
        secret_key="my-secret-key",
        redis_url="redis://localhost:6379",
    )
    hook = AuthLifespanHook(s)

    with patch("redis.asyncio.from_url", side_effect=AssertionError("must not create pool")):
        await hook.__aenter__()
    await hook.__aexit__(None, None, None)


# ===========================================================================
# Family 2: Contract (LifespanHook Protocol)
# ===========================================================================


def test_c1_auth_lifespan_hook_implements_protocol() -> None:
    from fast_agent_stack.core.protocols import LifespanHook

    s = _settings()
    hook = AuthLifespanHook(s)
    assert isinstance(hook, LifespanHook)


def test_c2_hook_has_no_redis_attribute_after_init() -> None:
    s = _settings()
    hook = AuthLifespanHook(s)
    assert not hasattr(hook, "_redis")
    assert not hasattr(hook, "redis")


# ===========================================================================
# Family 3: Architectural (I3, I9)
# ===========================================================================


def test_a1_lifespan_has_no_redis_asyncio_import() -> None:
    """lifespan.py must not import from redis.asyncio (pool managed by SDK, ADR-037)."""
    import ast
    import pathlib

    src = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "auth" / "lifespan.py"
    tree = ast.parse(src.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "redis" not in node.module, (
                f"lifespan.py imports from redis module '{node.module}' "
                "— pool management must stay in FastAPIRedisLifespanHook (ADR-037)"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "redis" not in alias.name, f"lifespan.py imports redis module '{alias.name}'"


def test_a2_auth_backend_chain_not_in_lifespan() -> None:
    """_AuthBackendChain must live in factory.py after Phase 8 migration."""
    import ast
    import pathlib

    src = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "auth" / "lifespan.py"
    tree = ast.parse(src.read_text())
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert "_AuthBackendChain" not in class_names


# ===========================================================================
# Family 4: NFR — I11 startup validation
# ===========================================================================


def test_n1_i11_jwt_requires_secret_key() -> None:
    with pytest.raises(RuntimeError, match="secret_key"):
        BaseSettings(
            auth_backends=["jwt"],
            redis_url="redis://localhost:6379",
        )


def test_n2_i11_jwt_requires_redis_url() -> None:
    with pytest.raises(RuntimeError, match="redis_url"):
        BaseSettings(
            auth_backends=["jwt"],
            secret_key="my-secret",
        )


def test_n3_i11_session_requires_redis_url() -> None:
    with pytest.raises(RuntimeError, match="redis_url"):
        BaseSettings(auth_backends=["session"])


async def test_n4_i11_missing_redis_url_raises_in_hook_aenter() -> None:
    """AuthLifespanHook also validates redis_url in __aenter__ (defense in depth)."""
    s = _settings(auth_backends=["jwt"], secret_key="k")
    # No redis_url in model_construct — bypasses BaseSettings validator
    hook = AuthLifespanHook(s)
    with pytest.raises(RuntimeError, match="redis_url"):
        await hook.__aenter__()


async def test_n5_i11_missing_secret_key_raises_in_hook_aenter() -> None:
    """AuthLifespanHook validates secret_key for JWT in __aenter__."""
    s = _settings(auth_backends=["jwt"], redis_url="redis://localhost:6379")
    hook = AuthLifespanHook(s)
    with pytest.raises(RuntimeError, match="secret_key"):
        await hook.__aenter__()


def test_n6_settings_valid_empty_auth_no_redis_needed() -> None:
    s = BaseSettings(auth_backends=[])
    assert s.auth_backends == []


def test_n7_settings_valid_jwt_with_all_required() -> None:
    s = BaseSettings(
        auth_backends=["jwt"],
        secret_key="valid-secret-key",
        redis_url="redis://localhost:6379",
    )
    assert s.auth_backends == ["jwt"]


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


async def test_f1_exit_is_safe_after_no_op_entry() -> None:
    """__aexit__ must not raise even if __aenter__ was a no-op (empty auth_backends)."""
    s = _settings(auth_backends=[])
    hook = AuthLifespanHook(s)
    await hook.__aenter__()  # no-op
    await hook.__aexit__(None, None, None)  # must not raise


async def test_f2_double_exit_is_safe() -> None:
    s = _settings(
        auth_backends=["jwt"],
        secret_key="k",
        redis_url="redis://localhost:6379",
    )
    hook = AuthLifespanHook(s)
    await hook.__aenter__()
    await hook.__aexit__(None, None, None)
    await hook.__aexit__(None, None, None)  # second exit must not raise
