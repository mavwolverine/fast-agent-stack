"""API key management routes and helpers (ADR-031, I19)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fast_agent_stack.core.auth.dependencies import get_current_user
from fast_agent_stack.core.auth.models import ApiKey, User
from fast_agent_stack.core.database import get_async_session

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_KEY_HEADER = "fas_"


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, sha256_hex, key_prefix_8chars). ADR-031, I19.

    Full key is ``fas_`` + 43 URL-safe chars (32 bytes) = 47 chars total.
    Only the SHA-256 hex digest is persisted — full key is shown once and discarded.
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"{_KEY_HEADER}{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:8]
    return full_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hex digest of a raw API key (ADR-031)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def authenticate_api_key(raw_key: str, session: AsyncSession) -> ApiKey | None:
    """Lookup by SHA-256 hash. Returns None if not found, expired, or revoked.

    Updates ``last_used_at`` in-place on success — caller must commit the session.
    """
    key_hash = hash_api_key(raw_key)
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if api_key.revoked_at is not None:
        return None
    if api_key.expires_at is not None and api_key.expires_at < _utcnow():
        return None
    api_key.last_used_at = _utcnow()
    return api_key


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str
    scopes: dict[str, Any] | None = None
    expires_at: datetime | None = None


class ApiKeyCreatedResponse(BaseModel):
    """POST /api-keys only — includes the full key (show-once, I19)."""

    id: uuid.UUID
    name: str
    key: str  # full key — never returned again after creation (I19)
    key_prefix: str
    scopes: dict[str, Any] | None
    expires_at: datetime | None
    created_at: datetime


class ApiKeyListItem(BaseModel):
    """All reads after creation — no full key or key_hash (I19)."""

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: dict[str, Any] | None
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ApiKeyCreatedResponse:
    full_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        user_id=current_user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyListItem])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[ApiKeyListItem]:
    result = await session.execute(select(ApiKey).where(ApiKey.user_id == current_user.id))
    keys = result.scalars().all()
    return [
        ApiKeyListItem(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.post("/{key_id}/revoke", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    result = await session.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.revoked_at = _utcnow()
    await session.commit()


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    result = await session.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    await session.delete(api_key)
    await session.commit()
