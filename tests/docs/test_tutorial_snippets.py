"""Tutorial documentation quality tests.

Validates that tutorial markdown files exist, have required structure, and that all
Python code snippets are syntactically valid.

Families covered:
  1. Behavior   — file/section existence, through-line app mentioned
  2. Contract   — Python fences compile; CLI uses correct entry-point names; public API only
  3. Architectural — no fast_agent_stack.core.* shown to users; import name correct
  4. NFR        — reasonable word count; next-steps link present
  5. Failure-mode — relative links target .md files

Run with: pytest tests/docs/ -m docs
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

TUTORIAL_DIR = Path(__file__).parents[2] / "docs" / "tutorial"

_PY_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_BASH_FENCE_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)
_MD_LINK_RE = re.compile(r"\[.*?\]\((.*?)\)")


def _python_snippets(path: Path) -> list[str]:
    return _PY_FENCE_RE.findall(path.read_text())


def _bash_snippets(path: Path) -> list[str]:
    return _BASH_FENCE_RE.findall(path.read_text())


# ---------------------------------------------------------------------------
# Part 1 — Hello World
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart1Scaffold:
    part = TUTORIAL_DIR / "01-scaffold.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_tutorial_index_exists(self):
        assert (TUTORIAL_DIR / "index.md").exists(), "Missing docs/tutorial/index.md"

    def test_has_prerequisites_section(self):
        assert "Prerequisite" in self.part.read_text()

    def test_mentions_through_line_app(self):
        text = self.part.read_text()
        assert "Document Q&A" in text or "docqa" in text.lower()

    def test_links_to_part2(self):
        assert "02-database-models.md" in self.part.read_text()

    def test_has_scaffold_instructions(self):
        text = self.part.read_text()
        assert "fas new" in text or "fastagentstack new" in text

    # 2. Contract

    def test_has_python_snippets(self):
        assert _python_snippets(self.part), "Part 1 has no Python code snippets"

    def test_python_snippets_compile(self):
        """Every Python code fence must be syntactically valid."""
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_cli_commands_use_fas_entry_point(self):
        """CLI command lines must start with 'fas' or 'fastagentstack' (ADR-001, ADR-027)."""
        fas_cmds = {"new ", "migrate", "dev", "run", "worker", "scheduler"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(cmd in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), f"CLI line does not use 'fas' or 'fastagentstack': {stripped!r}"

    # 3. Architectural

    def test_no_private_imports_shown(self):
        """User-facing code must not import from fast_agent_stack.core.* (I12)."""
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet, (
                f"Tutorial exposes internal import path. Use the public API instead.\nSnippet:\n{snippet}"
            )

    def test_import_name_uses_underscores(self):
        """Import name must be 'fast_agent_stack' (underscores), not 'fastagentstack' (ADR-001)."""
        for snippet in _python_snippets(self.part):
            assert "import fastagentstack" not in snippet, "Tutorial uses wrong import name 'fastagentstack'."

    # 4. NFR

    def test_reasonable_word_count(self):
        """Tutorial part should be readable in a single sitting (< 2 500 words)."""
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 1 is {words} words — consider splitting"

    def test_has_next_steps(self):
        text = self.part.read_text()
        assert "Next" in text or "next steps" in text.lower()

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        """All relative links (non-anchor, non-URL) must point to .md files."""
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"

    def test_index_links_use_new_naming(self):
        """Tutorial index must reference the descriptive file naming convention."""
        index_text = (TUTORIAL_DIR / "index.md").read_text()
        assert "01-scaffold.md" in index_text, "index.md does not reference 01-scaffold.md"

    # Rewrite-enforcement: agent preset (ROADMAP Phase 10.1)

    def test_uses_agent_preset(self):
        """ROADMAP requires --preset agent."""
        assert "--preset agent" in self.part.read_text(), (
            "Part 1 must scaffold with --preset agent (ROADMAP Phase 10.1)"
        )

    def test_shows_ai_agents_package(self):
        """Part 1 must explain the generated ai/agents/ package."""
        assert "ai/agents/__init__.py" in self.part.read_text()

    def test_links_to_part0(self):
        """Part 1 must reference Part 0 (services must be running)."""
        assert "00-prerequisites.md" in self.part.read_text()

    def test_uses_postgres_database_url(self):
        """Agent preset uses PostgreSQL — must show the postgresql+asyncpg URL."""
        assert "postgresql+asyncpg" in self.part.read_text()


# ---------------------------------------------------------------------------
# Part 2 — Database & Models
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart2DatabaseModels:
    part = TUTORIAL_DIR / "02-database-models.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_mentions_document_model(self):
        text = self.part.read_text()
        assert "Document" in text, "Through-line model 'Document' not mentioned"

    def test_has_migration_section(self):
        text = self.part.read_text()
        assert "makemigrations" in text or "migration" in text.lower()

    def test_links_to_part1(self):
        assert "01-scaffold.md" in self.part.read_text()

    def test_links_to_part3(self):
        assert "03-authentication.md" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        """Every Python code fence must be syntactically valid."""
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_uses_get_async_session(self):
        assert "get_async_session" in self.part.read_text()

    def test_basemodel_from_database(self):
        text = self.part.read_text()
        assert "fast_agent_stack.database" in text and "BaseModel" in text

    def test_document_create_schema_defined(self):
        assert "DocumentCreate" in self.part.read_text()

    def test_document_response_schema_defined(self):
        assert "DocumentResponse" in self.part.read_text()

    # 3. Architectural

    def test_no_private_imports_shown(self):
        """User-facing code must not import from fast_agent_stack.core.* (I12)."""
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet, (
                f"Tutorial exposes internal import path. Use the public API instead.\nSnippet:\n{snippet}"
            )

    def test_import_name_uses_underscores(self):
        """Import name must be 'fast_agent_stack' (underscores), not 'fastagentstack' (ADR-001)."""
        for snippet in _python_snippets(self.part):
            assert "import fastagentstack" not in snippet, "Tutorial uses wrong import name 'fastagentstack'."

    # 4. NFR

    def test_reasonable_word_count(self):
        """Tutorial part should be readable in a single sitting (< 2 500 words)."""
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 2 is {words} words — consider splitting"

    def test_has_what_you_built(self):
        assert "What you built" in self.part.read_text()

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        """All relative links (non-anchor, non-URL) must point to .md files."""
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"

    def test_index_references_part2(self):
        """Tutorial index must reference 02-database-models.md."""
        index_text = (TUTORIAL_DIR / "index.md").read_text()
        assert "02-database-models.md" in index_text, "index.md does not reference 02-database-models.md"


# ---------------------------------------------------------------------------
# Part 0 — Prerequisites
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart0Prerequisites:
    part = TUTORIAL_DIR / "00-prerequisites.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_tutorial_index_exists(self):
        assert (TUTORIAL_DIR / "index.md").exists(), "Missing docs/tutorial/index.md"

    def test_has_docker_compose_section(self):
        text = self.part.read_text()
        assert "docker" in text.lower() or "Docker Compose" in text

    def test_has_ollama_section(self):
        assert "Ollama" in self.part.read_text() or "ollama" in self.part.read_text()

    def test_mentions_through_line_app(self):
        text = self.part.read_text()
        assert "Document Q&A" in text or "docqa" in text.lower()

    def test_links_to_part1(self):
        assert "01-scaffold.md" in self.part.read_text()

    # 2. Contract

    def test_has_bash_snippets(self):
        assert _bash_snippets(self.part), "Part 0 has no bash snippets"

    def test_has_ollama_pull_commands(self):
        text = self.part.read_text()
        assert "ollama pull" in text, "Part 0 must show ollama pull commands"

    def test_docker_compose_file_exists(self):
        """Standalone docker-compose.yml must exist alongside the tutorial docs."""
        assert (TUTORIAL_DIR / "docker-compose.yml").exists(), (
            "docs/tutorial/docker-compose.yml missing — readers need it to copy/curl directly"
        )

    def test_docker_compose_yaml_linked_and_run(self):
        """The doc must link to docker-compose.yml and show the up command."""
        text = self.part.read_text()
        assert "docker-compose.yml" in text, "Part 0 must link to docker-compose.yml"
        assert "docker compose up" in text or "docker-compose up" in text

    def test_has_env_example(self):
        """Part 0 must show the .env variables needed before Part 1."""
        text = self.part.read_text()
        assert "DATABASE_URL" in text or ".env" in text

    # 3. Architectural

    def test_no_private_imports_shown(self):
        """Part 0 has no Python code, but guard anyway."""
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet

    def test_service_ports_mentioned(self):
        """Must mention enough for a user to verify services are up."""
        text = self.part.read_text()
        # At least one of the three service ports/URLs
        assert any(marker in text for marker in ("5432", "6379", "6333", "localhost")), (
            "Part 0 should mention service addresses so users can verify setup"
        )

    def test_uses_correct_redis_image(self):
        """Must use valkey (not legacy redis image) — matches scaffolded docker-compose."""
        text = self.part.read_text()
        assert "valkey" in text, "docker-compose in Part 0 must use valkey/valkey image"

    # 4. NFR

    def test_reasonable_word_count(self):
        """Prerequisites guide should be concise (< 2000 words)."""
        words = len(self.part.read_text().split())
        assert words < 2000, f"Part 0 is {words} words — consider trimming"

    def test_has_verification_step(self):
        """Part 0 must tell users how to verify services are running."""
        text = self.part.read_text()
        assert any(w in text.lower() for w in ("verify", "check", "confirm", "healthz", "ping")), (
            "Part 0 must include a verification step"
        )

    # 5. Failure-mode

    def test_relative_links_target_known_file_types(self):
        """Relative links must target .md or known companion file types (.yml, .yaml)."""
        _ALLOWED = (".md", ".yml", ".yaml")
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert any(link.endswith(ext) for ext in _ALLOWED), f"Relative link targets unexpected file type: {link!r}"

    def test_index_references_part0(self):
        """Tutorial index must reference 00-prerequisites.md."""
        index_text = (TUTORIAL_DIR / "index.md").read_text()
        assert "00-prerequisites.md" in index_text, "index.md does not reference 00-prerequisites.md"


# ---------------------------------------------------------------------------
# Part 3 — Authentication
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart3Authentication:
    part = TUTORIAL_DIR / "03-authentication.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_mentions_through_line_app(self):
        text = self.part.read_text()
        assert "Document Q&A" in text or "docqa" in text.lower()

    def test_links_to_part2(self):
        assert "02-database-models.md" in self.part.read_text()

    def test_links_to_part4(self):
        assert "04-ingestion-agent.md" in self.part.read_text()

    def test_shows_fas_migrate(self):
        assert "fas migrate" in self.part.read_text()

    def test_shows_fas_createsuperuser(self):
        assert "createsuperuser" in self.part.read_text()

    def test_shows_auth_token_endpoint(self):
        assert "auth/token" in self.part.read_text()

    def test_has_what_you_built(self):
        assert "What you built" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_shows_get_current_user(self):
        assert "get_current_user" in self.part.read_text()

    def test_shows_auth_refresh_endpoint(self):
        assert "auth/refresh" in self.part.read_text()

    def test_shows_secret_key(self):
        assert "SECRET_KEY" in self.part.read_text()

    def test_no_admin_secret_key(self):
        """ADR-049: admin_secret_key removed — tutorial must not mention it."""
        assert "ADMIN_SECRET_KEY" not in self.part.read_text()

    def test_cli_commands_use_fas_entry_point(self):
        fas_cmds = {"new ", "migrate", "dev", "run", "worker", "createsuperuser"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(cmd in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), f"CLI line does not use 'fas' entry point: {stripped!r}"

    # 3. Architectural

    def test_no_private_imports_shown(self):
        """User-facing code must not import from fast_agent_stack.core.* (I12)."""
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet, (
                f"Tutorial exposes internal import path. Use the public API instead.\nSnippet:\n{snippet}"
            )

    def test_import_uses_public_auth_facade(self):
        """Tutorial must import from fast_agent_stack.auth (public facade), not .core.auth."""
        text = self.part.read_text()
        assert "fast_agent_stack.auth" in text, (
            "Tutorial must show 'from fast_agent_stack.auth import ...' for user-facing auth symbols"
        )

    def test_import_name_uses_underscores(self):
        for snippet in _python_snippets(self.part):
            assert "import fastagentstack" not in snippet

    # 4. NFR

    def test_reasonable_word_count(self):
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 3 is {words} words — consider splitting"

    def test_has_next_steps(self):
        text = self.part.read_text()
        assert "Next" in text or "next steps" in text.lower()

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"

    def test_index_references_part3(self):
        index_text = (TUTORIAL_DIR / "index.md").read_text()
        assert "03-authentication.md" in index_text


# ---------------------------------------------------------------------------
# Part 4 — Ingestion Agent
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart4IngestionAgent:
    part = TUTORIAL_DIR / "04-ingestion-agent.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_links_to_part3(self):
        assert "03-authentication.md" in self.part.read_text()

    def test_links_to_part5(self):
        assert "05-chat-agent.md" in self.part.read_text()

    def test_mentions_upload(self):
        assert "upload" in self.part.read_text().lower()

    def test_mentions_qdrant_or_vector(self):
        text = self.part.read_text().lower()
        assert "qdrant" in text or "vector" in text

    def test_mentions_background_task(self):
        assert "BackgroundTask" in self.part.read_text()

    def test_has_what_you_built(self):
        assert "What you built" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_shows_rag_service(self):
        assert "RagService" in self.part.read_text()

    def test_shows_ingest_file(self):
        assert "ingest_file" in self.part.read_text()

    def test_shows_status_field(self):
        assert "status" in self.part.read_text()

    def test_shows_upload_endpoint(self):
        assert "/documents/upload" in self.part.read_text()

    def test_cli_commands_use_fas_entry_point(self):
        fas_cmds = {"migrate", "dev", "run", "makemigrations"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(cmd in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), f"CLI line does not use 'fas' entry point: {stripped!r}"

    # 3. Architectural

    def test_no_private_imports_shown(self):
        """User-facing code must not import from fast_agent_stack.core.* (I12)."""
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet, (
                f"Tutorial exposes internal import path.\nSnippet:\n{snippet}"
            )

    def test_uses_public_rag_facade(self):
        """Tutorial must import RagService from fast_agent_stack.rag (public facade)."""
        text = self.part.read_text()
        assert "fast_agent_stack.rag" in text

    def test_uses_public_auth_facade(self):
        text = self.part.read_text()
        assert "fast_agent_stack.auth" in text

    def test_import_name_uses_underscores(self):
        for snippet in _python_snippets(self.part):
            assert "import fastagentstack" not in snippet

    # 4. NFR

    def test_reasonable_word_count(self):
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 4 is {words} words — consider splitting"

    def test_has_next_steps(self):
        text = self.part.read_text()
        assert "Next" in text or "next steps" in text.lower()

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"


# ---------------------------------------------------------------------------
# Part 5 — Chat Agent with Tools
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart5ChatAgent:
    part = TUTORIAL_DIR / "05-chat-agent.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_links_to_part4(self):
        assert "04-ingestion-agent.md" in self.part.read_text()

    def test_links_to_part6(self):
        assert "06-chat-ui.md" in self.part.read_text()

    def test_mentions_agent_loop(self):
        assert "agent_loop" in self.part.read_text()

    def test_mentions_tool_decorator(self):
        text = self.part.read_text()
        assert "@tool" in text or "tool(" in text

    def test_mentions_streaming(self):
        text = self.part.read_text().lower()
        assert "sse" in text or "stream" in text

    def test_has_what_you_built(self):
        assert "What you built" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_shows_search_tool(self):
        assert "search_docs" in self.part.read_text()

    def test_shows_app_agent_registration(self):
        assert "app.agent" in self.part.read_text()

    def test_agent_registration_targets_ai_agents_package(self):
        """Tutorial must instruct the user to edit ai/agents/__init__.py, not app.py directly."""
        text = self.part.read_text()
        assert "ai/agents/__init__.py" in text
        assert "register_agents" in text

    def test_agent_endpoint_requires_auth(self):
        """Chat agent must be protected with get_current_user (not open to anonymous requests)."""
        text = self.part.read_text()
        assert "get_current_user" in text
        assert "dependencies" in text

    def test_shows_curl_example(self):
        assert "curl" in self.part.read_text().lower()

    def test_cli_commands_use_fas_entry_point(self):
        fas_cmds = {"dev", "run"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(cmd in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), f"CLI line does not use 'fas' entry point: {stripped!r}"

    # 3. Architectural

    def test_no_private_imports_shown(self):
        """User-facing code must not import from fast_agent_stack.core.* (I12)."""
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet, (
                f"Tutorial exposes internal import path.\nSnippet:\n{snippet}"
            )

    def test_uses_public_ai_facade(self):
        """Tutorial must import tool/agent_loop from fast_agent_stack.ai (public facade)."""
        assert "fast_agent_stack.ai" in self.part.read_text()

    def test_uses_public_rag_facade(self):
        assert "fast_agent_stack.rag" in self.part.read_text()

    # 4. NFR

    def test_reasonable_word_count(self):
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 5 is {words} words — consider splitting"

    def test_has_next_steps(self):
        text = self.part.read_text()
        assert "Next" in text or "next steps" in text.lower()

    def test_no_emdashes(self):
        assert "—" not in self.part.read_text(), "Found em-dash in Part 5"

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"


# ---------------------------------------------------------------------------
# Part 6 — Chat UI
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart6ChatUI:
    part = TUTORIAL_DIR / "06-chat-ui.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_links_to_part5(self):
        assert "05-chat-agent.md" in self.part.read_text()

    def test_links_to_part7(self):
        assert "07-background-tasks.md" in self.part.read_text()

    def test_mentions_frontend_method(self):
        assert "frontend(" in self.part.read_text()

    def test_mentions_streaming(self):
        text = self.part.read_text().lower()
        assert "sse" in text or "stream" in text

    def test_has_what_you_built(self):
        assert "What you built" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_shows_stack_frontend_call(self):
        assert "_stack.frontend(" in self.part.read_text()

    def test_shows_fetch_reader_not_eventsource(self):
        text = self.part.read_text()
        assert "getReader" in text, "Must show fetch()+getReader() for POST SSE"
        assert "EventSource" not in text, "EventSource does not support POST endpoints"

    def test_cli_commands_use_fas_entry_point(self):
        fas_cmds = {"dev", "run"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(cmd in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), f"CLI line does not use 'fas' entry point: {stripped!r}"

    # 3. Architectural

    def test_no_private_imports_shown(self):
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet

    # 4. NFR

    def test_reasonable_word_count(self):
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 6 is {words} words - consider splitting"

    def test_has_next_steps(self):
        text = self.part.read_text()
        assert "Next" in text or "next steps" in text.lower()

    def test_no_emdashes(self):
        assert "—" not in self.part.read_text(), "Found em-dash in Part 6"

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"


# ---------------------------------------------------------------------------
# Part 7 - Background Tasks
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart7BackgroundTasks:
    part = TUTORIAL_DIR / "07-background-tasks.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_links_to_part6(self):
        assert "06-chat-ui.md" in self.part.read_text()

    def test_links_to_part8(self):
        assert "08-production.md" in self.part.read_text()

    def test_mentions_dramatiq(self):
        assert "dramatiq" in self.part.read_text().lower()

    def test_mentions_periodiq(self):
        assert "periodiq" in self.part.read_text().lower()

    def test_has_what_you_built(self):
        assert "What you built" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_shows_actor_send(self):
        assert ".send(" in self.part.read_text()

    def test_shows_configure_broker(self):
        assert "configure_broker" in self.part.read_text()

    def test_no_background_tasks_import(self):
        for snippet in _python_snippets(self.part):
            assert "BackgroundTasks" not in snippet, (
                "Tutorial must not import BackgroundTasks - ingestion moved to Dramatiq"
            )

    def test_cli_commands_use_fas_entry_point(self):
        fas_cmds = {"dev", "worker", "scheduler"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(stripped.startswith(cmd) or f" {cmd}" in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), f"CLI line does not use 'fas' entry point: {stripped!r}"

    # 3. Architectural

    def test_no_private_imports_shown(self):
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet

    # 4. NFR

    def test_reasonable_word_count(self):
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 7 is {words} words - consider splitting"

    def test_has_next_steps(self):
        text = self.part.read_text()
        assert "Next" in text or "next steps" in text.lower()

    def test_no_emdashes(self):
        assert "—" not in self.part.read_text(), "Found em-dash in Part 7"
        assert "–" not in self.part.read_text(), "Found en-dash in Part 7"

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"


# ---------------------------------------------------------------------------
# Part 8 - Production
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPart8Production:
    part = TUTORIAL_DIR / "08-production.md"

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_links_to_part7(self):
        assert "07-background-tasks.md" in self.part.read_text()

    def test_links_to_index(self):
        assert "index.md" in self.part.read_text()

    def test_mentions_rate_limiting(self):
        assert "rate" in self.part.read_text().lower()

    def test_mentions_jaeger(self):
        assert "jaeger" in self.part.read_text().lower()

    def test_mentions_docker_compose(self):
        assert "docker compose" in self.part.read_text().lower()

    def test_has_what_you_built(self):
        assert "What you built" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_shows_tracing_lifespan_hook(self):
        assert "TracingLifespanHook" in self.part.read_text()

    def test_cli_commands_use_fas_entry_point(self):
        fas_cmds = {"dev", "run"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(cmd in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), f"CLI line does not use 'fas' entry point: {stripped!r}"

    # 3. Architectural

    def test_no_private_imports_shown(self):
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet

    # 4. NFR

    def test_reasonable_word_count(self):
        words = len(self.part.read_text().split())
        assert words < 2500, f"Part 8 is {words} words - consider splitting"

    def test_is_final_part(self):
        text = self.part.read_text()
        assert "index.md" in text, "Final part must link back to tutorial index"
        assert "09-" not in text, "Part 8 must not link to a non-existent Part 9"

    def test_no_emdashes(self):
        assert "—" not in self.part.read_text(), "Found em-dash in Part 8"
        assert "–" not in self.part.read_text(), "Found en-dash in Part 8"

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"
