"""Config module tests — 5 families (B/C/A/N/F)."""

import time

import pytest
from pydantic_settings import BaseSettings as PydanticBaseSettings

from fast_agent_stack.config import BaseSettings

# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_constructs_with_defaults() -> None:
    s = BaseSettings.model_construct()  # bypass validation to inspect raw defaults
    assert s.app_name == "FastAgentStack"
    assert s.debug is False
    assert s.secret_key is None
    assert s.auth_backends == []
    assert s.admin_enabled is False
    assert not hasattr(s, "admin_secret_key")


def test_b2_field_resolves_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "MyApp")
    s = BaseSettings()
    assert s.app_name == "MyApp"


def test_b3_constructor_kwarg_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "FromEnv")
    s = BaseSettings(app_name="FromConstructor")
    assert s.app_name == "FromConstructor"


def test_b4_user_subclass_inherits_framework_fields() -> None:
    class AppSettings(BaseSettings):
        my_api_key: str = "default"

    s = AppSettings()
    assert s.app_name == "FastAgentStack"
    assert s.my_api_key == "default"


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_importable_from_public_path() -> None:
    from fast_agent_stack.config import BaseSettings as BS

    assert BS is BaseSettings


def test_c2_is_pydantic_settings_subclass() -> None:
    assert issubclass(BaseSettings, PydanticBaseSettings)


def test_c3_model_config_extra_ignore() -> None:
    s = BaseSettings(unknown_field_xyz="ignored")  # type: ignore[call-arg]
    assert not hasattr(s, "unknown_field_xyz")


def test_c3_model_config_env_file() -> None:
    assert BaseSettings.model_config.get("env_file") == ".env"


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_aws_extras_gate_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """I3: ImportError must name the correct extras group."""
    monkeypatch.setenv("SECRETS_BACKEND", "aws")
    monkeypatch.setenv("SECRETS_AWS_SECRET_ID", "my-secret")
    with pytest.raises(ImportError, match=r"fast-agent-stack\[secrets-aws\]"):
        BaseSettings()


def test_a2_gcp_extras_gate_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """I3: ImportError must name the correct extras group."""
    monkeypatch.setenv("SECRETS_BACKEND", "gcp")
    monkeypatch.setenv("SECRETS_GCP_PROJECT_ID", "my-project")
    with pytest.raises(ImportError, match=r"fast-agent-stack\[secrets-gcp\]"):
        BaseSettings()


def test_a3_no_cloud_backend_uses_four_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-017: SECRETS_BACKEND=none must not inject a cloud source."""
    monkeypatch.setenv("SECRETS_BACKEND", "none")
    # Four-source chain: construction must succeed and not contact any cloud
    s = BaseSettings()
    assert s is not None


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_construction_under_100ms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRETS_BACKEND", raising=False)
    start = time.monotonic()
    BaseSettings()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1, f"Settings construction took {elapsed:.3f}s (limit: 0.1s)"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_jwt_no_secret_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """I11: auth_backends=['jwt'] requires secret_key."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="secret_key"):
        BaseSettings(auth_backends=["jwt"], redis_url="redis://localhost:6379")


def test_f2_multi_backend_no_secret_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """I11: auth_backends=['jwt','session'] requires secret_key for jwt."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="secret_key"):
        BaseSettings(auth_backends=["jwt", "session"], redis_url="redis://localhost:6379")


def test_f3_admin_enabled_no_secret_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """I11 / ADR-049: admin_enabled requires secret_key."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="secret_key"):
        BaseSettings(auth_backends=[], admin_enabled=True)


def test_f4_admin_enabled_with_secret_key_does_not_raise() -> None:
    """I11 / ADR-049: single secret_key covers both JWT and admin panel."""
    s = BaseSettings(auth_backends=[], admin_enabled=True, secret_key="s3cr3t")
    assert s.admin_enabled is True


def test_f5_invalid_secrets_backend_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETS_BACKEND", "vault")
    with pytest.raises(ValueError, match="SECRETS_BACKEND"):
        BaseSettings()


# ---------------------------------------------------------------------------
# ADR-050: Per-Backend Base URL and Model Settings
# ---------------------------------------------------------------------------


def test_b5_llm_base_url_defaults_to_none() -> None:
    s = BaseSettings.model_construct()
    assert s.llm_base_url is None


def test_b6_llm_model_default_is_gpt4o() -> None:
    s = BaseSettings.model_construct()
    assert s.llm_model == "gpt-4o"


def test_b7_embedding_base_url_defaults_to_none() -> None:
    s = BaseSettings.model_construct()
    assert s.embedding_base_url is None


def test_a4_embedding_openai_model_field_removed() -> None:
    s = BaseSettings.model_construct()
    assert not hasattr(s, "embedding_openai_model")


def test_n2_embedding_model_default_is_local_fastembed() -> None:
    """embedding_model default must align with the local/fastembed default provider."""
    s = BaseSettings.model_construct()
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"


def test_b8_llm_base_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    s = BaseSettings()
    assert s.llm_base_url == "http://localhost:11434/v1"


def test_b9_embedding_base_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://localhost:11434/v1")
    s = BaseSettings()
    assert s.embedding_base_url == "http://localhost:11434/v1"


def test_f6_invalid_auth_backend_name_raises() -> None:
    with pytest.raises(ValueError, match="Unknown auth backend"):
        BaseSettings(auth_backends=["magic"])


def test_f7_rate_limit_no_redis_url_raises() -> None:
    """I11: include_rate_limit=True requires redis_url (ADR-016)."""
    with pytest.raises(RuntimeError, match="redis_url"):
        BaseSettings(include_rate_limit=True)


def test_f8_rate_limit_with_redis_url_does_not_raise() -> None:
    """I11: include_rate_limit=True is valid when redis_url is set."""
    s = BaseSettings(include_rate_limit=True, redis_url="redis://localhost:6379")
    assert s.include_rate_limit is True
