from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from fast_agent_stack.core.ai.llm import CompletionResult

logger = logging.getLogger(__name__)


class UsageService:
    async def log_usage(
        self,
        result: CompletionResult,
        *,
        user_id: UUID | None,
        api_key_id: UUID | None,
        agent_name: str,
        conversation_id: UUID | None,
    ) -> None:
        try:
            # Phase 4a stub — no DB write.
            # Real write (token_usage_log table) implemented in Phase 4c.
            pass
        except Exception:
            logger.warning(
                "UsageService.log_usage failed (swallowed per I21)",
                exc_info=True,
            )
