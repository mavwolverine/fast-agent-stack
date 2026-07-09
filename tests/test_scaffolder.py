"""Scaffolder integration tests — 5 families (B/C/A/N/F), Phase 7 additions."""

import re
import time
from pathlib import Path

from typer.testing import CliRunner

from fast_agent_stack.cli.main import app
from fast_agent_stack.cli.new import PRESETS, TEMPLATE_DIR

runner = CliRunner()

_MINIMAL_REQUIRED_KEYS = {
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
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "pyproject.toml").exists()
    assert (tmp_path / "myproject" / "settings.py").exists()
    assert (tmp_path / "main.py").exists()
    assert (tmp_path / ".env.example").exists()


def test_b4_minimal_creates_routes_file(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    assert (tmp_path / "myproject" / "routes.py").exists()


def test_b5_minimal_routes_have_get_root(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    routes = (tmp_path / "myproject" / "routes.py").read_text()
    assert "@router.get" in routes
    assert '"/")' in routes or '"/"' in routes


def test_b6_minimal_main_py_has_app(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    main = (tmp_path / "main.py").read_text()
    assert "app" in main


def test_b7_project_name_substituted_in_settings(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    settings = (tmp_path / "myproject" / "settings.py").read_text()
    assert "myproject" in settings.lower() or "MYPROJECT" in settings


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_presets_has_all_four() -> None:
    assert "minimal" in PRESETS
    assert "standard" in PRESETS
    assert "full" in PRESETS
    assert "agent" in PRESETS


def test_c2_minimal_preset_has_required_keys() -> None:
    missing = _MINIMAL_REQUIRED_KEYS - PRESETS["minimal"].keys()
    assert not missing, f"Missing keys in minimal preset: {missing}"


def test_c3_no_dockerfile_content_in_minimal(tmp_path: Path) -> None:
    """Minimal preset: Dockerfile rendered empty (include_dockerfile=False)."""
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    dockerfile = tmp_path / "Dockerfile"
    # Copier creates the file from the .jinja template; content is empty when disabled
    assert not dockerfile.exists() or dockerfile.read_text().strip() == ""


def test_c4_no_docker_compose_content_in_minimal(tmp_path: Path) -> None:
    """Minimal preset: docker-compose.yml rendered empty (include_docker_compose=False)."""
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    compose = tmp_path / "docker-compose.yml"
    assert not compose.exists() or compose.read_text().strip() == ""


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
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert "myproject" in pyproject


def test_a3_generated_settings_extends_base_settings(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
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
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
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
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    # Should still succeed (warning only, not error)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Phase 7: I7 — template conditional values must match copier.yml choices
# ---------------------------------------------------------------------------

_COPIER_CHOICES: dict[str, set[str]] = {
    "db": {"postgres", "mysql", "sqlite"},
    "llm_provider": {"bedrock", "openai", "anthropic", "litellm", "none"},
    "vector_db": {"qdrant", "pgvector", "opensearch", "weaviate", "none"},
    "embedding_provider": {"bedrock", "openai", "local", "none"},
    "storage_backend": {"s3", "local", "minio", "none"},
    "task_broker": {"redis", "none"},
    "auth_backends": {"jwt", "session", "jwt-and-session"},
    "tracing": {"jaeger", "none"},
    "secrets_backend": {"none", "aws", "gcp"},
    "python_version": {"3.11", "3.12", "3.13", "3.14"},
}


def test_a4_i7_all_template_conditionals_use_valid_copier_values() -> None:
    """Every value compared in a Jinja conditional must be a valid copier.yml choice (I7)."""
    question_pattern = r'\{%-?\s*(?:if|elif)\s+(\w+)\s*(?:!=|==)\s*"([^"]+)"'
    violations: list[str] = []
    for jinja_file in sorted(TEMPLATE_DIR.rglob("*.jinja")):
        text = jinja_file.read_text()
        for question, value in re.findall(question_pattern, text):
            if question not in _COPIER_CHOICES:
                continue
            if value not in _COPIER_CHOICES[question]:
                violations.append(
                    f"{jinja_file.relative_to(TEMPLATE_DIR)}: '{value}' not a valid choice for '{question}'"
                )
    assert not violations, "I7 violations:\n" + "\n".join(violations)


def test_a5_i9_hook_registration_order_in_app_template() -> None:
    """app.py.jinja must register hooks in I9-mandated order."""
    text = (TEMPLATE_DIR / "{{project_name}}" / "app.py.jinja").read_text()
    hooks_in_order = [
        "DatabaseLifespanHook",
        "AuthLifespanHook",
        "RateLimitLifespanHook",
        "TracingLifespanHook",
        "AdminLifespanHook",
    ]
    positions = [(text.find(h), h) for h in hooks_in_order if h in text]
    positions.sort()
    found_order = [h for _, h in positions]
    expected_order = [h for h in hooks_in_order if h in text]
    assert found_order == expected_order, f"I9 hook order violated. Expected {expected_order}, got {found_order}"


# ---------------------------------------------------------------------------
# Phase 7: new template files exist
# ---------------------------------------------------------------------------

_PHASE7_TEMPLATE_FILES = [
    "Dockerfile.jinja",
    "docker-compose.yml.jinja",
    "k8s/deployment.yaml.jinja",
    "k8s/service.yaml.jinja",
    "k8s/configmap.yaml.jinja",
    "{{project_name}}/schemas.py.jinja",
    "{{project_name}}/tasks.py.jinja",
]


def test_c5_phase7_template_files_exist() -> None:
    missing = [p for p in _PHASE7_TEMPLATE_FILES if not (TEMPLATE_DIR / p).exists()]
    assert not missing, f"Phase 7 template files missing: {missing}"


def test_c6_dockerfile_uses_python_version_variable() -> None:
    text = (TEMPLATE_DIR / "Dockerfile.jinja").read_text()
    assert "{{ python_version }}" in text
    assert "include_dockerfile" in text


def test_c7_docker_compose_uses_valkey_image() -> None:
    text = (TEMPLATE_DIR / "docker-compose.yml.jinja").read_text()
    assert "valkey/valkey" in text, "Must use Valkey image per ADR-006"


def test_c8_docker_compose_includes_worker_service() -> None:
    text = (TEMPLATE_DIR / "docker-compose.yml.jinja").read_text()
    assert "worker" in text
    assert 'task_broker != "none"' in text


def test_c9_docker_compose_includes_jaeger_when_tracing_jaeger() -> None:
    text = (TEMPLATE_DIR / "docker-compose.yml.jinja").read_text()
    assert "jaeger" in text
    assert 'tracing == "jaeger"' in text


def test_c10_app_template_rate_limit_passes_app_to_hook() -> None:
    text = (TEMPLATE_DIR / "{{project_name}}" / "app.py.jinja").read_text()
    assert "RateLimitLifespanHook(_settings, app=app)" in text


def test_c11_standard_preset_generates_dockerfile(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["new", "myproject", "--preset", "standard", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "Dockerfile").exists()
    assert (tmp_path / "docker-compose.yml").exists()


def test_c12_standard_app_py_wires_auth_hook(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "standard", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    app_py = (tmp_path / "myproject" / "app.py").read_text()
    assert "AuthLifespanHook" in app_py
    assert "auth_router" in app_py


def test_c13_full_preset_app_py_has_all_hooks(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "full", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    app_py = (tmp_path / "myproject" / "app.py").read_text()
    assert "DatabaseLifespanHook" in app_py
    assert "AuthLifespanHook" in app_py
    assert "RateLimitLifespanHook" in app_py
    assert "TracingLifespanHook" in app_py
    assert "AdminLifespanHook" in app_py


def test_f4_second_new_same_dir_succeeds_with_overwrite(tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    result = runner.invoke(
        app,
        ["new", "myproject", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
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
        ["new", "smokeproj", "--preset", "minimal", "--db", "sqlite", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    # Put the project root on sys.path so `routes` resolves as a flat module.
    sys.path.insert(0, str(tmp_path))
    _cleanup = {"_smokeproj_main", "routes"}
    for key in list(sys.modules):
        if key in _cleanup:
            del sys.modules[key]

    try:
        spec = importlib.util.spec_from_file_location("_smokeproj_main", str(tmp_path / "main.py"))
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
