from fastapi import APIRouter
from fastapi.responses import JSONResponse

from fast_agent_stack.core.database import check_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    ok, msg = await check_db()
    if not ok:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": msg},
        )
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "database": "ok"},
    )
