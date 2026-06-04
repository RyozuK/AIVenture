"""Inventory and examination action utilities."""

from __future__ import annotations

import logging

from aiventure.model import Entity, Item, Player

logger = logging.getLogger("aiventure.controller.actions.inventory")


async def do_look(session: "GameSession", target: str = "") -> dict:
    """Describe the current room or a specific target."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You can't see anything.", "state": {}}

    current_room = session.world.get_room(player.position) if player.position else None
    world = session.world

    if target:
        # Entities in room
        for eid in (current_room.connected_entities if current_room else []):
            entity = world.get_entity(eid)
            if entity and isinstance(entity, Entity) and target.lower() in entity.name.lower():
                narrative = f"**{entity.name}**\n\n{entity.description}"
                if not entity.is_alive:
                    narrative += "\n\nIt is dead."
                return {"narrative": narrative, "state": {}}

        # Items on ground
        for iid in (current_room.connected_items if current_room else []):
            item = world.get_item(iid)
            if item and isinstance(item, Item) and target.lower() in item.name.lower():
                return {"narrative": f"**{item.name}**\n\n{item.description}", "state": {}}

        # Inventory items
        for item in player.inventory.owned_items.values():
            if item and target.lower() in item.name.lower():
                equipped = " (equipped)" if item.id in player.inventory.equipped.values() else ""
                return {"narrative": f"**{item.name}**{equipped}\n\n{item.description}", "state": {}}

        return {"narrative": f"You don't see anything matching '{target}' here.", "state": {}}

    # No target — describe room
    if current_room:
        narrative = _describe_room(world, current_room)
    else:
        narrative = "You are standing in darkness."

    return {"narrative": narrative, "state": {}}


async def do_take(session: "GameSession", target: str) -> dict:
    """Pick up an item from the current room."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have no hands!", "state": {}}

    current_room = session.world.get_room(player.position) if player.position else None
    if not current_room:
        return {"narrative": "There is nothing here to take.", "state": {}}

    item = _find_item_in_room(session.world, current_room, target)
    if item is None:
        return {"narrative": f"There is no '{target}' here to take.", "state": {}}

    ok = player.inventory.add(item)
    if not ok:
        return {"narrative": "Your inventory is full.", "state": {}}

    current_room.connected_items.remove(item.id)
    logger.info("Player took %s", item.name)

    # Advance collect-based quests
    from .combat import _advance_collect_quests
    _advance_collect_quests(session, item.name)

    return {
        "narrative": f"You pick up {item.name}.",
        "state": {"item_taken": item.name},
    }


async def do_drop(session: "GameSession", target: str) -> dict:
    """Drop an item from the inventory onto the ground."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have nothing to drop.", "state": {}}

    items = player.inventory.find(target)
    if not items:
        return {"narrative": f"You don't have a '{target}'.", "state": {}}

    item = items[0]
    player.inventory.remove(item.id)

    current_room = session.world.get_room(player.position) if player.position else None
    if current_room:
        current_room.connected_items.append(item.id)

    return {
        "narrative": f"You drop {item.name}.",
        "state": {"item_dropped": item.name},
    }


async def do_equip(session: "GameSession", target: str) -> dict:
    """Equip an item from the inventory."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have nothing to equip.", "state": {}}

    items = player.inventory.find(target)
    if not items:
        return {"narrative": f"You don't have a '{target}'.", "state": {}}

    item = items[0]
    if not item.is_equippable:
        return {"narrative": f"You can't equip {item.name}.", "state": {}}

    from aiventure.model.item import EquipSlot

    # Check slot validity
    from aiventure.model.item import VALID_SLOT_TYPES
    if item.equip_slot not in VALID_SLOT_TYPES:
        return {"narrative": f"You can't equip {item.name} — no valid slot.", "state": {}}
    valid_types = VALID_SLOT_TYPES[item.equip_slot]
    if item.item_type not in valid_types:
        return {"narrative": f"You can't equip {item.name} in the {item.equip_slot.value} slot.", "state": {}}

    ok = player.inventory.equip(item.id)
    if not ok:
        return {"narrative": f"You already have {item.name} equipped.", "state": {}}

    return {
        "narrative": f"You equip {item.name} on your {item.equip_slot.value}.",
        "state": {"equipped": item.name, "slot": item.equip_slot.value},
    }


