import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request ID, or '' outside a request context."""
    return _request_id_var.get()


class RequestIDMiddleware:
    """Pure-ASGI middleware that injects X-Request-ID into every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        incoming = headers.get("x-request-id", "").strip()
        request_id = incoming if incoming else str(uuid.uuid4())

        scope.setdefault("state", {})["request_id"] = request_id
        token = _request_id_var.set(request_id)

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                resp_headers = MutableHeaders(scope=message)
                if "x-request-id" not in resp_headers:
                    resp_headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            _request_id_var.reset(token)


def apply_request_id(app: FastAPI) -> None:
    app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    headers: dict[str, str] = {}
    if request_id:
        headers["X-Request-ID"] = str(request_id)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Exception, _unhandled_exception_handler)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


@dataclass
class CORSConfig:
    allow_origins: list[str]
    allow_credentials: bool = False
    allow_methods: list[str] = field(default_factory=lambda: ["*"])
    allow_headers: list[str] = field(default_factory=lambda: ["*"])
    expose_headers: list[str] = field(default_factory=list)
    max_age: int = 600


def apply_cors(app: FastAPI, config: CORSConfig) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allow_origins,
        allow_credentials=config.allow_credentials,
        allow_methods=config.allow_methods,
        allow_headers=config.allow_headers,
        expose_headers=config.expose_headers,
        max_age=config.max_age,
    )
