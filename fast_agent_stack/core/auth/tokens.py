"""JWT access-token creation and decoding (ADR-029, ADR-015)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

try:
    import jwt as pyjwt
except ImportError:
    raise ImportError(
        "pyjwt is required for JWT authentication. Install it with: pip install fast-agent-stack[auth-jwt]"
    )


def create_access_token(
    user_id: uuid.UUID,
    secret_key: str,
    ttl_seconds: int,
    algorithm: str = "HS256",
) -> tuple[str, str]:
    """Return (encoded_token, jti). The jti is needed for the Phase-3c denylist."""
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    token = pyjwt.encode(payload, secret_key, algorithm=algorithm)
    return token, jti


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, object]:
    """Decode and validate. Raises HTTPException(401) on any failure."""
    try:
        return pyjwt.decode(token, secret_key, algorithms=[algorithm])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
