from types import TracebackType
from typing import Any, Protocol, runtime_checkable

from fastapi import APIRouter


@runtime_checkable
class LifespanHook(Protocol):
    async def __aenter__(self) -> None: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None: ...


@runtime_checkable
class AppModule(Protocol):
    def get_router(self) -> APIRouter: ...
    def get_models(self) -> list[Any]: ...
    def get_admin_views(self) -> list[Any]: ...