async def do_unequip(session: "GameSession", target: str) -> dict:
    """Unequip an item from a slot."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have nothing to unequip.", "state": {}}

    from aiventure.model.item import EquipSlot

    # Resolve target to a slot
    slot = None
    for s in EquipSlot:
        if s.value.lower() in target.lower():
            slot = s
            break

    if slot is None:
        return {"narrative": f"I don't understand which slot to unequip from.", "state": {}}

    if slot not in player.inventory.equipped:
        return {"narrative": f"You have nothing equipped on your {slot.value}.", "state": {}}

    item = player.inventory.get_equipped(slot)
    player.inventory.unequip(slot)

    return {
        "narrative": f"You unequip {item.name} from your {slot.value}." if item else f"You remove the item from your {slot.value}.",
        "state": {"unequipped_slot": slot.value},
    }


async def do_use(session: "GameSession", target: str) -> dict:
    """Use a consumable item (potion, etc.)."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have nothing to use.", "state": {}}

    items = player.inventory.find(target)
    if not items:
        return {"narrative": f"You don't have a '{target}'.", "state": {}}

    item = items[0]

    # Potions and consumables can be used
    from aiventure.model.item import ItemType
    if item.item_type not in (ItemType.POTION, ItemType.CONSUMABLE):
        # Weapons and armor can't be "used" directly
        return {"narrative": f"You can't use {item.name} that way. Try equipping it instead.", "state": {}}

    # Determine effect
    from aiventure.controller.context import ContextBuilder
    system, messages = ContextBuilder.build_item_use_context(
        session.world, player, item,
    )
    from aiventure.llm.service import ItemUseOutcomeData
    outcome = await session.llm_service.describe_item_use(system, messages)

    narrative = outcome.narrative

    # Apply deterministic heal if it's a potion
    if item.item_type == ItemType.POTION and item.stat_value > 0:
        healed = player.heal(item.stat_value)
        narrative += f"\nYou recover {healed} HP (HP: {player.hp}/{player.max_hp})."

    # Consume charges
    if item.charges == 0:
        player.inventory.remove(item.id)
        narrative += f"\n{item.name} is now empty."
    elif item.charges > 0:
        item.charges -= outcome.charges_consumed
        if item.charges <= 0:
            player.inventory.remove(item.id)
            narrative += f"\n{item.name} is now empty."

    return {"narrative": narrative, "state": {"item_used": item.name}}


async def do_inventory(session: "GameSession", target: str = "") -> dict:
    """Show the player's inventory."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have no inventory.", "state": {}}

    inv = player.inventory
    lines = ["\n**Inventory**"]

    # Equipped
    for slot, item_id in inv.equipped.items():
        item = inv.owned_items.get(item_id)
        if item:
            lines.append(f"  [{slot.value.upper()}] {item.name}")

    # Carried
    equipped_ids = set(inv.equipped.values())
    carried = [
        item for item in inv.owned_items.values()
        if item and item.id not in equipped_ids
    ]
    if carried:
        lines.append("\nCarried:")
        for item in carried:
            lines.append(f"  - {item.name}")
    elif not equipped_ids:
        lines.append("\n  (empty)")

    lines.append(f"\nWeight: {inv.current_weight}/{inv.max_weight}")
    lines.append(f"Gold: {player.gold}")

    return {"narrative": "\n".join(lines), "state": {}}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_item_in_room(world, room, target: str) -> Item | None:
    for iid in room.connected_items:
        item = world.get_item(iid)
        if item and target.lower() in item.name.lower():
            return item
    return None


def _describe_room(world, room) -> str:
    parts = [f"\n**{room.name}**\n", room.description]

    if room.features:
        parts.append(f"\nNotable features: {', '.join(room.features)}.")

    entity_names = []
    for eid in room.connected_entities:
        entity = world.get_entity(eid)
        if entity and isinstance(entity, Entity) and entity.is_alive:
            host = " (hostile)" if entity.is_hostile else ""
            entity_names.append(f"{entity.name}{host}")
    if entity_names:
        parts.append(f"\nYou can see: {', '.join(entity_names)}.")

    item_names = []
    for iid in room.connected_items:
        item = world.get_item(iid)
        if item:
            item_names.append(item.name)
    if item_names:
        parts.append(f"\nYou see: {', '.join(item_names)}.")

    exit_dirs = [d.value for d in room.exits.keys()]
    if exit_dirs:
        parts.append(f"\nExits: {', '.join(exit_dirs)}.")

    return "\n".join(parts)