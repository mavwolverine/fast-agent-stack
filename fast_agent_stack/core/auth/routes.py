"""Auth routes (ADR-015, ADR-030): /auth/token, /auth/refresh, /auth/logout + stubs."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fast_agent_stack.core.auth.backends import AuthBackend, TokenResponse
from fast_agent_stack.core.auth.backends.factory import get_auth_backend
from fast_agent_stack.core.auth.models import User
from fast_agent_stack.core.auth.password import verify_password
from fast_agent_stack.core.database import get_async_session

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/token", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    backend: AuthBackend = Depends(get_auth_backend),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    ok, new_hash = verify_password(body.password, user.password_hash or "")
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if new_hash:  # ADR-030: transparent re-hash when params change
        user.password_hash = new_hash
        await session.commit()
    return await backend.create_token(user, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    backend: AuthBackend = Depends(get_auth_backend),
) -> TokenResponse:
    return await backend.refresh_token(body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    body: LogoutRequest = Body(default_factory=LogoutRequest),
    backend: AuthBackend = Depends(get_auth_backend),
) -> None:
    await backend.revoke_token(request, response, body.refresh_token)


# ---------------------------------------------------------------------------
# Email / verification stubs — delivery deferred to Phase 6 (ADR-018)
# ---------------------------------------------------------------------------

@router.post("/send-verification", status_code=202)
async def send_verification() -> dict[str, str]:
    return {"detail": "Email verification not configured in this deployment"}


@router.post("/verify-email", status_code=202)
async def verify_email() -> dict[str, str]:
    return {"detail": "Email verification not configured in this deployment"}


@router.post("/forgot-password", status_code=202)
async def forgot_password() -> dict[str, str]:
    return {"detail": "Password reset not configured in this deployment"}


@router.post("/reset-password", status_code=202)
async def reset_password() -> dict[str, str]:
    return {"detail": "Password reset not configured in this deployment"}
