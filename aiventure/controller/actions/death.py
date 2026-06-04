"""Death and respawn handling."""

from __future__ import annotations

import logging

from aiventure.model import Player, Position, Room, World

logger = logging.getLogger("aiventure.controller.actions.death")


async def handle_death(session: "GameSession", player: Player) -> dict:
    """Handle player death: apply penalties, respawn, and generate narrative."""
    world = session.world
    player.death_count += 1

    # Apply death penalties based on config
    penalty_gold = max(0, int(player.gold * session.config.death_gold_loss_pct))
    penalty_items = session.config.death_item_loss

    narrative_parts = [
        "\n**You have been slain!**",
        f"Death #{player.death_count}.",
    ]

    # Gold penalty
    if penalty_gold > 0:
        player.gold -= penalty_gold
        narrative_parts.append(f"You lose {penalty_gold} gold (remaining: {player.gold}).")

    # Item loss (optional)
    if penalty_items:
        lost_items = _apply_item_loss(player, session)
        if lost_items:
            narrative_parts.append(f"You lose: {', '.join(lost_items)}.")

    # Respawn: find the last safe room (starting room or last auto-save position)
    respawn_pos = _find_respawn_position(world)
    player.position = respawn_pos
    player.hp = player.max_hp  # Full heal on respawn
    player.is_alive = True
    player.room_id = world.get_room(respawn_pos).id if world.get_room(respawn_pos) else None

    narrative_parts.append(f"\nYou awaken at {world.get_room(respawn_pos).name if world.get_room(respawn_pos) else 'an unknown location'}.")

    logger.info("Player died (death #%d), respawned at %s", player.death_count, respawn_pos)

    return {
        "narrative": "\n".join(narrative_parts),
        "state": {
            "player_hp": player.hp,
            "player_max_hp": player.max_hp,
            "respawn_position": {"x": respawn_pos.x, "y": respawn_pos.y, "z": respawn_pos.z},
        },
        "game_over": False,  # Player continues after death
    }


def _apply_item_loss(player: Player, session: "GameSession") -> list[str]:
    """Remove a percentage of carried items as death penalty. Returns names of lost items."""
    import random

    loss_pct = session.config.death_item_loss_pct
    items_to_lose = max(1, int(len(player.inventory.owned_items) * loss_pct))
    owned = [
        (iid, item) for iid, item in player.inventory.owned_items.items() if item
    ]

    lost_names = []
    removed_ids = set()

    for _ in range(min(items_to_lose, len(owned))):
        if not owned:
            break
        item_id, item = random.choice(owned)
        owned.remove((item_id, item))
        player.inventory.remove(item_id)
        lost_names.append(item.name)
        removed_ids.add(item_id)

    # Also remove from equipped
    for slot, item_id in list(player.inventory.equipped.items()):
        if item_id in removed_ids:
            del player.inventory.equipped[slot]

    return lost_names


def _find_respawn_position(world: World) -> Position:
    """Find the position to respawn the player at.

    Priority:
    1. Last auto-save position (if tracked in world metadata)
    2. Starting room (position 0,0,0)
    3. Any explored room closest to the player's original position
    """
    # Try starting room first
    start_pos = Position(0, 0, 0)
    if world.get_room(start_pos):
        return start_pos

    # Try any explored position
    if world.explored_positions:
        # Find the one closest to origin
        closest = min(
            world.explored_positions,
            key=lambda p: p.distance_to(start_pos),
        )
        return closest

    # Last resort: original position
    return start_pos