"""Save provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SaveSlotInfo:
    name: str
    created_at: datetime
    modified_at: datetime
    player_name: str = ""
    player_level: int = 0
    turn_count: int = 0
    current_room_name: str = ""
    thumbnail: str = ""
    metadata: dict = field(default_factory=dict)


class SaveProvider(ABC):
    """A single save strategy."""

    @abstractmethod
    async def save(self, slot_name: str, world_state: dict) -> None: ...

    @abstractmethod
    async def load(self, slot_name: str) -> dict | None: ...

    @abstractmethod
    async def delete(self, slot_name: str) -> None: ...

    @abstractmethod
    async def list_slots(self) -> list[str]: ...