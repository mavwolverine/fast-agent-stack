
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

_VALID_AUTH_BACKENDS = frozenset({"none", "jwt", "session", "both"})
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
    auth_backend: str = "none"  # "jwt" | "session" | "both" | "none"
    admin_enabled: bool = False
    admin_secret_key: str | None = None

    @model_validator(mode="after")
    def _validate_required_secrets(self) -> Self:
        if self.auth_backend not in _VALID_AUTH_BACKENDS:
            raise ValueError(
                f"Invalid auth_backend={self.auth_backend!r}. "
                f"Expected one of: {sorted(_VALID_AUTH_BACKENDS)}"
            )
        if self.auth_backend in ("jwt", "both") and not self.secret_key:
            raise RuntimeError(
                "secret_key must be set when auth_backend is 'jwt' or 'both' (I11)"
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
