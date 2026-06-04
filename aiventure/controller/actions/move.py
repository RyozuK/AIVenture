"""Movement action utilities."""

from __future__ import annotations

import logging

from aiventure.model import Player, Room
from aiventure.model.coords import Direction

logger = logging.getLogger("aiventure.controller.actions.move")


async def do_move(session: "GameSession", direction: Direction) -> dict:
    """Move the player one step in *direction*."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have no body to move with!", "state": {}}

    current_pos = player.position
    if current_pos is None:
        return {"narrative": "You are lost in the void.", "state": {}}

    current_room = session.world.get_room(current_pos)
    if current_room is None:
        return {"narrative": "You are in an unknown location.", "state": {}}

    target_pos = direction.apply_to(current_pos)
    if direction in current_room.exits:
        target_pos = current_room.exits[direction]

    target_room = session.world.get_room(target_pos)
    if target_room is None:
        target_room = await session._generate_room(current_room, direction, target_pos)
        if target_room is None:
            return {
                "narrative": f"There is a solid wall to the {direction.value}.",
                "state": {},
            }

    player.position = target_pos
    session.world.explored_positions.add(target_pos)
    target_room.visited_count += 1
    if direction not in target_room.exits:
        target_room.exits[direction.opposite()] = current_pos

    narrative = _describe_room_entry(session.world, target_room)
    logger.info("Player moved %s to %s (%s)", direction.value, target_pos, target_room.name)

    # Advance explore-based quests
    from .combat import _advance_explore_quests
    _advance_explore_quests(session, target_room.name)

    return {
        "narrative": narrative,
        "state": _room_state(target_room, player),
    }


def _describe_room_entry(world, room: Room) -> str:
    from aiventure.model.entity import Entity

    parts = [f"\n**{room.name}**\n", room.description]

    if room.features:
        parts.append(f"\nYou notice: {', '.join(room.features)}.")

    entity_names = []
    for eid in room.connected_entities:
        entity = world.get_entity(eid)
        if entity and isinstance(entity, Entity) and entity.is_alive:
            entity_names.append(entity.name)
    if entity_names:
        parts.append(f"\nYou see: {', '.join(entity_names)}.")

    if room.connected_items:
        parts.append(f"\nItems on the ground: {len(room.connected_items)} item(s).")

    exit_dirs = [d.value for d in room.exits.keys()]
    if exit_dirs:
        parts.append(f"\nExits: {', '.join(exit_dirs)}.")

    return "\n".join(parts)


def _room_state(room: Room, player: Player) -> dict:
    return {
        "room_id": room.id,
        "room_name": room.name,
        "position": {
            "x": player.position.x,
            "y": player.position.y,
            "z": player.position.z,
        } if player.position else None,
    }