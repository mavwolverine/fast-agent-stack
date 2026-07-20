"""Public AI facade - re-exports LLM types, tool utilities, and agent helpers."""

from fast_agent_stack.core.ai.llm import CompletionResult, LLMBackend, Message, ToolCall, ToolCallResult, get_llm
from fast_agent_stack.core.ai.tools import Tool, agent_loop, tool

__all__ = [
    "Message",
    "CompletionResult",
    "LLMBackend",
    "ToolCall",
    "ToolCallResult",
    "get_llm",
    "tool",
    "Tool",
    "agent_loop",
]
