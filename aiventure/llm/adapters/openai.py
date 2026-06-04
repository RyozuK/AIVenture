"""Official OpenAI SDK adapter."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from ..adapter import LLMAdapter, LLMResponse, ToolCall, ToolSchema


class OpenAIAdapter(LLMAdapter):
    """Adapter wrapping the official ``openai`` SDK."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.9,
        max_tokens: int = 1024,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = AsyncOpenAI(api_key=api_key)

    async def close(self) -> None:
        await self._client.close()

    async def chat(
        self,
        system_prompt: str,
        user_messages: list[str],
        tools: list[ToolSchema] | None = None,
        response_format: str | None = None,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
            ]
            + [{"role": "user", "content": msg} for msg in user_messages],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            body["tools"] = tools
        if response_format:
            body["response_format"] = {"type": response_format}

        resp = await self._client.chat.completions.create(**body)
        choice = resp.choices[0]
        message = choice.message

        tool_calls: list[ToolCall] = []
        for tc in (message.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(ToolCall(name=tc.function.name, arguments=args))

        return LLMResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            tokens_used=resp.usage.total_tokens if resp.usage else 0,
        )

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 256,
    ) -> str:
        resp = await self.chat(
            system_prompt="You are a helpful assistant.",
            user_messages=[prompt],
        )
        return resp.text