"""Pydantic AI guide documentation quality tests.

Validates that the framework-integration guide pages exist and that all Python code
snippets in the Pydantic AI guide are syntactically valid and free of drift (no internal
`fast_agent_stack.core.*` imports leaking to users, no invented multi-agent/session-manager
API names, no em-dashes, working relative links).

Families covered:
  1. Behavior      - file existence, section presence, companion-edit links
  2. Contract      - Python fences compile; CLI uses correct entry-point name
  3. Architectural - no fast_agent_stack.core.* shown to users; no AsyncRedisDep misuse;
                     no invented GraphBuilder/Swarm/session-manager equivalents;
                     configure_broker/configure_engine called at module level, not per-invocation
  4. NFR           - no em-dash/en-dash
  5. Failure-mode  - relative links target .md files

Run with: pytest tests/docs/ -m docs
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

GUIDES_DIR = Path(__file__).parents[2] / "docs" / "guides"
PYDANTIC_AI_GUIDE = GUIDES_DIR / "framework-integration" / "pydantic-ai.md"
FRAMEWORK_INTEGRATION_INDEX = GUIDES_DIR / "framework-integration" / "index.md"
TUTORIAL_PART5 = Path(__file__).parents[2] / "docs" / "tutorial" / "05-chat-agent.md"

_PY_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_BASH_FENCE_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)
_MD_LINK_RE = re.compile(r"\[.*?\]\((.*?)\)")
_INVENTED_SESSION_MANAGER_RE = re.compile(r"Pydantic\w*SessionManager")


def _python_snippets(path: Path) -> list[str]:
    return _PY_FENCE_RE.findall(path.read_text())


def _bash_snippets(path: Path) -> list[str]:
    return _BASH_FENCE_RE.findall(path.read_text())


# ---------------------------------------------------------------------------
# Companion edits (framework-integration/index.md, tutorial Part 5 branch table)
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPydanticAiCompanionEdits:
    def test_framework_integration_index_links_to_pydantic_ai(self):
        text = FRAMEWORK_INTEGRATION_INDEX.read_text()
        assert "Pydantic AI *(planned)*" not in text
        assert "(pydantic-ai.md)" in text

    def test_tutorial_part5_links_to_pydantic_ai_guide(self):
        text = TUTORIAL_PART5.read_text()
        assert "Pydantic AI *(planned)*" not in text
        assert "../guides/framework-integration/pydantic-ai.md" in text

    def test_no_emdashes(self):
        for path in (FRAMEWORK_INTEGRATION_INDEX, TUTORIAL_PART5):
            text = path.read_text()
            assert "—" not in text, f"Found em-dash in {path.name}"
            assert "–" not in text, f"Found en-dash in {path.name}"

    def test_relative_links_target_md_files(self):
        for path in (FRAMEWORK_INTEGRATION_INDEX, TUTORIAL_PART5):
            for link in _MD_LINK_RE.findall(path.read_text()):
                if link.startswith("#") or link.startswith("http"):
                    continue
                assert link.endswith(".md"), f"{path.name}: relative link does not target a .md file: {link!r}"


# ---------------------------------------------------------------------------
# Pydantic AI guide
# ---------------------------------------------------------------------------


@pytest.mark.docs
class TestPydanticAiGuide:
    part = PYDANTIC_AI_GUIDE

    # 1. Behavior

    def test_file_exists(self):
        assert self.part.exists(), f"Missing: {self.part}"

    def test_links_back_to_overview(self):
        assert "index.md" in self.part.read_text()

    def test_has_getting_started_section(self):
        assert "## Getting Started" in self.part.read_text()

    def test_has_infra_section(self):
        assert "Using fast-agent-stack Infra from Pydantic AI" in self.part.read_text()

    def test_has_api_surface_admonition(self):
        text = self.part.read_text()
        assert "Pydantic AI" in text
        assert any(phrase in text for phrase in ("fast-moving", "check the", "before copying"))

    # 2. Contract

    def test_python_snippets_compile(self):
        for snippet in _python_snippets(self.part):
            try:
                ast.parse(textwrap.dedent(snippet))
            except SyntaxError as exc:
                pytest.fail(f"Snippet failed to parse:\n{exc}\n\nSnippet:\n{snippet}")

    def test_public_facade_imports_present(self):
        text = "\n".join(_python_snippets(self.part))
        for facade in (
            "from fast_agent_stack.rag import",
            "from fast_agent_stack.storage import",
            "from fast_agent_stack.auth import",
            "from fast_agent_stack.database import",
        ):
            assert facade in text, f"Expected {facade!r} to appear in a code snippet"

    def test_cli_commands_use_fas_entry_point(self):
        fas_cmds = {"dev", "run", "migrate", "makemigrations"}
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
            assert "from fast_agent_stack.core" not in snippet, (
                "Guide must import from public facades (fast_agent_stack.rag/.storage/.database/"
                ".auth/.ai/.tasks), never fast_agent_stack.core.* directly"
            )

    def test_no_async_redis_dep_in_tool_code(self):
        for snippet in _python_snippets(self.part):
            assert "AsyncRedisDep" not in snippet, (
                "AsyncRedisDep requires FastAPI request-scoped DI and is unreachable from a "
                "Pydantic AI tool - must not appear as an import/usage in tool code snippets"
            )

    def test_no_invented_multiagent_classes(self):
        text = self.part.read_text()
        assert "GraphBuilder" not in text, "GraphBuilder is a Strands-specific class, not Pydantic AI's"
        assert "Swarm" not in text, "Swarm is a Strands-specific class, not Pydantic AI's"
        assert "pydantic-graph" in text or "pydantic_graph" in text, (
            "Multi-Agent Patterns section must point to pydantic-graph for complex orchestration"
        )

    def test_no_invented_session_manager_class(self):
        text = self.part.read_text()
        assert not _INVENTED_SESSION_MANAGER_RE.search(text), (
            "No fabricated Pydantic-AI-specific session-manager class name - Pydantic AI has no "
            "bundled equivalent to Strands' ValkeySessionManager"
        )

    def test_configure_calls_are_module_level_not_per_invocation(self):
        """configure_broker/configure_engine must run once at import time, not inside a function body."""
        for snippet in _python_snippets(self.part):
            if "configure_broker(" not in snippet and "configure_engine(" not in snippet:
                continue
            tree = ast.parse(textwrap.dedent(snippet))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for inner in ast.walk(node):
                        if (
                            isinstance(inner, ast.Call)
                            and isinstance(inner.func, ast.Name)
                            and inner.func.id in {"configure_broker", "configure_engine"}
                        ):
                            pytest.fail(f"{inner.func.id}() must be called at module level, not inside {node.name}()")

    # 4. NFR

    def test_no_emdashes(self):
        text = self.part.read_text()
        assert "—" not in text, "Found em-dash in Pydantic AI guide"
        assert "–" not in text, "Found en-dash in Pydantic AI guide"

    def test_reasonable_word_count(self):
        assert len(self.part.read_text().split()) < 3000

    # 5. Failure-mode

    def test_relative_links_target_md_files(self):
        for link in _MD_LINK_RE.findall(self.part.read_text()):
            if link.startswith("#") or link.startswith("http"):
                continue
            assert link.endswith(".md"), f"Relative link does not target a .md file: {link!r}"
