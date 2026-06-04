"""Base client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .protocol import CommandResult


class Client(ABC):
    """Abstract base for game clients."""

    @abstractmethod
    async def send_result(self, result: CommandResult) -> None: ...

    @abstractmethod
    async def get_input(self) -> str | None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...