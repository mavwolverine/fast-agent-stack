from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI

from fast_agent_stack.core.middleware import (
    CORSConfig,
    apply_cors,
    apply_request_id,
    install_error_handlers,
)
from fast_agent_stack.core.protocols import AppModule, LifespanHook


class FastAgentStack:
    def __init__(
        self,
        *,
        cors_origins: list[str] | None = None,
        cors_allow_credentials: bool = False,
        cors_allow_methods: list[str] | None = None,
        cors_allow_headers: list[str] | None = None,
        request_id_middleware: bool = True,
        error_handlers: bool = True,
        **kwargs: Any,
    ) -> None:
        if "lifespan" in kwargs:
            raise ValueError(
                "Do not pass `lifespan` to FastAgentStack"
                " — use add_lifespan_hook() instead."
            )

        self._hooks: list[LifespanHook] = []
        self._models: list[Any] = []
        self._admin_views: list[Any] = []
        hooks = self._hooks

        @asynccontextmanager
        async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
            async with AsyncExitStack() as stack:
                for hook in hooks:
                    await stack.enter_async_context(hook)
                yield

        self.fastapi_app: FastAPI = FastAPI(lifespan=_lifespan, **kwargs)

        if error_handlers:
            install_error_handlers(self.fastapi_app)

        # Middleware order: CORS added first (inner), RequestID added last (outermost).
        # Starlette wraps in reverse insertion order, so the last add_middleware call
        # becomes the outermost layer — RequestID injects X-Request-ID into all
        # responses, including CORS preflight 200s.
        if cors_origins:
            apply_cors(
                self.fastapi_app,
                CORSConfig(
                    allow_origins=cors_origins,
                    allow_credentials=cors_allow_credentials,
                    allow_methods=cors_allow_methods if cors_allow_methods is not None else ["*"],
                    allow_headers=cors_allow_headers if cors_allow_headers is not None else ["*"],
                ),
            )

        if request_id_middleware:
            apply_request_id(self.fastapi_app)

    def add_lifespan_hook(self, hook: LifespanHook) -> None:
        self._hooks.append(hook)

    def install_app(self, module: AppModule) -> None:
        self.fastapi_app.include_router(module.get_router())
        self._models.extend(module.get_models())
        self._admin_views.extend(module.get_admin_views())

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await self.fastapi_app(scope, receive, send)
