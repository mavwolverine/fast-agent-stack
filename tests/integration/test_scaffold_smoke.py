"""Tier 1 scaffold smoke tests (ADR-043).

Verifies that each preset produces valid Python and a parseable pyproject.toml.
No external services required.

Run with: pytest tests/integration/ -m integration
"""

from __future__ import annotations

import py_compile
import tomllib
from pathlib import Path

import pytest

from fast_agent_stack.cli.new import PRESETS

PRESET_NAMES = list(PRESETS)

# Files expected in every generated project
UNIVERSAL_FILES = ["pyproject.toml", "main.py"]

# Files required only for specific presets
PRESET_REQUIRED_FILES: dict[str, list[str]] = {
    "standard": ["Dockerfile"],
    "full": ["Dockerfile", "docker-compose.yml"],
    "agent": ["Dockerfile"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _py_files(project_dir: Path) -> list[Path]:
    return [p for p in project_dir.rglob("*.py") if ".venv" not in p.parts]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_scaffold_produces_output(scaffolded, preset):
    project_dir = scaffolded[preset]
    assert project_dir.exists()
    assert any(project_dir.iterdir()), f"Preset {preset!r} produced an empty directory"


@pytest.mark.integration
@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_all_py_files_compile(scaffolded, preset):
    """Every generated .py file must be valid Python (py_compile)."""
    project_dir = scaffolded[preset]
    py_files = _py_files(project_dir)
    assert py_files, f"Preset {preset!r} generated no .py files"
    for f in py_files:
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as exc:
            pytest.fail(f"Compile error in {f.relative_to(project_dir)}: {exc}")


@pytest.mark.integration
@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_pyproject_toml_is_valid(scaffolded, preset):
    """Generated pyproject.toml must be parseable TOML with required fields."""
    project_dir = scaffolded[preset]
    pyproject = project_dir / "pyproject.toml"
    assert pyproject.exists(), f"Preset {preset!r} missing pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    assert "project" in data
    assert "name" in data["project"]
    assert "dependencies" in data["project"]


@pytest.mark.integration
@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_universal_files_exist(scaffolded, preset):
    """Every preset must generate the universal file set."""
    project_dir = scaffolded[preset]
    missing = [f for f in UNIVERSAL_FILES if not (project_dir / f).exists()]
    assert not missing, f"Preset {preset!r} missing files: {missing}"


@pytest.mark.integration
@pytest.mark.parametrize("preset,files", [(p, files) for p, files in PRESET_REQUIRED_FILES.items()])
def test_preset_specific_files_exist(scaffolded, preset, files):
    """Preset-specific files must be present when expected."""
    project_dir = scaffolded[preset]
    missing = [f for f in files if not (project_dir / f).exists()]
    assert not missing, f"Preset {preset!r} missing expected files: {missing}"


@pytest.mark.integration
def test_agent_preset_has_ai_agents_file(scaffolded):
    """The agent preset must generate an ai/agents/__init__.py."""
    project_dir = scaffolded["agent"]
    package_dir = project_dir / "test_agent"
    agents = package_dir / "ai" / "agents" / "__init__.py"
    assert agents.exists(), "agent preset must generate ai/agents/__init__.py in the package directory"


@pytest.mark.integration
@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_env_example_generated(scaffolded, preset):
    """.env.example must be generated so users know what variables to set."""
    project_dir = scaffolded[preset]
    env_example = project_dir / ".env.example"
    assert env_example.exists(), f"Preset {preset!r} missing .env.example"
