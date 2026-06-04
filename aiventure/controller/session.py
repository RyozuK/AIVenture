"""GameSession — the main controller orchestrating game play."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from aiventure.model import Player, Position, Room, World
from aiventure.model.coords import Direction
from aiventure.model.entity import EntityType
from aiventure.llm.service import LLMService
from aiventure.utils.config import GameConfig

from .context import ContextBuilder
from .parser import ParsedCommand, parse_input

logger = logging.getLogger("aiventure.controller.session")


@dataclass
class GameSession:
    """Top-level controller. One session per active game."""

    world: World
    llm_service: LLMService
    config: GameConfig
    _history: list[str] = field(default_factory=list, repr=False)
    _save_manager: Any = None
    _last_target: str = ""

    # -- Public API -- #

    async def process_command(self, input_text: str) -> dict:
        """Process a raw text command and return a result dict."""
        parsed = parse_input(input_text, last_target=self._last_target)
        logger.debug("Parsed: %s", parsed)

        # Track last target for pronoun resolution
        if parsed.target and parsed.pronoun != "it":
            self._last_target = parsed.target.split()[-1] if parsed.target else ""

        result = await self._dispatch(parsed)
        self.world.turn_count += 1

        # Record in history for context
        self._history.append(
            f"Turn {self.world.turn_count}: {input_text} → {result.get('narrative', '')}"
        )
        if len(self._history) > self.config.max_context_turns:
            self._history = self._history[-self.config.max_context_turns:]

        result["turn"] = self.world.turn_count
        result.setdefault("game_over", False)

        # Check for death
        if result.get("death") and self.world.player:
            result["game_over"] = True

        # Auto-save: on interval, on quest-complete, and on new room generation
        await self._maybe_auto_save(result)

        return result

    async def describe_current_room(self) -> str:
        """Return a full description of the current room (entry text)."""
        from .actions.inventory import _describe_room

        player = self.world.player
        if not player or not isinstance(player, Player) or not player.position:
            return "You are lost in the void."
        room = self.world.get_room(player.position)
        if room:
            return _describe_room(self.world, room)
        return "You are in an unknown location."

    # -- Internal dispatch -- #

    async def _dispatch(self, parsed: ParsedCommand) -> dict:
        if parsed.verb == "move" and parsed.direction:
            from .actions.move import do_move
            return await do_move(self, parsed.direction)

        elif parsed.verb == "look":
            from .actions.inventory import do_look
            return await do_look(self, parsed.target)

        elif parsed.verb == "take":
            from .actions.inventory import do_take
            return await do_take(self, parsed.target)

        elif parsed.verb == "drop":
            from .actions.inventory import do_drop
            return await do_drop(self, parsed.target)

        elif parsed.verb == "inventory":
            from .actions.inventory import do_inventory
            return await do_inventory(self)

        elif parsed.verb == "attack":
            from .actions.combat import do_attack
            return await do_attack(self, parsed.target)

        elif parsed.verb == "equip":
            from .actions.inventory import do_equip
            return await do_equip(self, parsed.target)

        elif parsed.verb == "unequip":
            from .actions.inventory import do_unequip
            return await do_unequip(self, parsed.target)

        elif parsed.verb == "use":
            from .actions.inventory import do_use
            return await do_use(self, parsed.target)

        elif parsed.verb == "search":
            from .actions.examine import do_search
            return await do_search(self, parsed.target)

        elif parsed.verb == "talk":
            from .actions.social import do_talk
            return await do_talk(self, parsed.target)

        elif parsed.verb == "quests":
            from .actions.social import do_quests
            return await do_quests(self, parsed.target)

        elif parsed.verb == "stats":
            from .actions.stats import do_stats
            return await do_stats(self)

        elif parsed.verb == "save":
            if self._save_manager:
                slot = parsed.target or "default"
                await self._save_manager.save(slot, self.world)
                return {"narrative": f"Game saved to slot '{slot}'.", "state": {}}
            return {"narrative": "No save manager configured.", "state": {}}

        elif parsed.verb == "export":
            return await self.do_export(parsed.target)

        elif parsed.verb == "quit":
            return {
                "narrative": "Thanks for playing! Goodbye.",
                "state": {},
                "game_over": True,
            }

        else:
            return await self._handle_freeform(parsed.raw)

    async def _handle_freeform(self, raw: str) -> dict:
        """Send an unrecognized command to the LLM with a safety gate."""
        system, messages = ContextBuilder.build_action_context(self.world, raw)
        outcome = await self.llm_service.describe_action_outcome(system, messages)

        # Safety gate: apply discovered items/entities from the LLM response
        narrative = outcome.narrative
        current_room = (
            self.world.get_room(self.world.player.position)
            if self.world.player and isinstance(self.world.player, Player) and self.world.player.position
            else None
        )

        # Apply discovered items
        for item_data in outcome.discovered_items:
            from aiventure.model import Item
            from aiventure.model.item import ItemType
            try:
                item_type = ItemType(item_data.get("item_type", "treasure"))
            except ValueError:
                item_type = ItemType.TREASURE
            item = Item(
                name=item_data.get("name", "Unknown Item"),
                description=item_data.get("description", ""),
                item_type=item_type,
                stat_value=item_data.get("stat_value", 0),
                charges=item_data.get("charges", -1),
                is_equippable=item_data.get("is_equippable", False),
            )
            self.world.items[item.id] = item
            if current_room:
                current_room.connected_items.append(item.id)

        # Apply discovered entities
        for entity_data in outcome.discovered_entities:
            from aiventure.model.entity import Entity
            try:
                etype = EntityType(entity_data.get("entity_type", "monster"))
            except ValueError:
                etype = EntityType.MONSTER
            entity = Entity(
                name=entity_data.get("name", "Unknown creature"),
                description=entity_data.get("description", ""),
                entity_type=etype,
                room_id=current_room.id if current_room else None,
                hp=entity_data.get("hp", 10),
                max_hp=entity_data.get("max_hp", 10),
                attack=entity_data.get("attack", 1),
                defense=entity_data.get("defense", 1),
                is_hostile=entity_data.get("is_hostile", etype == EntityType.MONSTER),
            )
            self.world.entities[entity.id] = entity
            if current_room:
                current_room.connected_entities.append(entity.id)

        return {"narrative": narrative, "state": {}}

    # -- Room generation -- #

    async def _generate_room(
        self,
        source_room: Room,
        direction: Direction,
        target_position: Position,
    ) -> Room | None:
        """Ask the LLM to generate a new room and add it to the world."""
        from aiventure.model.item import ItemType

        system, messages = ContextBuilder.build_room_generation_context(
            self.world, source_room, direction, target_position,
        )
        room_data = await self.llm_service.generate_room(system, messages)

        if not room_data.name:
            return None

        room = Room(
            position=target_position,
            name=room_data.name,
            description=room_data.description,
            features=room_data.features,
        )

        # Build exits
        for exit_dir_name in room_data.exits:
            d = Direction.from_str(exit_dir_name)
            if d:
                room.exits[d] = d.apply_to(target_position)

        # Add items
        for item_data in room_data.items:
            from aiventure.model import Item
            try:
                item_type = ItemType(item_data.get("item_type", "treasure"))
            except ValueError:
                item_type = ItemType.TREASURE
            equip_slot_raw = item_data.get("equip_slot", "none")
            from aiventure.model.item import EquipSlot
            try:
                equip_slot = EquipSlot(equip_slot_raw) if equip_slot_raw and equip_slot_raw != "none" else EquipSlot.NONE
            except ValueError:
                equip_slot = EquipSlot.NONE
            item = Item(
                name=item_data.get("name", "Unknown Item"),
                description=item_data.get("description", ""),
                item_type=item_type,
                stat_value=item_data.get("stat_value", 0),
                charges=item_data.get("charges", -1),
                is_equippable=item_data.get("is_equippable", False),
                equip_slot=equip_slot,
            )
            self.world.items[item.id] = item
            room.connected_items.append(item.id)

        # Add entities
        for entity_data in room_data.entities:
            from aiventure.model.entity import Entity
            try:
                etype = EntityType(entity_data.get("entity_type", "monster"))
            except ValueError:
                etype = EntityType.MONSTER
            entity = Entity(
                name=entity_data.get("name", "Unknown creature"),
                description=entity_data.get("description", ""),
                entity_type=etype,
                room_id=room.id,
                hp=entity_data.get("hp", 10),
                max_hp=entity_data.get("max_hp", 10),
                attack=entity_data.get("attack", 1),
                defense=entity_data.get("defense", 1),
                is_hostile=entity_data.get("is_hostile", etype == EntityType.MONSTER),
                personality=entity_data.get("personality", ""),
                ai_behavior=entity_data.get("ai_behavior", "wander"),
            )
            self.world.entities[entity.id] = entity
            room.connected_entities.append(entity.id)

        self.world.add_room(room)
        logger.info("Generated room '%s' at %s", room.name, target_position)

        # Auto-save on new room generation
        await self._background_save("default")

        return room

    # -- Auto-save helpers -- #

    async def _maybe_auto_save(self, result: dict) -> None:
        """Trigger auto-save on: interval, quest-complete, room-gen."""
        if not self._save_manager:
            return
        should_save = False
        # Interval-based
        if self.world.turn_count % self.config.auto_save_interval == 0:
            should_save = True
        # Quest completed
        if result.get("quest_completed"):
            should_save = True
        # Death
        if result.get("death"):
            should_save = True
        if should_save:
            await self._background_save("default")

    async def _background_save(self, slot_name: str) -> None:
        """Non-blocking save — fire and forget."""
        if not self._save_manager:
            return
        try:
            await asyncio.wait_for(
                self._save_manager.auto_save(slot_name, self.world),
                timeout=2.0,
            )
        except (asyncio.TimeoutError, Exception):
            logger.warning("Background save timed out or failed")

    # -- World export/import (Phase 4.3) -- #

    def export_world(self) -> str:
        """Export the current world as a JSON string."""
        return json.dumps(self.world.to_dict(), indent=2, ensure_ascii=False)

    def export_world_file(self, path: str) -> None:
        """Export the current world to a JSON file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.export_world())
        logger.info("Exported world to %s", path)

    @classmethod
    def import_world(cls, path: str):
        """Import a world from a JSON file (returns World object)."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return World.from_dict(data)

    async def do_export(self, path: str = "") -> dict:
        """Handle the 'export' command."""
        export_path = path or "exports/world_export.json"
        self.export_world_file(export_path)
        return {"narrative": f"World exported to {export_path}.", "state": {}}

    async def do_import(self, path: str) -> dict:
        """Handle the 'import' command."""
        new_world = self.import_world(path)
        self.world = new_world
        return {"narrative": "World imported successfully.", "state": {}}