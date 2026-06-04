"""JSON file save provider — one file per slot."""

from __future__ import annotations

import json
import os
from datetime import datetime

import aiofiles

from ..provider import SaveProvider


class JsonFileProvider(SaveProvider):
    """Stores each save slot as a JSON file in a directory."""

    def __init__(self, directory: str) -> None:
        self._dir = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, slot_name: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in slot_name)
        return os.path.join(self._dir, f"{safe}.json")

    async def save(self, slot_name: str, world_state: dict) -> None:
        payload = {
            "slot_name": slot_name,
            "saved_at": datetime.now().isoformat(),
            "world": world_state,
        }
        path = self._path(slot_name)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(payload, indent=2, ensure_ascii=False))

    async def load(self, slot_name: str) -> dict | None:
        path = self._path(slot_name)
        if not os.path.isfile(path):
            return None
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
        return data.get("world")

    async def delete(self, slot_name: str) -> None:
        path = self._path(slot_name)
        if os.path.isfile(path):
            os.remove(path)

    async def list_slots(self) -> list[str]:
        slots = []
        for fname in os.listdir(self._dir):
            if fname.endswith(".json"):
                # Try to extract slot name from file
                path = os.path.join(self._dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    slots.append(data.get("slot_name", fname[:-5]))
                except (json.JSONDecodeError, OSError):
                    slots.append(fname[:-5])
        return slots