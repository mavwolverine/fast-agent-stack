"""Alembic scaffold integration tests — 5 families (B/C/A/N/F).

Verifies that:
- the alembic/ directory structure is generated correctly by the copier template
- the generated env.py is syntactically valid and architecturally correct
- `fastagentstack migrate` and `fastagentstack makemigrations` work end-to-end

Migration-run tests (B6, B7, N2) are regular sync functions (not async) because
env.py calls asyncio.run() at module level — that requires no running event loop.
"""

import ast
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fast_agent_stack.cli.main import app

runner = CliRunner()

# Use a unique project name so sys.modules entries don't collide with test_scaffolder.py
_PROJECT = "algtest"


@pytest.fixture(autouse=True)
def _clean_generated_modules() -> None:  # type: ignore[return]
    yield
    for key in list(sys.modules):
        if key.startswith(_PROJECT):
            del sys.modules[key]


def _scaffold(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["new", _PROJECT, "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_alembic_dir_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (tmp_path / "alembic").is_dir()


def test_b2_env_py_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (tmp_path / "alembic" / "env.py").exists()


def test_b3_script_mako_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (tmp_path / "alembic" / "script.py.mako").exists()


def test_b4_versions_dir_generated(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert (tmp_path / "alembic" / "versions").is_dir()


def test_b5_env_py_contains_project_name_substitution(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert _PROJECT in content


def test_b6_migrate_succeeds_in_generated_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code == 0, result.output + (str(result.exception) if result.exception else "")


def test_b7_makemigrations_creates_revision_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    # ADR-044: DB must be at known heads before makemigrations can generate a new revision.
    migrate_result = runner.invoke(app, ["migrate"])
    assert migrate_result.exit_code == 0, migrate_result.output + (
        str(migrate_result.exception) if migrate_result.exception else ""
    )
    result = runner.invoke(app, ["makemigrations", "-m", "initial"])
    assert result.exit_code == 0, result.output + (str(result.exception) if result.exception else "")
    py_revisions = [f for f in (tmp_path / "alembic" / "versions").iterdir() if f.suffix == ".py"]
    # ADR-048: scaffold now writes the seed migration (1 file); makemigrations adds a second.
    assert len(py_revisions) == 2, f"Expected 2 revision .py files (seed + generated), found: {py_revisions}"


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_env_py_is_syntactically_valid(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    ast.parse(content)  # raises SyntaxError if invalid


def test_c2_env_py_imports_fast_agent_stack_database(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert "fast_agent_stack.database" in content


def test_c3_env_py_has_include_object_function(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert "include_object" in content


def test_c4_env_py_imports_project_models(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert f"{_PROJECT}.models" in content


def test_c5_script_mako_has_upgrade_and_downgrade(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "script.py.mako").read_text()
    assert "def upgrade" in content
    assert "def downgrade" in content


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_env_py_references_framework_tables_i16(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert "FRAMEWORK_TABLES" in content


def test_a2_env_py_reads_url_from_settings_not_os_environ_i15(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert "get_settings" in content
    assert "os.environ" not in content


def test_a3_env_py_uses_async_engine_i2(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert "create_async_engine" in content


def test_a4_env_py_uses_asyncio_run(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = (tmp_path / "alembic" / "env.py").read_text()
    assert "asyncio.run" in content


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_scaffold_renders_alembic_in_under_30s(tmp_path: Path) -> None:
    start = time.monotonic()
    _scaffold(tmp_path)
    elapsed = time.monotonic() - start
    assert (tmp_path / "alembic" / "env.py").exists()
    assert elapsed < 30.0, f"Scaffold took {elapsed:.1f}s (limit: 30s)"


def test_n2_migrate_completes_in_under_10s(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    start = time.monotonic()
    result = runner.invoke(app, ["migrate"])
    elapsed = time.monotonic() - start
    assert result.exit_code == 0, result.output
    assert elapsed < 10.0, f"migrate took {elapsed:.1f}s (limit: 10s)"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_migrate_fails_without_alembic_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code != 0


def test_f2_makemigrations_fails_without_alembic_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["makemigrations"])
    assert result.exit_code != 0


def test_f3_seed_with_no_seeds_py_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["seed"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# ADR-048: Seed migration + user branch
# ---------------------------------------------------------------------------


def _scaffold_with_auth_and_ai(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            _PROJECT,
            "--preset",
            "minimal",
            "--db",
            "sqlite",
            "--auth",
            "--llm",
            "openai",
            "--no-admin",
            "--no-rate-limit",
            "--no-dockerfile",
            "--no-docker-compose",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output


def _seed_file(tmp_path: Path) -> Path:
    return tmp_path / "alembic" / "versions" / f"0001_{_PROJECT}_initial.py"


# Family 1: Behavior — seed file existence


def test_b8_seed_migration_file_exists_after_scaffold(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    assert _seed_file(tmp_path).exists(), f"Seed migration not found at {_seed_file(tmp_path)}"


def test_b9_seed_migration_exists_for_auth_and_ai_scaffold(tmp_path: Path) -> None:
    _scaffold_with_auth_and_ai(tmp_path)
    assert _seed_file(tmp_path).exists()


def test_b10_makemigrations_generated_revision_chains_from_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    runner.invoke(app, ["migrate"])
    result = runner.invoke(app, ["makemigrations", "-m", "add-stuff"])
    assert result.exit_code == 0, result.output + (str(result.exception) if result.exception else "")
    generated = [
        f
        for f in (tmp_path / "alembic" / "versions").iterdir()
        if f.suffix == ".py" and f.name != f"0001_{_PROJECT}_initial.py"
    ]
    assert len(generated) == 1
    content = generated[0].read_text()
    assert f"{_PROJECT}_0001" in content, "Generated migration must chain from seed revision"


# Family 2: Contract — seed file content


def test_c6_seed_migration_is_syntactically_valid(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    ast.parse(_seed_file(tmp_path).read_text())


def test_c7_seed_migration_has_correct_revision_id(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = _seed_file(tmp_path).read_text()
    assert f'"{_PROJECT}_0001"' in content


def test_c8_seed_migration_has_correct_branch_labels(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = _seed_file(tmp_path).read_text()
    assert f'("{_PROJECT}",)' in content


def test_c9_seed_migration_upgrade_is_no_op(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = _seed_file(tmp_path).read_text()
    tree = ast.parse(content)
    upgrade_fn = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "upgrade"),
        None,
    )
    assert upgrade_fn is not None, "upgrade() not found in seed migration"
    # body must be only a docstring (Expr) and/or Pass - no real statements
    real_stmts = [s for s in upgrade_fn.body if not isinstance(s, (ast.Expr, ast.Pass))]
    assert not real_stmts, f"upgrade() is not a no-op: {real_stmts}"


def test_c10_seed_migration_downgrade_is_no_op(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    content = _seed_file(tmp_path).read_text()
    tree = ast.parse(content)
    downgrade_fn = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "downgrade"),
        None,
    )
    assert downgrade_fn is not None, "downgrade() not found in seed migration"
    real_stmts = [s for s in downgrade_fn.body if not isinstance(s, (ast.Expr, ast.Pass))]
    assert not real_stmts, f"downgrade() is not a no-op: {real_stmts}"


# Family 3: Architectural — depends_on filtering (ADR-048 §2)


def test_a5_seed_depends_on_includes_auth_head_when_auth_enabled(tmp_path: Path) -> None:
    _scaffold_with_auth_and_ai(tmp_path)
    content = _seed_file(tmp_path).read_text()
    assert "fas_auth_0001" in content, "Auth-enabled scaffold must include fas_auth_0001 in depends_on"


def test_a6_seed_depends_on_includes_ai_head_when_llm_enabled(tmp_path: Path) -> None:
    _scaffold_with_auth_and_ai(tmp_path)
    content = _seed_file(tmp_path).read_text()
    assert "fas_ai_0002" in content, "AI-enabled scaffold must include fas_ai_0002 in depends_on"


def test_a7_seed_depends_on_is_none_when_no_framework_features(tmp_path: Path) -> None:
    _scaffold(tmp_path)  # minimal: no auth, no AI
    content = _seed_file(tmp_path).read_text()
    assert "depends_on = None" in content, "No-feature scaffold must have depends_on = None"


def test_a8_copier_answers_yml_contains_project_name(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    import yaml

    answers = yaml.safe_load((tmp_path / ".copier-answers.yml").read_text())
    assert answers.get("project_name") == _PROJECT


# Family 4: NFR


def test_n3_seed_migration_present_after_scaffold_under_30s(tmp_path: Path) -> None:
    import time

    start = time.monotonic()
    _scaffold(tmp_path)
    elapsed = time.monotonic() - start
    assert _seed_file(tmp_path).exists()
    assert elapsed < 30.0, f"Scaffold (with seed) took {elapsed:.1f}s (limit: 30s)"


# Family 5: Failure-mode


def test_f4_makemigrations_fails_when_copier_answers_yml_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "alembic" / "versions").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["makemigrations"])
    assert result.exit_code != 0, "makemigrations must exit non-zero when .copier-answers.yml is absent"
