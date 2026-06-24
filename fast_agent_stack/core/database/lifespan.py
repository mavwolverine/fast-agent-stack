from types import TracebackType

from fast_agent_stack.core.database import session as _session_mod


class DatabaseLifespanHook:
    """Async context manager that initialises the SQLAlchemy engine on enter
    and disposes it on exit (ADR-023, I9)."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        self._database_url = database_url
        self._echo = echo

    async def __aenter__(self) -> None:
        _session_mod.configure_engine(self._database_url, echo=self._echo)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await _session_mod.dispose_engine()
