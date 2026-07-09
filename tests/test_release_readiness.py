"""Meta-tests verifying Phase 9 release-readiness deliverables exist and are well-formed.

These tests are purely static — no network, no processes.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO = Path(__file__).parent.parent

README = REPO / "README.md"
CHANGELOG = REPO / "CHANGELOG.md"
PYPROJECT = REPO / "pyproject.toml"
TESTPYPI_YML = REPO / ".github" / "workflows" / "testpypi.yml"

REQUIRED_DOC_FILES = [
    "getting-started.md",
    "auth.md",
    "ai.md",
    "rag.md",
    "storage.md",
    "tasks.md",
    "ratelimit.md",
    "deployment.md",
    "custom-backends.md",
    "api-reference.md",
    "configuration.md",
    "migration.md",
]

INTEGRATION_SMOKE = REPO / "tests" / "integration" / "test_scaffold_smoke.py"

# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_readme_exists():
    assert README.exists(), "README.md must exist for PyPI landing page"


def test_b2_readme_has_install_section():
    text = README.read_text()
    assert "pip install" in text or "uv add" in text, "README must show how to install"


def test_b3_readme_has_quick_start():
    text = README.read_text().lower()
    assert "quick start" in text or "quickstart" in text


def test_b4_readme_has_features_or_presets():
    text = README.read_text().lower()
    assert "preset" in text or "feature" in text


def test_b5_changelog_has_real_date():
    text = CHANGELOG.read_text()
    assert "TBD" not in text, "CHANGELOG.md must have a real release date, not TBD"
    # Must contain a date in YYYY-MM-DD format
    assert re.search(r"\d{4}-\d{2}-\d{2}", text), "CHANGELOG must contain a YYYY-MM-DD date"


def test_b6_all_doc_guides_exist():
    missing = [f for f in REQUIRED_DOC_FILES if not (REPO / "docs" / f).exists()]
    assert not missing, f"Missing doc files: {missing}"


def test_b7_integration_smoke_test_exists():
    assert INTEGRATION_SMOKE.exists(), "tests/integration/test_scaffold_smoke.py must exist (ADR-043 Tier 1)"


def test_b8_testpypi_workflow_exists():
    assert TESTPYPI_YML.exists(), ".github/workflows/testpypi.yml must exist (Phase 9)"


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_pyproject_has_readme_field():
    data = tomllib.loads(PYPROJECT.read_text())
    assert data["project"].get("readme") == "README.md", 'pyproject.toml must have readme = "README.md"'


def test_c2_pyproject_has_description():
    data = tomllib.loads(PYPROJECT.read_text())
    assert data["project"].get("description"), "pyproject.toml must have a description"


def test_c3_readme_mentions_project_name():
    text = README.read_text()
    assert "fast-agent-stack" in text.lower() or "fastagentstack" in text.lower()


def test_c4_changelog_has_version_0_1_0():
    text = CHANGELOG.read_text()
    assert "0.1.0" in text, "CHANGELOG must contain 0.1.0 entry"


def test_c5_integration_smoke_imports_presets():
    text = INTEGRATION_SMOKE.read_text()
    assert "PRESETS" in text or "minimal" in text, "Smoke tests must cover all presets"


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_readme_does_not_reference_tbd():
    text = README.read_text()
    assert "TBD" not in text and "TODO" not in text, "README must not have TBD/TODO placeholders"


def test_a2_docs_directory_is_not_empty():
    docs = list((REPO / "docs").glob("*.md"))
    assert len(docs) >= 10, f"Expected at least 10 doc files, found {len(docs)}"


def test_a3_testpypi_workflow_triggers_on_workflow_dispatch():
    import yaml

    data = yaml.safe_load(TESTPYPI_YML.read_text())
    on = data.get("on") or data.get(True) or {}
    assert "workflow_dispatch" in on, "testpypi.yml must be manually triggerable"


def test_a4_integration_smoke_marked_integration():
    text = INTEGRATION_SMOKE.read_text()
    assert "integration" in text, "Scaffold smoke tests must be marked with @pytest.mark.integration"


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_readme_has_badge_or_links():
    text = README.read_text()
    assert "http" in text or "![" in text, "README should have links or badges"


def test_n2_changelog_has_unreleased_section():
    text = CHANGELOG.read_text()
    assert "[Unreleased]" in text, "CHANGELOG must have an [Unreleased] section (ADR-014)"


def test_n3_docs_getting_started_has_quickstart_commands():
    text = (REPO / "docs" / "getting-started.md").read_text()
    assert "fastagentstack" in text or "fas " in text


def test_n4_readme_length_adequate():
    text = README.read_text()
    assert len(text) > 1000, "README is too short — PyPI landing page needs substance"


def test_n5_all_guides_have_content():
    thin = [f for f in REQUIRED_DOC_FILES if len((REPO / "docs" / f).read_text()) < 200]
    assert not thin, f"Guide files with too little content (<200 chars): {thin}"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_testpypi_workflow_does_not_publish_to_real_pypi():
    text = TESTPYPI_YML.read_text()
    assert "test.pypi.org" in text or "testpypi" in text.lower(), "testpypi.yml must target TestPyPI, not real PyPI"
    assert "upload.pypi.org/legacy" not in text, "testpypi.yml must not target the real PyPI upload URL"


def test_f2_changelog_format_matches_keepachangelog():
    text = CHANGELOG.read_text()
    assert "Keep a Changelog" in text, "CHANGELOG header must reference keepachangelog.com (ADR-014)"
    assert "Semantic Versioning" in text, "CHANGELOG must reference semver"


def test_f3_readme_install_uses_correct_package_name():
    text = README.read_text()
    assert "fast-agent-stack" in text, "README install command must use the PyPI package name"
