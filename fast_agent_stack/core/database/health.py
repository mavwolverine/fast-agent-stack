from sqlalchemy import text

from fast_agent_stack.core.database.session import get_engine


async def check_db() -> tuple[bool, str]:
    """Lightweight connectivity check: SELECT 1 against the configured engine.

    Returns (True, "ok") on success, (False, reason) on any failure.
    Used by /health/ready (I13).
    """
    engine = get_engine()
    if engine is None:
        return False, "database engine not initialized"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
