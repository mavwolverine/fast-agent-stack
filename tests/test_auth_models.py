"""Auth model tests — 5 families (B/C/A/N/F).

Integration tests use SQLite in-memory via aiosqlite.
Password tests require fast-agent-stack[auth-jwt] (pwdlib[argon2]).
"""

from __future__ import annotations

import ast
import pathlib
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

import fast_agent_stack.core.auth.models as _auth_mod  # registers models on Base.metadata
from fast_agent_stack.core.auth.models import (
    ApiKey,
    AuthVerificationToken,
    Group,
    Permission,
    User,
)
from fast_agent_stack.core.auth.password import hash_password, verify_password
from fast_agent_stack.core.database import (
    FRAMEWORK_TABLES,
    Base,
    configure_engine,
    dispose_engine,
    get_async_session,
    get_engine,
)

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
async def setup_db() -> Any:
    configure_engine(SQLITE_URL)
    engine = get_engine()
    assert engine is not None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


async def test_b1_user_can_be_created() -> None:
    async for session in get_async_session():
        user = User(email="alice@example.com", password_hash="hashed")
        session.add(user)
        await session.commit()
        assert user.id is not None
        assert user.email == "alice@example.com"
        break


async def test_b2_group_can_be_created() -> None:
    async for session in get_async_session():
        group = Group(name="admins", description="Admin group")
        session.add(group)
        await session.commit()
        assert group.id is not None
        assert group.name == "admins"
        break


async def test_b3_permission_can_be_created() -> None:
    async for session in get_async_session():
        perm = Permission(resource="posts", action="delete")
        session.add(perm)
        await session.commit()
        assert perm.id is not None
        assert perm.resource == "posts"
        assert perm.action == "delete"
        break


