"""OpenAI-compatible adapter — works with OpenAI, LM Studio, vLLM, etc."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..adapter import LLMAdapter, LLMResponse, ToolCall, ToolSchema


class OpenAICompatibleAdapter(LLMAdapter):
    """Adapter for any OpenAI-compatible REST endpoint."""

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.9,
        max_tokens: int = 1024,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=self._endpoint,
            headers=headers,
            timeout=httpx.Timeout(120.0, connect=30.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

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

        resp = await self._client.post("/chat/completions", json=body)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice.get("message", {})

        # Parse tool calls
        tool_calls: list[ToolCall] = []
        raw_tool_calls = message.get("tool_calls") or []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            args_raw = func.get("arguments", "{}")
            try:
                args = json.loads(args_raw)
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(ToolCall(name=func.get("name", ""), arguments=args))

        return LLMResponse(
            text=message.get("content", "") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
        )

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 256,
    ) -> str:
        resp = await self.chat(system_prompt="You are a helpful assistant.", user_messages=[prompt])
        return resp.text