"""Public storage facade — re-exports the user-facing storage symbols.

User code should import from here, not from fast_agent_stack.core.storage directly.
"""

from fast_agent_stack.core.storage import (
    KeyNotFoundError,
    StorageProtocol,
    get_storage,
)

__all__ = [
    "StorageProtocol",
    "KeyNotFoundError",
    "get_storage",
]
