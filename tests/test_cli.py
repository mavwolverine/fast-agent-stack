"""CLI tests — 5 families (B/C/A/N/F)."""


import re
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from fast_agent_stack import __version__
from fast_agent_stack.cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[^m]*m", "", text)


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_b2_version_flag_shows_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_b3_version_short_flag() -> None:
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_b4_version_subcommand_shows_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_b5_run_help_exits_zero() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "0.0.0.0" in output  # production default host visible in help
    assert "--workers" in output


def test_b7_dev_help_exits_zero() -> None:
    result = runner.invoke(app, ["dev", "--help"])
    assert result.exit_code == 0
    assert "127.0.0.1" in result.output  # loopback default visible in help


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_app_name_is_fastagentstack() -> None:
    assert app.info.name == "fastagentstack"


def test_c2_run_command_is_registered() -> None:
    names = [c.name for c in app.registered_commands]
    assert "run" in names


def test_c2_version_command_is_registered() -> None:
    names = [c.name for c in app.registered_commands]
    assert "version" in names


def test_c5_dev_command_is_registered() -> None:
    names = [c.name for c in app.registered_commands]
    assert "dev" in names


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_run_calls_uvicorn_run() -> None:
    """ADR-019: fastagentstack run must call uvicorn.run() in-process."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["run"])
    assert mock_run.called


def test_a1b_dev_calls_uvicorn_run() -> None:
    """ADR-019: fastagentstack dev must call uvicorn.run() in-process."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["dev"])
    assert mock_run.called


def test_a2_dev_default_host_is_loopback() -> None:
    """NFR Security: fastagentstack dev must bind to 127.0.0.1 by default."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["dev"])
    assert mock_run.call_args.kwargs.get("host") == "127.0.0.1"


def test_a2b_run_default_host_is_all_interfaces() -> None:
    """NFR Security + ADR-019: fastagentstack run must bind to 0.0.0.0 by default."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["run"])
    assert mock_run.call_args.kwargs.get("host") == "0.0.0.0"


def test_a3_dev_host_override_is_passed_through() -> None:
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["dev", "--host", "0.0.0.0"])
    assert mock_run.call_args.kwargs.get("host") == "0.0.0.0"


def test_a7_run_workers_flag_passed_to_uvicorn() -> None:
    """ADR-019: fastagentstack run --workers must forward the value to uvicorn."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["run", "--workers", "4"])
    assert mock_run.call_args.kwargs.get("workers") == 4


def test_a8_run_omits_workers_when_unset() -> None:
    """uvicorn.run() must not receive workers= when --workers is not passed."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["run"])
    assert "workers" not in (mock_run.call_args.kwargs or {})


def test_a9_run_does_not_enable_reload() -> None:
    """ADR-019 / NFR Security: fastagentstack run must never pass reload=True to uvicorn."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        runner.invoke(app, ["run"])
    assert mock_run.call_args.kwargs.get("reload") is not True


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_help_completes_under_2s() -> None:
    start = time.monotonic()
    runner.invoke(app, ["--help"])
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"--help took {elapsed:.3f}s (limit: 2.0s)"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_unknown_command_exits_nonzero() -> None:
    result = runner.invoke(app, ["nonexistent-command"])
    assert result.exit_code != 0


def test_f2_uvicorn_failure_propagates() -> None:
    """If uvicorn.run() raises, the exit code must be non-zero."""
    with (
        patch("fast_agent_stack.cli.run._resolve", return_value="main:app"),
        patch("uvicorn.run") as mock_run,
    ):
        mock_run.side_effect = SystemExit(1)
        result = runner.invoke(app, ["run"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# `new` command — Contract
# ---------------------------------------------------------------------------


def test_c3_new_command_is_registered() -> None:
    names = [c.name for c in app.registered_commands]
    assert "new" in names


def test_c4_update_command_is_registered() -> None:
    names = [c.name for c in app.registered_commands]
    assert "update" in names


# ---------------------------------------------------------------------------
# `new` command — Behavior
# ---------------------------------------------------------------------------


def test_b6_new_help_exits_zero() -> None:
    result = runner.invoke(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "project" in result.output.lower()


# ---------------------------------------------------------------------------
# `new` command — Architectural
# ---------------------------------------------------------------------------


def test_a4_new_uses_copier_run_copy(tmp_path: Path) -> None:
    """ADR-010: fastagentstack new must use copier.run_copy."""
    with patch("fast_agent_stack.cli.new.run_copy") as mock_copy:
        mock_copy.return_value = None
        runner.invoke(
            app,
            ["new", "demo", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
        )
    assert mock_copy.called


def test_a5_new_template_dir_contains_copier_yml() -> None:

    from fast_agent_stack.cli.new import TEMPLATE_DIR

    assert (TEMPLATE_DIR / "copier.yml").exists()


# ---------------------------------------------------------------------------
# `new` command — Failure-mode
# ---------------------------------------------------------------------------


def test_f3_new_invalid_preset_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["new", "demo", "--preset", "bogus", "--output-dir", str(tmp_path)]
    )
    assert result.exit_code != 0


def test_f4_new_existing_dir_exits_nonzero(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()  # pre-create the target dir
    result = runner.invoke(
        app, ["new", "demo", "--output-dir", str(tmp_path)]
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# `run` / `dev` commands — NFR: default app path (ADR-019 / DX.md)
# ---------------------------------------------------------------------------


def test_a6_run_default_app_path_is_main_app() -> None:
    """fastagentstack run with no args must pass main:app to fastapi_cli discovery (DX.md)."""
    mock_import_data = MagicMock()
    mock_import_data.import_string = "main:app"
    with (
        patch(
            "fast_agent_stack.cli.run.get_import_data_from_import_string",
            return_value=mock_import_data,
        ) as mock_discover,
        patch("fast_agent_stack.cli.run.uvicorn") as mock_uvicorn,
    ):
        runner.invoke(app, ["run"])
    mock_discover.assert_called_once_with("main:app", from_pyproject=False)
    assert mock_uvicorn.run.call_args.kwargs.get("app") == "main:app"
