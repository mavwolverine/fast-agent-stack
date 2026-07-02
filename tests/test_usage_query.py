"""Tests for Phase 6-6: UsageService read methods (ADR-035, ADR-042)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from fast_agent_stack.core.ai.usage import UsageService, UsageSummary, UsageByModel


# ---------------------------------------------------------------------------
# CONTRACT — dataclass shape
# ---------------------------------------------------------------------------

def test_usage_summary_has_total_prefix():
    s = UsageSummary(
        total_tokens=100,
        prompt_tokens=60,
        completion_tokens=40,
        total_cost_microcents=50_000,
        request_count=5,
    )
    assert hasattr(s, "total_cost_microcents"), "UsageSummary must have total_cost_microcents"
    assert not hasattr(s, "cost_microcents"), "UsageSummary must NOT have cost_microcents without total_ prefix"


def test_usage_by_model_has_no_total_prefix():
    m = UsageByModel(
        model="claude-sonnet-4-6",
        total_tokens=100,
        prompt_tokens=60,
        completion_tokens=40,
        cost_microcents=25_000,
        request_count=3,
    )
    assert hasattr(m, "cost_microcents"), "UsageByModel must have cost_microcents"
    assert not hasattr(m, "total_cost_microcents"), (
        "UsageByModel must NOT have total_cost_microcents — no total_ prefix (ADR-042)"
    )


def test_usage_summary_is_frozen():
    s = UsageSummary(total_tokens=0, prompt_tokens=0, completion_tokens=0,
                     total_cost_microcents=0, request_count=0)
    with pytest.raises((AttributeError, TypeError)):
        s.total_tokens = 999  # type: ignore[misc]


def test_usage_by_model_is_frozen():
    m = UsageByModel(model="gpt-4o", total_tokens=0, prompt_tokens=0, completion_tokens=0,
                     cost_microcents=0, request_count=0)
    with pytest.raises((AttributeError, TypeError)):
        m.model = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BEHAVIOR — get_usage()
# ---------------------------------------------------------------------------

async def test_get_usage_raises_value_error_when_all_filters_none():
    svc = UsageService()
    mock_db = AsyncMock()
    with pytest.raises(ValueError, match="At least one"):
        await svc.get_usage(
            db=mock_db,
            user_id=None,
            api_key_id=None,
            agent_name=None,
        )


async def test_get_usage_by_user_id():
    svc = UsageService()
    mock_db = AsyncMock()
    row = MagicMock()
    row.total_tokens = 500
    row.prompt_tokens = 300
    row.completion_tokens = 200
    row.total_cost_microcents = 12_000
    row.request_count = 10
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = row
    mock_db.execute = AsyncMock(return_value=mock_result)
    uid = uuid.uuid4()
    result = await svc.get_usage(db=mock_db, user_id=uid, api_key_id=None, agent_name=None)
    assert isinstance(result, UsageSummary)
    assert result.total_tokens == 500
    assert result.total_cost_microcents == 12_000


async def test_get_usage_by_agent_name():
    svc = UsageService()
    mock_db = AsyncMock()
    row = MagicMock()
    row.total_tokens = 200
    row.prompt_tokens = 120
    row.completion_tokens = 80
    row.total_cost_microcents = 5_000
    row.request_count = 4
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = row
    mock_db.execute = AsyncMock(return_value=mock_result)
    result = await svc.get_usage(db=mock_db, user_id=None, api_key_id=None, agent_name="my-agent")
    assert isinstance(result, UsageSummary)
    assert result.request_count == 4


async def test_get_usage_returns_none_when_no_rows():
    svc = UsageService()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    result = await svc.get_usage(db=mock_db, user_id=uuid.uuid4(), api_key_id=None, agent_name=None)
    assert result is None


# ---------------------------------------------------------------------------
# BEHAVIOR — get_usage_by_model()
# ---------------------------------------------------------------------------

async def test_get_usage_by_model_raises_value_error_when_all_filters_none():
    svc = UsageService()
    mock_db = AsyncMock()
    with pytest.raises(ValueError, match="At least one"):
        await svc.get_usage_by_model(
            db=mock_db,
            user_id=None,
            api_key_id=None,
            agent_name=None,
        )


async def test_get_usage_by_model_returns_list_of_usage_by_model():
    svc = UsageService()
    mock_db = AsyncMock()
    row1 = MagicMock()
    row1.model = "claude-sonnet-4-6"
    row1.total_tokens = 300
    row1.prompt_tokens = 200
    row1.completion_tokens = 100
    row1.cost_microcents = 8_000
    row1.request_count = 3
    row2 = MagicMock()
    row2.model = "claude-haiku-4-5"
    row2.total_tokens = 100
    row2.prompt_tokens = 60
    row2.completion_tokens = 40
    row2.cost_microcents = 1_000
    row2.request_count = 2
    mock_result = MagicMock()
    mock_result.all.return_value = [row1, row2]
    mock_db.execute = AsyncMock(return_value=mock_result)
    uid = uuid.uuid4()
    results = await svc.get_usage_by_model(db=mock_db, user_id=uid, api_key_id=None, agent_name=None)
    assert len(results) == 2
    assert all(isinstance(r, UsageByModel) for r in results)
    assert results[0].model == "claude-sonnet-4-6"
    assert results[0].cost_microcents == 8_000


async def test_get_usage_by_model_returns_empty_list_when_no_rows():
    svc = UsageService()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)
    results = await svc.get_usage_by_model(db=mock_db, user_id=uuid.uuid4(), api_key_id=None, agent_name=None)
    assert results == []


# ---------------------------------------------------------------------------
# NFR — I21 (exceptions propagate)
# ---------------------------------------------------------------------------

async def test_i21_get_usage_propagates_db_exceptions():
    svc = UsageService()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=RuntimeError("DB offline"))
    with pytest.raises(RuntimeError, match="DB offline"):
        await svc.get_usage(db=mock_db, user_id=uuid.uuid4(), api_key_id=None, agent_name=None)


async def test_i21_get_usage_by_model_propagates_db_exceptions():
    svc = UsageService()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=RuntimeError("timeout"))
    with pytest.raises(RuntimeError, match="timeout"):
        await svc.get_usage_by_model(db=mock_db, user_id=uuid.uuid4(), api_key_id=None, agent_name=None)
