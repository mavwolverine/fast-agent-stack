"""Verify CI workflow files satisfy ADR-011 and spec requirements.

Parses YAML/TOML statically — no network, no processes.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

REPO = Path(__file__).parent.parent
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
E2E_YML = REPO / ".github" / "workflows" / "e2e.yml"
PYPROJECT = REPO / "pyproject.toml"

REQUIRED_VERSIONS = {"3.11", "3.12", "3.13", "3.14"}
REQUIRED_TOX_ENVS = {"py311", "py312", "py313", "py314"}


def _ci() -> dict:
    return yaml.safe_load(CI_YML.read_text())


def _e2e() -> dict:
    return yaml.safe_load(E2E_YML.read_text())


def _on(workflow: dict) -> dict:
    """Return the trigger block. PyYAML (YAML 1.1) parses 'on:' as True."""
    return workflow.get("on") or workflow.get(True) or {}


def _toml() -> dict:
    return tomllib.loads(PYPROJECT.read_text())


def _tox_ini(toml: dict) -> str:
    return toml["tool"]["tox"]["legacy_tox_ini"]


def _ci_test_steps(ci: dict) -> list[dict]:
    return ci["jobs"]["test"]["steps"]


def _step_runs(steps: list[dict]) -> list[str]:
    return [s.get("run", "") for s in steps if "run" in s]


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_test_job_runs_tox():
    runs = _step_runs(_ci_test_steps(_ci()))
    assert any("tox" in r for r in runs), "test job must invoke tox (ADR-011)"


def test_b2_test_matrix_covers_all_python_versions():
    matrix = _ci()["jobs"]["test"]["strategy"]["matrix"]
    # matrix may use flat list or include list
    if "python-version" in matrix:
        versions = set(str(v) for v in matrix["python-version"])
    else:
        versions = {str(item["python-version"]) for item in matrix.get("include", [])}
    assert REQUIRED_VERSIONS <= versions, f"Missing versions: {REQUIRED_VERSIONS - versions}"


def test_b3_lint_job_runs_ruff_check_and_format():
    runs = _step_runs(_ci()["jobs"]["lint"]["steps"])
    assert any("ruff check" in r for r in runs)
    assert any("ruff format" in r and "--check" in r for r in runs)


def test_b4_e2e_triggers_on_version_tag():
    tags = _on(_e2e()).get("push", {}).get("tags", [])
    assert any("v*" in str(t) for t in tags), "e2e must trigger on v* tags"


def test_b5_e2e_has_workflow_dispatch():
    assert "workflow_dispatch" in _on(_e2e()), "e2e must support manual dispatch"


def test_b6_tox_envs_include_all_python_versions():
    ini = _tox_ini(_toml())
    for env in REQUIRED_TOX_ENVS:
        assert env in ini, f"tox envlist missing {env}"


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_ci_yml_is_valid_yaml():
    data = _ci()
    assert isinstance(data, dict)


def test_c2_ci_yml_has_required_jobs():
    jobs = set(_ci()["jobs"])
    missing = {"lint", "mypy", "test"} - jobs
    assert not missing, f"Missing CI jobs: {missing}"


def test_c3_e2e_yml_is_valid_yaml():
    data = _e2e()
    assert isinstance(data, dict)


def test_c4_e2e_yml_has_e2e_job():
    assert "e2e" in _e2e()["jobs"]


def test_c5_mypy_job_exists_and_runs_mypy():
    runs = _step_runs(_ci()["jobs"]["mypy"]["steps"])
    assert any("mypy" in r for r in runs)


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_test_job_does_not_run_raw_pytest():
    """ADR-011: tests must go through tox, not direct pytest."""
    runs = _step_runs(_ci_test_steps(_ci()))
    assert not any(r.strip().startswith("pytest") for r in runs), (
        "test job must not call pytest directly — use tox (ADR-011)"
    )


def test_a2_tox_uses_uv_venv_runner():
    ini = _tox_ini(_toml())
    assert "uv-venv-runner" in ini, "tox must use runner = uv-venv-runner"


def test_a3_tox_envlist_matches_ci_matrix():
    """tox envlist and CI matrix must cover the same Python versions."""
    toml = _toml()
    ini = _tox_ini(toml)

    # Extract envlist line
    envlist_line = next((line.strip() for line in ini.splitlines() if line.strip().startswith("envlist")), "")
    tox_envs = {e.strip() for e in envlist_line.split("=", 1)[-1].split(",")}
    tox_envs = {e for e in tox_envs if e.startswith("py3")}

    assert REQUIRED_TOX_ENVS <= tox_envs, f"CI matrix versions {REQUIRED_TOX_ENVS} not all in tox envlist {tox_envs}"


def test_a4_e2e_not_run_on_pr():
    assert "pull_request" not in _on(_e2e()), "e2e must not run on every PR — release gate only"


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_test_job_fail_fast_false():
    strategy = _ci()["jobs"]["test"]["strategy"]
    assert strategy.get("fail-fast") is False, "fail-fast must be false to see all version failures"


def test_n2_mypy_uses_strict():
    runs = _step_runs(_ci()["jobs"]["mypy"]["steps"])
    assert any("--strict" in r for r in runs), "mypy must run with --strict"


def test_n3_ci_triggers_on_push_and_pr():
    on = _on(_ci())
    assert "push" in on and "pull_request" in on


def test_n4_e2e_has_nightly_schedule():
    assert "schedule" in _on(_e2e()), "e2e should run nightly to catch regressions before release"


def test_n5_e2e_preset_matrix_covers_all_presets():
    matrix = _e2e()["jobs"]["e2e"]["strategy"]["matrix"]
    presets = set(matrix.get("preset", []))
    assert {"minimal", "standard", "full", "agent"} <= presets


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_e2e_yml_exists():
    assert E2E_YML.exists(), "e2e.yml must exist as a release gate (ADR-043)"


def test_f2_ci_uses_uv_setup_action():
    """astral-sh/setup-uv must be present in every job (consistent uv version)."""
    ci = _ci()
    for job_name, job in ci["jobs"].items():
        uses = [s.get("uses", "") for s in job["steps"]]
        assert any("setup-uv" in u for u in uses), f"job '{job_name}' must use astral-sh/setup-uv@v4"


def test_f3_tox_isolated_build():
    ini = _tox_ini(_toml())
    assert "isolated_build = true" in ini, "tox must use isolated_build for reproducibility"
