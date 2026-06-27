"""SQLAdmin model views (ADR-007, I19).

key_hash and the full API key must never appear in any view column (I19).
"""

from __future__ import annotations

from typing import Any

try:
    from sqladmin import ModelView
except ImportError:
    raise ImportError(
        "sqladmin is required for the admin panel. "
        "Install it with: pip install fast-agent-stack[admin]"
    )

from fast_agent_stack.core.auth.models import ApiKey, Group, Permission, User


class UserAdmin(ModelView, model=User):
    column_list = [
        User.id,
        User.email,
        User.is_active,
        User.is_staff,
        User.is_superuser,
        User.date_joined,
    ]
    column_details_list = column_list
    form_excluded_columns = ["password_hash", "groups", "direct_permissions"]
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class GroupAdmin(ModelView, model=Group):
    column_list = [Group.id, Group.name, Group.description]
    column_details_list = column_list
    name = "Group"
    name_plural = "Groups"
    icon = "fa-solid fa-users"


class PermissionAdmin(ModelView, model=Permission):
    column_list = [Permission.id, Permission.resource, Permission.action]
    column_details_list = column_list
    name = "Permission"
    name_plural = "Permissions"
    icon = "fa-solid fa-shield"


class ApiKeyAdmin(ModelView, model=ApiKey):
    # key_hash excluded entirely — never shown in list, detail, or form (I19)
    column_list = [
        ApiKey.id,
        ApiKey.user_id,
        ApiKey.name,
        ApiKey.key_prefix,
        ApiKey.scopes,
        ApiKey.expires_at,
        ApiKey.last_used_at,
        ApiKey.revoked_at,
        ApiKey.created_at,
    ]
    column_details_list = column_list
    form_excluded_columns = ["key_hash"]
    can_create = False  # API keys are created via /api-keys route only (I19)
    name = "API Key"
    name_plural = "API Keys"
    icon = "fa-solid fa-key"


def get_admin_views() -> list[Any]:
    """Return sqladmin ModelView instances for all auth models."""
    return [UserAdmin, GroupAdmin, PermissionAdmin, ApiKeyAdmin]
