"""Command router — maps parsed verbs to action handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .parser import ParsedCommand


@dataclass
class CommandRouter:
    """Dispatches parsed commands to registered action handler coroutines.

    Handlers have the signature::

        async handler(session, target: str) -> dict
    """

    _handlers: dict[str, Callable[..., Awaitable[dict]]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._handlers is None:
            self._handlers = {}

    def register(
        self,
        verb: str,
        handler: Callable[..., Awaitable[dict]],
    ) -> None:
        self._handlers[verb] = handler

    async def dispatch(
        self,
        parsed: ParsedCommand,
        session: object,
    ) -> dict:
        handler = self._handlers.get(parsed.verb)
        if handler is None:
            return {
                "narrative": f"I don't understand the command: {parsed.verb}",
                "state": {},
            }
        return await handler(session, target=parsed.target)