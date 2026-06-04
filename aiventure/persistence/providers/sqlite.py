"""SQLite persistence provider — one row per save slot."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ..provider import SaveProvider


class SQLiteProvider(SaveProvider):
    """Stores save slots in a single SQLite database."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saves (
                    slot_name TEXT PRIMARY KEY,
                    world_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    modified_at TEXT NOT NULL,
                    player_name TEXT DEFAULT '',
                    player_level INTEGER DEFAULT 0,
                    turn_count INTEGER DEFAULT 0,
                    room_name TEXT DEFAULT '',
                    thumbnail TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                )
            """)
            conn.commit()

    async def save(self, slot_name: str, world_state: dict) -> None:
        now = datetime.now().isoformat()
        player = world_state.get("player", {})
        with sqlite3.connect(self._db_path) as conn:
            # Check if slot exists to preserve created_at
            row = conn.execute(
                "SELECT created_at FROM saves WHERE slot_name = ?",
                (slot_name,),
            ).fetchone()
            created = row[0] if row else now

            conn.execute("""
                INSERT INTO saves (
                    slot_name, world_json, created_at, modified_at,
                    player_name, player_level, turn_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slot_name) DO UPDATE SET
                    world_json = excluded.world_json,
                    modified_at = excluded.modified_at,
                    player_name = excluded.player_name,
                    player_level = excluded.player_level,
                    turn_count = excluded.turn_count
            """, (
                slot_name,
                json.dumps(world_state, ensure_ascii=False),
                created,
                now,
                player.get("name", ""),
                player.get("level", 0),
                world_state.get("turn_count", 0),
            ))
            conn.commit()

    async def load(self, slot_name: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT world_json FROM saves WHERE slot_name = ?",
                (slot_name,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    async def delete(self, slot_name: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM saves WHERE slot_name = ?", (slot_name,))
            conn.commit()

    async def list_slots(self) -> list[str]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT slot_name FROM saves ORDER BY modified_at DESC"
            ).fetchall()
        return [row[0] for row in rows]