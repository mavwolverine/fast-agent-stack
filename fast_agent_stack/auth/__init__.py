"""Public auth facade — re-exports the user-facing auth symbols (ADR-034, I12).

User code should import from here, not from fast_agent_stack.core.auth directly.
"""

from fast_agent_stack.core.auth import (
    User,
    get_current_user,
    require_permission,
)

__all__ = [
    "User",
    "get_current_user",
    "require_permission",
]
