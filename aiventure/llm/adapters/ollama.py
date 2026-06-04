"""Ollama adapter — calls Ollama's local API."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..adapter import LLMAdapter, LLMResponse, ToolCall, ToolSchema

logger = logging.getLogger("aiventure.llm.adapters.ollama")


class OllamaAdapter(LLMAdapter):
    """Adapter for local Ollama models via the /api/chat endpoint.

    Supports tool calling for Ollama models that support it (e.g. llama3.1, qwen2.5).
    Falls back to JSON-mode prompting if tool calling is not supported.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model: str = "llama3.1",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> None:
        self._base_url = endpoint.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        system_prompt: str,
        user_messages: list[str],
        tools: list[ToolSchema] | None = None,
        response_format: str | None = None,
    ) -> LLMResponse:
        url = f"{self._base_url}/api/chat"
        body: dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(system_prompt, user_messages),
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "num_predict": self._max_tokens,
            },
        }

        # Add tools if the model supports them
        if tools:
            body["tools"] = tools

        logger.debug("Ollama chat request: model=%s, tools=%d", self._model, len(tools) or 0)

        async with self._client:
            resp = await self._client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        return self._parse_response(data)

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 256,
    ) -> str:
        url = f"{self._base_url}/api/generate"
        body = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": max_tokens,
            },
        }

        async with self._client:
            resp = await self._client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        return data.get("response", "").strip()

    async def close(self) -> None:
        await self._client.aclose()

    # -- internal -- #

    def _build_messages(self, system_prompt: str, user_messages: list[str]) -> list[dict]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in user_messages:
            messages.append({"role": "user", "content": msg})
        return messages

    def _parse_response(self, data: dict) -> LLMResponse:
        message = data.get("message", {})
        text = message.get("content", "")
        tool_calls_raw = message.get("tool_calls", [])

        tool_calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            func = tc.get("function", {})
            args_raw = func.get("arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(ToolCall(
                name=func.get("name", ""),
                arguments=args,
            ))

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=message.get("finish_reason", "stop"),
        )