"""Combined auth backend — JWT Bearer + session cookie (ADR-008)."""

from __future__ import annotations

import uuid

from fastapi import Request, Response

from fast_agent_stack.core.auth.backends import TokenResponse
from fast_agent_stack.core.auth.backends.jwt import JWTAuthBackend
from fast_agent_stack.core.auth.backends.session import SessionAuthBackend


class CombinedAuthBackend:
    """Tries JWT Bearer first, then session cookie. Issues JWT tokens by default."""

    def __init__(self, jwt: JWTAuthBackend, session: SessionAuthBackend) -> None:
        self._jwt = jwt
        self._session = session

    async def authenticate(self, request: Request) -> uuid.UUID | None:
        user_id = await self._jwt.authenticate(request)
        if user_id is not None:
            return user_id
        return await self._session.authenticate(request)

    async def create_token(self, user: object, response: Response) -> TokenResponse:
        return await self._jwt.create_token(user, response)

    async def revoke_token(
        self,
        request: Request,
        response: Response,
        refresh_tok: str | None,
    ) -> None:
        await self._jwt.revoke_token(request, response, refresh_tok)
        await self._session.revoke_token(request, response, refresh_tok)

    async def refresh_token(self, refresh_tok: str) -> TokenResponse:
        return await self._jwt.refresh_token(refresh_tok)
