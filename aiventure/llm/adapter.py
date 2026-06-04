"""LLM adapter interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A structured tool invocation returned by the LLM."""

    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """Raw response from the LLM backend."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    tokens_used: int = 0


ToolSchema = dict  # OpenAI-compatible tool definition dict


class LLMAdapter(ABC):
    """Interface for any LLM backend."""

    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        user_messages: list[str],
        tools: list[ToolSchema] | None = None,
        response_format: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            system_prompt: System-level instruction.
            user_messages: List of user message strings.
            tools: Optional tool definitions for function/tool calling.
            response_format: e.g. ``"json_object"``.
        """
        ...

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 256,
    ) -> str:
        """Simple text generation (no chat context, no tools)."""
        ...