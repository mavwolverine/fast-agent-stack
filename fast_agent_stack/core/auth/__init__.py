from fast_agent_stack.core.auth.api_keys import (
    authenticate_api_key,
    generate_api_key,
    hash_api_key,
)
from fast_agent_stack.core.auth.api_keys import (
    router as api_keys_router,
)
from fast_agent_stack.core.auth.backends import AuthBackend, TokenResponse
from fast_agent_stack.core.auth.backends.factory import get_auth_backend
from fast_agent_stack.core.auth.dependencies import get_current_user, require_permission
from fast_agent_stack.core.auth.lifespan import AuthLifespanHook
from fast_agent_stack.core.auth.models import (
    ApiKey,
    AuthVerificationToken,
    Group,
    Permission,
    User,
    group_permissions,
    user_groups,
    user_permissions,
)
from fast_agent_stack.core.auth.password import hash_password, verify_password
from fast_agent_stack.core.auth.routes import router as auth_router

__all__ = [
    "ApiKey",
    "AuthBackend",
    "AuthLifespanHook",
    "AuthVerificationToken",
    "Group",
    "Permission",
    "TokenResponse",
    "User",
    "api_keys_router",
    "auth_router",
    "authenticate_api_key",
    "generate_api_key",
    "get_auth_backend",
    "get_current_user",
    "group_permissions",
    "hash_api_key",
    "hash_password",
    "require_permission",
    "user_groups",
    "user_permissions",
    "verify_password",
]
