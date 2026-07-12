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
class TestPart1HelloWorld:
    part = TUTORIAL_DIR / "01-hello-world.md"

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
                pytest.fail(
                    f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}"
                )

    def test_cli_commands_use_fas_entry_point(self):
        """CLI command lines must start with 'fas' or 'fastagentstack' (ADR-001, ADR-027)."""
        fas_cmds = {"new ", "migrate", "dev", "run", "worker", "scheduler"}
        for fence in _bash_snippets(self.part):
            for line in fence.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(cmd in stripped for cmd in fas_cmds):
                    assert stripped.startswith("fas"), (
                        f"CLI line does not use 'fas' or 'fastagentstack': {stripped!r}"
                    )

    # 3. Architectural

    def test_no_private_imports_shown(self):
        """User-facing code must not import from fast_agent_stack.core.* (I12)."""
        for snippet in _python_snippets(self.part):
            assert "from fast_agent_stack.core" not in snippet, (
                "Tutorial exposes internal import path. Use the public API instead.\n"
                f"Snippet:\n{snippet}"
            )

    def test_import_name_uses_underscores(self):
        """Import name must be 'fast_agent_stack' (underscores), not 'fastagentstack' (ADR-001)."""
        for snippet in _python_snippets(self.part):
            assert "import fastagentstack" not in snippet, (
                "Tutorial uses wrong import name 'fastagentstack'."
            )

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
        assert "01-hello-world.md" in index_text, (
            "index.md does not reference 01-hello-world.md"
        )


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
        assert "01-hello-world.md" in self.part.read_text()

    def test_links_to_part3(self):
        assert "03-authentication.md" in self.part.read_text()

    # 2. Contract

    def test_python_snippets_compile(self):
        """Every Python code fence must be syntactically valid."""
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(
                    f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}"
                )

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
                "Tutorial exposes internal import path. Use the public API instead.\n"
                f"Snippet:\n{snippet}"
            )

    def test_import_name_uses_underscores(self):
        """Import name must be 'fast_agent_stack' (underscores), not 'fastagentstack' (ADR-001)."""
        for snippet in _python_snippets(self.part):
            assert "import fastagentstack" not in snippet, (
                "Tutorial uses wrong import name 'fastagentstack'."
            )

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
        assert "02-database-models.md" in index_text, (
            "index.md does not reference 02-database-models.md"
        )


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
        assert "01-hello-world.md" in self.part.read_text()

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
            assert any(link.endswith(ext) for ext in _ALLOWED), (
                f"Relative link targets unexpected file type: {link!r}"
            )

    def test_index_references_part0(self):
        """Tutorial index must reference 00-prerequisites.md."""
        index_text = (TUTORIAL_DIR / "index.md").read_text()
        assert "00-prerequisites.md" in index_text, (
            "index.md does not reference 00-prerequisites.md"
        )
