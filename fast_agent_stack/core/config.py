
import os
from typing import Self

from pydantic import model_validator
from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    GoogleSecretManagerSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings import (
    BaseSettings as _BaseSettings,
)

_BUILTIN_AUTH_BACKENDS = frozenset({"jwt", "session"})
_VALID_SECRETS_BACKENDS = frozenset({"none", "aws", "gcp", ""})


class BaseSettings(_BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FastAgentStack"
    debug: bool = False

    # Auth fields — validated at construction time by I11
    secret_key: str | None = None
    auth_backends: list[str] = []  # e.g. ["jwt"] | ["session"] | ["jwt", "session"] (ADR-034)
    admin_enabled: bool = False
    admin_secret_key: str | None = None

    # Redis (ADR-006, ADR-032, ADR-033)
    redis_url: str | None = None

    # Rate limiting (ADR-016)
    include_rate_limit: bool = False

    # LLM backend timeout — seconds to wait for provider API calls (NFR Reliability)
    llm_timeout: float = 30.0

    # Token / session TTLs (ADR-015, ADR-032)
    access_token_ttl_seconds: int = 900        # 15 minutes
    refresh_token_ttl_seconds: int = 2592000   # 30 days
    session_ttl_seconds: int = 86400           # 24 hours

    @model_validator(mode="after")
    def _validate_required_secrets(self) -> Self:
        builtin = [b for b in self.auth_backends if b in _BUILTIN_AUTH_BACKENDS]
        unknown_builtins = [
            b for b in self.auth_backends
            if b not in _BUILTIN_AUTH_BACKENDS and "." not in b
        ]
        if unknown_builtins:
            raise ValueError(
                f"Unknown auth backend(s): {unknown_builtins!r}. "
                f"Built-in options: {sorted(_BUILTIN_AUTH_BACKENDS)}. "
                "For custom backends use a dotted Python path."
            )
        if "jwt" in builtin and not self.secret_key:
            raise RuntimeError(
                "secret_key must be set when 'jwt' is in auth_backends (I11)"
            )
        if (builtin or self.include_rate_limit) and not self.redis_url:
            raise RuntimeError(
                "redis_url must be set when auth_backends includes built-in backends "
                "or include_rate_limit is True (I11, ADR-016)"
            )
        if self.admin_enabled and not (self.admin_secret_key or self.secret_key):
            raise RuntimeError(
                "admin_secret_key (or secret_key) must be set"
                " when admin is enabled (I11)"
            )
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[_BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        secrets_backend = os.environ.get("SECRETS_BACKEND", "none").lower().strip()

        if secrets_backend not in _VALID_SECRETS_BACKENDS:
            raise ValueError(
                f"Invalid SECRETS_BACKEND={secrets_backend!r}. "
                "Expected 'aws', 'gcp', or 'none'."
            )

        if secrets_backend == "aws":
            cloud = _make_aws_source(settings_cls)
            # ADR-017 priority: init > env > cloud > dotenv > file
            return (
                init_settings,
                env_settings,
                cloud,
                dotenv_settings,
                file_secret_settings,
            )

        if secrets_backend == "gcp":
            cloud = _make_gcp_source(settings_cls)
            return (
                init_settings,
                env_settings,
                cloud,
                dotenv_settings,
                file_secret_settings,
            )

        return (init_settings, env_settings, dotenv_settings, file_secret_settings)


def _make_aws_source(settings_cls: type[_BaseSettings]) -> PydanticBaseSettingsSource:
    secret_id = os.environ.get("SECRETS_AWS_SECRET_ID", "")
    region = os.environ.get("SECRETS_AWS_REGION", "us-east-1")
    try:
        return AWSSecretsManagerSettingsSource(
            settings_cls, secret_id=secret_id, region_name=region
        )
    except ImportError as exc:
        raise ImportError("pip install fast-agent-stack[secrets-aws]") from exc


def _make_gcp_source(settings_cls: type[_BaseSettings]) -> PydanticBaseSettingsSource:
    project_id = os.environ.get("SECRETS_GCP_PROJECT_ID", "")
    try:
        return GoogleSecretManagerSettingsSource(settings_cls, project_id=project_id)
    except ImportError as exc:
        raise ImportError("pip install fast-agent-stack[secrets-gcp]") from exc
