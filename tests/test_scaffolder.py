"""Scaffolder integration tests — 5 families (B/C/A/N/F)."""


import time
from pathlib import Path

from typer.testing import CliRunner

from fast_agent_stack.cli.main import app
from fast_agent_stack.cli.new import PRESETS, TEMPLATE_DIR

runner = CliRunner()

_MINIMAL_REQUIRED_KEYS = {
    "db",
    "llm_provider",
    "vector_db",
    "embedding_provider",
    "storage_backend",
    "task_broker",
    "include_scheduler",
    "include_auth",
    "include_email",
    "include_admin",
    "include_rate_limit",
    "secrets_backend",
    "tracing",
    "include_dockerfile",
    "include_docker_compose",
    "include_k8s",
}


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_template_dir_exists() -> None:
    assert TEMPLATE_DIR.is_dir(), f"Template dir missing: {TEMPLATE_DIR}"


def test_b2_copier_yml_is_in_template_dir() -> None:
    assert (TEMPLATE_DIR / "copier.yml").exists()


def test_b3_minimal_creates_expected_files(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "pyproject.toml").exists()
    assert (tmp_path / "myproject" / "settings.py").exists()
    assert (tmp_path / "main.py").exists()
    assert (tmp_path / ".env.example").exists()


def test_b4_minimal_creates_routes_file(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    assert (tmp_path / "myproject" / "routes.py").exists()


def test_b5_minimal_routes_have_get_root(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    routes = (tmp_path / "myproject" / "routes.py").read_text()
    assert "@router.get" in routes
    assert '"/")' in routes or '"/"' in routes


def test_b6_minimal_main_py_has_app(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    main = (tmp_path / "main.py").read_text()
    assert "app" in main


def test_b7_project_name_substituted_in_settings(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    settings = (tmp_path / "myproject" / "settings.py").read_text()
    assert "myproject" in settings.lower() or "MYPROJECT" in settings


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_presets_has_all_three() -> None:
    assert "minimal" in PRESETS
    assert "api" in PRESETS
    assert "ai-full" in PRESETS


def test_c2_minimal_preset_has_required_keys() -> None:
    missing = _MINIMAL_REQUIRED_KEYS - PRESETS["minimal"].keys()
    assert not missing, f"Missing keys in minimal preset: {missing}"


def test_c3_no_dockerfile_in_minimal(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    assert not (tmp_path / "Dockerfile").exists()


def test_c4_no_docker_compose_in_minimal(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    assert not (tmp_path / "docker-compose.yml").exists()


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_template_dir_is_inside_package() -> None:
    import fast_agent_stack

    pkg_root = Path(fast_agent_stack.__file__).parent
    assert TEMPLATE_DIR.is_relative_to(pkg_root)


def test_a2_generated_pyproject_names_project(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert "myproject" in pyproject


def test_a3_generated_settings_extends_base_settings(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    settings = (tmp_path / "myproject" / "settings.py").read_text()
    assert "BaseSettings" in settings
    assert "fast_agent_stack" in settings


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_minimal_preset_completes_under_30s(tmp_path: Path) -> None:
    start = time.monotonic()
    result = runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    elapsed = time.monotonic() - start
    assert result.exit_code == 0, result.output
    assert elapsed < 30.0, f"new --preset minimal took {elapsed:.1f}s (limit: 30s)"


def test_n2_new_help_under_2s() -> None:
    start = time.monotonic()
    runner.invoke(app, ["new", "--help"])
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"new --help took {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_new_missing_project_name_exits_nonzero() -> None:
    result = runner.invoke(app, ["new"])
    assert result.exit_code != 0


def test_f2_new_invalid_preset_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["new", "myproject", "--preset", "nonexistent", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code != 0


def test_f3_new_nonempty_dir_warns(tmp_path: Path) -> None:
    (tmp_path / "existing_file.txt").write_text("hello")
    result = runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    # Should still succeed (warning only, not error)
    assert result.exit_code == 0


def test_f4_second_new_same_dir_succeeds_with_overwrite(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    result = runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    # Copier handles overwrite — should not crash
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Phase 1 smoke test: scaffold → import → run → GET /
# ---------------------------------------------------------------------------


def test_smoke_generated_project_serves_get_root(tmp_path: Path) -> None:
    """Phase 1 smoke: scaffold minimal → import generated app → GET / returns JSON."""
    import importlib.util
    import sys

    result = runner.invoke(
        app,
        ["new", "smokeproj", "--preset", "minimal", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    # Put the project root on sys.path so `routes` resolves as a flat module.
    sys.path.insert(0, str(tmp_path))
    _cleanup = {"_smokeproj_main", "routes"}
    for key in list(sys.modules):
        if key in _cleanup:
            del sys.modules[key]

    try:
        spec = importlib.util.spec_from_file_location(
            "_smokeproj_main", str(tmp_path / "main.py")
        )
        assert spec is not None and spec.loader is not None
        main_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_mod)  # type: ignore[union-attr]

        from fastapi.testclient import TestClient

        client = TestClient(main_mod.app)
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert "message" in body
    finally:
        sys.path.remove(str(tmp_path))
        for key in list(sys.modules):
            if key in _cleanup:
                del sys.modules[key]
