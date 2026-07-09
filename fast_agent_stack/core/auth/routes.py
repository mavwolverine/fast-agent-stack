"""Auth routes (ADR-015, ADR-030): /auth/token, /auth/refresh, /auth/logout + email/verification."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fast_agent_stack.core.auth.backends import AuthBackend, TokenResponse
from fast_agent_stack.core.auth.backends.factory import get_auth_backend
from fast_agent_stack.core.auth.models import AuthVerificationToken, User
from fast_agent_stack.core.auth.password import hash_password, verify_password
from fast_agent_stack.core.database import get_async_session
from fast_agent_stack.core.email import EmailDeliveryError, get_email_backend

logger = logging.getLogger(__name__)

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
# Email / verification routes (ADR-018, ADR-041)
# ---------------------------------------------------------------------------


class SendVerificationRequest(BaseModel):
    email: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/send-verification", status_code=200)
async def send_verification(
    body: SendVerificationRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    from fast_agent_stack.core.config import BaseSettings

    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is not None:
        token_str = secrets.token_urlsafe(32)
        token = AuthVerificationToken(
            user_id=user.id,
            token=token_str,
            type="email_verification",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=72),
        )
        session.add(token)
        await session.flush()
        await session.commit()
        try:
            backend = get_email_backend(BaseSettings())
            await backend.send(
                to=body.email,
                subject="Verify your email",
                body_text=f"Your verification token: {token_str}",
            )
        except EmailDeliveryError as exc:
            logger.warning("Email delivery failed for send-verification: %s", exc)
    return {"detail": "If that email is registered, a verification link has been sent."}


@router.post("/verify-email", status_code=200)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    now = datetime.now(tz=UTC)
    result = await session.execute(
        select(AuthVerificationToken).where(
            AuthVerificationToken.token == body.token,
            AuthVerificationToken.type == "email_verification",
            AuthVerificationToken.expires_at > now,
        )
    )
    token_row = result.scalar_one_or_none()
    if token_row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    user_result = await session.execute(select(User).where(User.id == token_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="User not found.")
    user.is_verified = True
    await session.delete(token_row)
    await session.commit()
    return {"detail": "Email verified successfully."}


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    from fast_agent_stack.core.config import BaseSettings

    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is not None:
        token_str = secrets.token_urlsafe(32)
        token = AuthVerificationToken(
            user_id=user.id,
            token=token_str,
            type="password_reset",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=24),
        )
        session.add(token)
        await session.flush()
        await session.commit()
        try:
            backend = get_email_backend(BaseSettings())
            await backend.send(
                to=body.email,
                subject="Reset your password",
                body_text=f"Your password reset token: {token_str}",
            )
        except EmailDeliveryError as exc:
            logger.warning("Email delivery failed for forgot-password: %s", exc)
    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    now = datetime.now(tz=UTC)
    result = await session.execute(
        select(AuthVerificationToken).where(
            AuthVerificationToken.token == body.token,
            AuthVerificationToken.type == "password_reset",
            AuthVerificationToken.expires_at > now,
        )
    )
    token_row = result.scalar_one_or_none()
    if token_row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    user_result = await session.execute(select(User).where(User.id == token_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="User not found.")
    user.password_hash = hash_password(body.new_password)
    await session.delete(token_row)
    await session.commit()
    return {"detail": "Password reset successfully."}
