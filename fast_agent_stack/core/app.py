from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI

from fast_agent_stack.core.health import router as _health_router
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
            raise ValueError("Do not pass `lifespan` to FastAgentStack — use add_lifespan_hook() instead.")

        self._hooks: list[LifespanHook] = []
        self._models: list[Any] = []
        self._admin_views: list[Any] = []
        self._agents: dict[str, Any] = {}
        hooks = self._hooks

        @asynccontextmanager
        async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
            async with AsyncExitStack() as stack:
                for hook in hooks:
                    await stack.enter_async_context(hook)
                yield

        self.fastapi_app: FastAPI = FastAPI(lifespan=_lifespan, **kwargs)
        self.fastapi_app.include_router(_health_router)

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

    def agent(
        self,
        name: str,
        backend: Any,
        *,
        tools: list[Any] | None = None,
        dependencies: list[Any] | None = None,
        path: str | None = None,
        tags: list[str] | None = None,
        summary: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an agent handler and mount a POST route at /agents/{name} (I6, ADR-046)."""
        from fast_agent_stack.core.ai.agents import make_agent_route_func

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            if name in self._agents:
                raise ValueError(
                    f"Agent name '{name}' is already registered. Each agent must have a unique name (I6)."
                )
            self._agents[name] = (handler, backend, tools)
            route_func = make_agent_route_func(name, handler, backend, tools=tools)
            self.fastapi_app.add_api_route(
                path or f"/agents/{name}",
                route_func,
                methods=["POST"],
                dependencies=dependencies,
                tags=tags or ["agents"],  # type: ignore[arg-type]
                summary=summary or f"Agent: {name}",
            )
            return handler

        return decorator

    def frontend(self, directory: str, *, path: str = "/") -> None:
        """Mount a static SPA build directory (ADR-024).

        Delegates to FastAPI's native frontend() (>=0.138.0). API routes take
        priority; unmatched paths fall back to index.html for SPA routing.
        """
        self.fastapi_app.frontend(path, directory=directory)

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await self.fastapi_app(scope, receive, send)
