"""AuthBackend Protocol and shared response types (I1)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from fastapi import Request, Response
from pydantic import BaseModel

if TYPE_CHECKING:
    from fast_agent_stack.core.auth.models import User


class TokenResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    refresh_token: str | None = None


@runtime_checkable
class AuthBackend(Protocol):
    """I1: all five methods required on every concrete backend."""

    async def authenticate(self, request: Request) -> uuid.UUID | None: ...

    async def verify_token(self, token: str) -> uuid.UUID | None: ...

    async def create_token(self, user: User, response: Response) -> TokenResponse: ...

    async def revoke_token(
        self,
        request: Request,
        response: Response,
        refresh_tok: str | None,
    ) -> None: ...

    async def refresh_token(self, refresh_tok: str) -> TokenResponse: ...


__all__ = ["AuthBackend", "TokenResponse"]
