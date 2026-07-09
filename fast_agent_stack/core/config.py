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

    # Storage backend (Phase 5, ADR-038)
    storage_backend: str = "local"
    storage_local_root: str = "./uploads"
    storage_s3_bucket: str = ""
    storage_s3_region: str = "us-east-1"
    storage_minio_endpoint: str = ""
    storage_minio_bucket: str = ""
    storage_minio_access_key: str = ""
    storage_minio_secret_key: str = ""
    storage_timeout: float = 30.0

    # Vector store backend (Phase 5, ADR-038)
    vector_db: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    pgvector_database_url: str | None = None  # postgresql+asyncpg://... required for PgVectorStore
    pgvector_collection_schema: str = "public"
    opensearch_url: str = "http://localhost:9200"
    opensearch_username: str | None = None
    opensearch_password: str | None = None
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str | None = None
    vector_timeout: float = 30.0

    # Embedding backend (Phase 5, ADR-038, ADR-039)
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = ""
    embedding_openai_model: str = "text-embedding-3-small"
    embedding_bedrock_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_timeout: float = 30.0

    # RAG pipeline (Phase 5, ADR-040)
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 64
    rag_chunking_strategy: str = "fixed"

    # Background tasks (Phase 6, ADR-005, ADR-020)
    tasks_broker_url: str | None = None  # falls back to redis_url when None

    # Rate limiting (Phase 6, ADR-016)
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds per fixed window

    # Email delivery (Phase 6, ADR-018, ADR-041)
    email_backend: str = "smtp"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    email_from: str = "noreply@example.com"
    email_from_name: str = "FastAgentStack"

    # Observability (Phase 6, ADR-009)
    tracing_enabled: bool = False
    otel_exporter_endpoint: str = "http://localhost:4317"

    # Token / session TTLs (ADR-015, ADR-032)
    access_token_ttl_seconds: int = 900  # 15 minutes
    refresh_token_ttl_seconds: int = 2592000  # 30 days
    session_ttl_seconds: int = 86400  # 24 hours

    @model_validator(mode="after")
    def _validate_required_secrets(self) -> Self:
        builtin = [b for b in self.auth_backends if b in _BUILTIN_AUTH_BACKENDS]
        unknown_builtins = [b for b in self.auth_backends if b not in _BUILTIN_AUTH_BACKENDS and "." not in b]
        if unknown_builtins:
            raise ValueError(
                f"Unknown auth backend(s): {unknown_builtins!r}. "
                f"Built-in options: {sorted(_BUILTIN_AUTH_BACKENDS)}. "
                "For custom backends use a dotted Python path."
            )
        if "jwt" in builtin and not self.secret_key:
            raise RuntimeError("secret_key must be set when 'jwt' is in auth_backends (I11)")
        if (builtin or self.include_rate_limit) and not self.redis_url:
            raise RuntimeError(
                "redis_url must be set when auth_backends includes built-in backends "
                "or include_rate_limit is True (I11, ADR-016)"
            )
        if self.admin_enabled and not (self.admin_secret_key or self.secret_key):
            raise RuntimeError("admin_secret_key (or secret_key) must be set when admin is enabled (I11)")
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
            raise ValueError(f"Invalid SECRETS_BACKEND={secrets_backend!r}. Expected 'aws', 'gcp', or 'none'.")

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
        return AWSSecretsManagerSettingsSource(settings_cls, secret_id=secret_id, region_name=region)
    except ImportError as exc:
        raise ImportError("pip install fast-agent-stack[secrets-aws]") from exc


def _make_gcp_source(settings_cls: type[_BaseSettings]) -> PydanticBaseSettingsSource:
    project_id = os.environ.get("SECRETS_GCP_PROJECT_ID", "")
    try:
        return GoogleSecretManagerSettingsSource(settings_cls, project_id=project_id)
    except ImportError as exc:
        raise ImportError("pip install fast-agent-stack[secrets-gcp]") from exc