async def test_b4_auth_verification_token_can_be_created() -> None:
    async for session in get_async_session():
        user = User(email="bob@example.com")
        session.add(user)
        await session.flush()
        token = AuthVerificationToken(
            token="tok123",
            user_id=user.id,
            type="email_verification",
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        session.add(token)
        await session.commit()
        assert token.id is not None
        break


async def test_b5_api_key_can_be_created() -> None:
    async for session in get_async_session():
        user = User(email="carol@example.com")
        session.add(user)
        await session.flush()
        key = ApiKey(
            user_id=user.id,
            name="my key",
            key_hash="a" * 64,
            key_prefix="fas_abcd",
        )
        session.add(key)
        await session.commit()
        assert key.id is not None
        break


def test_b6_hash_password_returns_string() -> None:
    result = hash_password("secret123")
    assert isinstance(result, str)
    assert len(result) > 0


def test_b7_verify_password_correct() -> None:
    hashed = hash_password("correct")
    is_valid, _ = verify_password("correct", hashed)
    assert is_valid is True


def test_b8_verify_password_wrong() -> None:
    hashed = hash_password("correct")
    is_valid, _ = verify_password("wrong", hashed)
    assert is_valid is False


async def test_b9_user_db_defaults() -> None:
    """After INSERT, SQLAlchemy applies server_default values (not Python-side)."""
    async for session in get_async_session():
        user = User(email="defaults@example.com")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.is_active is True
        assert user.is_verified is False
        assert user.is_staff is False
        assert user.is_superuser is False
        break


def test_b10_user_password_hash_nullable() -> None:
    user = User(email="oauth@example.com", password_hash=None)
    assert user.password_hash is None


def test_b11_api_key_nullable_fields() -> None:
    key = ApiKey(
        user_id=uuid.uuid4(),
        name="test",
        key_hash="b" * 64,
        key_prefix="fas_wxyz",
    )
    assert key.scopes is None
    assert key.expires_at is None
    assert key.last_used_at is None
    assert key.revoked_at is None


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_user_email_is_unique_constraint() -> None:
    users_table = User.__table__
    unique_cols = {
        col.name
        for c in users_table.constraints
        if hasattr(c, "columns")
        for col in c.columns
        if c.__class__.__name__ in ("UniqueConstraint",)
    }
    assert "email" in unique_cols or users_table.c["email"].unique


def test_c2_permission_has_unique_resource_action() -> None:
    constraints = Permission.__table__.constraints
    uq_names = {c.name for c in constraints}
    assert "uq_permission_resource_action" in uq_names


def test_c3_group_name_is_unique() -> None:
    groups_table = Group.__table__
    assert groups_table.c["name"].unique


def test_c4_api_key_hash_is_unique() -> None:
    api_keys_table = ApiKey.__table__
    assert api_keys_table.c["key_hash"].unique


def test_c5_all_auth_models_have_base_columns() -> None:
    for model in (User, Group, Permission, AuthVerificationToken, ApiKey):
        col_names = {c.name for c in model.__table__.columns}
        assert "id" in col_names, f"{model.__name__} missing id"
        assert "created_at" in col_names, f"{model.__name__} missing created_at"
        assert "updated_at" in col_names, f"{model.__name__} missing updated_at"


def test_c6_framework_tables_contains_all_auth_tables() -> None:
    expected = {
        "users",
        "groups",
        "permissions",
        "user_groups",
        "group_permissions",
        "user_permissions",
        "auth_verification_token",
        "api_keys",
    }
    assert expected.issubset(FRAMEWORK_TABLES), f"Missing from FRAMEWORK_TABLES: {expected - FRAMEWORK_TABLES}"


def test_c7_hash_password_not_plaintext() -> None:
    pw = "secret"
    assert hash_password(pw) != pw


def test_c8_verify_password_returns_tuple() -> None:
    hashed = hash_password("pw")
    result = verify_password("pw", hashed)
    assert isinstance(result, tuple)
    assert len(result) == 2


async def test_c9_duplicate_user_email_raises_integrity_error() -> None:
    async for session in get_async_session():
        u1 = User(email="dup@example.com")
        u2 = User(email="dup@example.com")
        session.add(u1)
        await session.flush()
        session.add(u2)
        with pytest.raises(IntegrityError):
            await session.flush()
        break


async def test_c10_duplicate_permission_raises_integrity_error() -> None:
    async for session in get_async_session():
        p1 = Permission(resource="posts", action="read")
        session.add(p1)
        await session.flush()
        p2 = Permission(resource="posts", action="read")
        session.add(p2)
        with pytest.raises(IntegrityError):
            await session.flush()
        break


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_password_py_has_extras_gate_for_pwdlib() -> None:
    """I3: pwdlib must be wrapped in try/except ImportError."""
    from fast_agent_stack.core.auth import password as pwd_mod

    source = pathlib.Path(pwd_mod.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type and isinstance(handler.type, ast.Name) and handler.type.id == "ImportError":
                    for stmt in node.body:
                        if isinstance(stmt, ast.ImportFrom) and stmt.module and "pwdlib" in stmt.module:
                            return
    pytest.fail("password.py missing try/except ImportError gate for pwdlib (I3)")


def test_a2_argon2id_params_meet_owasp_minimums() -> None:
    """I18: time_cost≥3, memory_cost≥65536, parallelism≥4."""
    hashed = hash_password("probe")
    assert "$argon2id$" in hashed, "Must use Argon2id (not argon2i or argon2d)"
    params_segment = hashed.split("$")[3]  # e.g. "m=65536,t=3,p=4"
    params: dict[str, int] = {k: int(v) for k, v in (p.split("=") for p in params_segment.split(","))}
    assert params["m"] >= 65536, f"memory_cost {params['m']} < 65536 (I18)"
    assert params["t"] >= 3, f"time_cost {params['t']} < 3 (I18)"
    assert params["p"] >= 4, f"parallelism {params['p']} < 4 (I18)"


def test_a3_auth_models_use_mapped_types() -> None:
    """Models must use SQLAlchemy 2.0 Mapped annotations."""
    source = pathlib.Path(_auth_mod.__file__).read_text()
    assert "Mapped[" in source, "models.py must use Mapped[...] type annotations"


def test_a4_models_py_does_not_import_core_internals() -> None:
    """I12: must import from core.database public __init__, not internals."""
    source = pathlib.Path(_auth_mod.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            bad_patterns = [
                "core.database.base",
                "core.database.session",
                "core.database.health",
                "core.database.lifespan",
            ]
            for bad in bad_patterns:
                assert bad not in node.module, (
                    f"models.py imports from {node.module} (I12 violation — use core.database public __init__)"
                )


def test_a5_auth_module_exports_public_api() -> None:
    """core/auth/__init__.py must re-export the key symbols."""
    from fast_agent_stack.core.auth import (
        ApiKey,
        AuthVerificationToken,
        Group,
        Permission,
        User,
        hash_password,
        verify_password,
    )

    assert User is not None
    assert Group is not None
    assert Permission is not None
    assert AuthVerificationToken is not None
    assert ApiKey is not None
    assert callable(hash_password)
    assert callable(verify_password)


def test_a6_import_hint_in_password_py_names_correct_extra() -> None:
    """I3: ImportError message must name the correct extras group."""
    from fast_agent_stack.core.auth import password as pwd_mod

    source = pathlib.Path(pwd_mod.__file__).read_text()
    assert "auth-jwt" in source or "auth-session" in source, (
        "ImportError hint must name auth-jwt or auth-session extra"
    )


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_hash_password_completes_under_5s() -> None:
    start = time.monotonic()
    hash_password("benchmark_password")
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"hash_password took {elapsed:.2f}s (limit: 5s)"


def test_n2_verify_password_completes_under_5s() -> None:
    hashed = hash_password("benchmark_password")
    start = time.monotonic()
    verify_password("benchmark_password", hashed)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"verify_password took {elapsed:.2f}s (limit: 5s)"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_import_error_message_contains_install_hint() -> None:
    """I3: The except clause must raise ImportError with an install hint."""
    from fast_agent_stack.core.auth import password as pwd_mod

    source = pathlib.Path(pwd_mod.__file__).read_text()
    assert "pip install" in source, "ImportError must include pip install hint"


def test_f2_verify_empty_password_returns_false() -> None:
    hashed = hash_password("nonempty")
    is_valid, _ = verify_password("", hashed)
    assert is_valid is False


async def test_f3_duplicate_api_key_hash_raises_integrity_error() -> None:
    async for session in get_async_session():
        user = User(email="keyholder@example.com")
        session.add(user)
        await session.flush()
        k1 = ApiKey(user_id=user.id, name="k1", key_hash="c" * 64, key_prefix="fas_1111")
        k2 = ApiKey(user_id=user.id, name="k2", key_hash="c" * 64, key_prefix="fas_2222")
        session.add(k1)
        await session.flush()
        session.add(k2)
        with pytest.raises(IntegrityError):
            await session.flush()
        break


def test_f4_user_model_has_correct_tablename() -> None:
    assert User.__tablename__ == "users"


def test_f5_all_model_tablenames_in_framework_tables() -> None:
    for model in (User, Group, Permission, AuthVerificationToken, ApiKey):
        assert model.__tablename__ in FRAMEWORK_TABLES, f"{model.__tablename__!r} not in FRAMEWORK_TABLES"
