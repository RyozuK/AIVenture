"""Save manager — multi-slot orchestration."""

from __future__ import annotations

import logging
from datetime import datetime

from aiventure.model import World

from .provider import SaveProvider, SaveSlotInfo

logger = logging.getLogger("aiventure.persistence.manager")


class SaveManager:
    """Manages multiple save slots with a chosen provider."""

    def __init__(self, provider: SaveProvider) -> None:
        self._provider = provider

    async def auto_save(self, slot_name: str, world: World) -> None:
        """Save the current world state to *slot_name*."""
        try:
            data = world.to_dict()
            await self._provider.save(slot_name, data)
            logger.debug("Auto-saved slot '%s' (turn %d)", slot_name, world.turn_count)
        except Exception:
            logger.exception("Auto-save failed for slot '%s'", slot_name)

    async def save(self, slot_name: str, world: World) -> None:
        """Explicit manual save."""
        await self.auto_save(slot_name, world)

    async def load_slot(self, slot_name: str) -> World | None:
        """Load a world from *slot_name*."""
        data = await self._provider.load(slot_name)
        if data is None:
            return None
        try:
            world = World.from_dict(data)
            logger.info("Loaded slot '%s' (turn %d)", slot_name, world.turn_count)
            return world
        except Exception:
            logger.exception("Failed to load slot '%s'", slot_name)
            return None

    async def create_slot(self, slot_name: str, world: World) -> None:
        """Create a new save slot from the current world."""
        await self.save(slot_name, world)

    async def delete_slot(self, slot_name: str) -> None:
        """Delete a save slot."""
        await self._provider.delete(slot_name)

    async def list_slots(self) -> list[SaveSlotInfo]:
        """List all save slots with metadata."""
        names = await self._provider.list_slots()
        slots = []
        for name in names:
            data = await self._provider.load(name)
            info = SaveSlotInfo(
                name=name,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )
            if data:
                info.player_name = data.get("player", {}).get("name", "Unknown")
                info.player_level = data.get("player", {}).get("level", 0)
                info.turn_count = data.get("turn_count", 0)
                info.world_seed = data.get("world_seed", "")
            slots.append(info)
        return slots