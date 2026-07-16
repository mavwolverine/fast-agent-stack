"""Public LLM backend re-exports.

Backends are optional extras - importing a backend raises ImportError with the install
command if the matching extras package is not installed (I3).
Imports are lazy so this module itself is importable without any extra installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend
    from fast_agent_stack.core.ai.llm.bedrock import BedrockLLMBackend
    from fast_agent_stack.core.ai.llm.litellm import LiteLLMLLMBackend
    from fast_agent_stack.core.ai.llm.openai import OpenAILLMBackend

__all__ = ["OpenAILLMBackend", "AnthropicLLMBackend", "BedrockLLMBackend", "LiteLLMLLMBackend"]


def __getattr__(name: str) -> object:
    if name == "OpenAILLMBackend":
        from fast_agent_stack.core.ai.llm.openai import OpenAILLMBackend

        return OpenAILLMBackend
    if name == "AnthropicLLMBackend":
        from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend

        return AnthropicLLMBackend
    if name == "BedrockLLMBackend":
        from fast_agent_stack.core.ai.llm.bedrock import BedrockLLMBackend

        return BedrockLLMBackend
    if name == "LiteLLMLLMBackend":
        from fast_agent_stack.core.ai.llm.litellm import LiteLLMLLMBackend

        return LiteLLMLLMBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
