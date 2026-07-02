"""Tests for Phase 6-4: Secrets Manager Backends (ADR-017)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from fast_agent_stack.core.config import BaseSettings


def test_secrets_backend_none_by_default():
    """Default SECRETS_BACKEND=none uses no cloud source."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SECRETS_BACKEND", None)
        s = BaseSettings(app_name="test")
    assert s.app_name == "test"


def test_invalid_secrets_backend_raises_value_error():
    with patch.dict(os.environ, {"SECRETS_BACKEND": "vault"}):
        with pytest.raises(ValueError, match="Invalid SECRETS_BACKEND"):
            BaseSettings(app_name="test")


def test_i3_aws_secrets_raises_import_error_with_hint():
    """When SECRETS_BACKEND=aws but boto3 absent, ImportError with exact hint."""
    with patch.dict(os.environ, {"SECRETS_BACKEND": "aws", "SECRETS_AWS_SECRET_ID": "test"}):
        with patch(
            "fast_agent_stack.core.config.AWSSecretsManagerSettingsSource",
            side_effect=ImportError("no boto3"),
        ):
            with pytest.raises(ImportError, match="pip install fast-agent-stack\\[secrets-aws\\]"):
                BaseSettings(app_name="test")


def test_i3_gcp_secrets_raises_import_error_with_hint():
    """When SECRETS_BACKEND=gcp but google-cloud absent, ImportError with exact hint."""
    with patch.dict(os.environ, {"SECRETS_BACKEND": "gcp", "SECRETS_GCP_PROJECT_ID": "my-proj"}):
        with patch(
            "fast_agent_stack.core.config.GoogleSecretManagerSettingsSource",
            side_effect=ImportError("no google"),
        ):
            with pytest.raises(ImportError, match="pip install fast-agent-stack\\[secrets-gcp\\]"):
                BaseSettings(app_name="test")


def test_aws_secrets_source_position_after_env_source():
    """env_settings must precede cloud in ADR-017 source order."""
    with patch.dict(os.environ, {"SECRETS_BACKEND": "aws", "SECRETS_AWS_SECRET_ID": "test"}):
        mock_aws_source = MagicMock()
        with patch(
            "fast_agent_stack.core.config.AWSSecretsManagerSettingsSource",
            return_value=mock_aws_source,
        ):
            sources = BaseSettings.settings_customise_sources(
                BaseSettings,
                init_settings=MagicMock(__name__="init"),
                env_settings=MagicMock(__name__="env"),
                dotenv_settings=MagicMock(__name__="dotenv"),
                file_secret_settings=MagicMock(__name__="file"),
            )
    source_list = list(sources)
    # Find positions — env should come before cloud
    env_idx = next(i for i, s in enumerate(source_list) if getattr(s, "__name__", "") == "env")
    cloud_idx = source_list.index(mock_aws_source)
    assert env_idx < cloud_idx, "env source must precede cloud source (ADR-017)"
