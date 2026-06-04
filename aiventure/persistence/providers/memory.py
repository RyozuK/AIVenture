"""In-memory save provider (for testing)."""

from __future__ import annotations

from datetime import datetime

from ..provider import SaveProvider


class MemoryProvider(SaveProvider):
    """Keeps saves in an in-memory dict.  Good for tests."""

    def __init__(self) -> None:
        self._stores: dict[str, dict] = {}

    async def save(self, slot_name: str, world_state: dict) -> None:
        self._stores[slot_name] = {
            "data": world_state,
            "saved_at": datetime.now().isoformat(),
        }

    async def load(self, slot_name: str) -> dict | None:
        entry = self._stores.get(slot_name)
        return entry["data"] if entry else None

    async def delete(self, slot_name: str) -> None:
        self._stores.pop(slot_name, None)

    async def list_slots(self) -> list[str]:
        return list(self._stores.keys())