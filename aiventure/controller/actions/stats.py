"""Statistics action — display game stats."""

from __future__ import annotations

from aiventure.model import Player


async def do_stats(session: "GameSession") -> dict:
    """Display game session statistics."""
    world = session.world
    player = world.player

    lines = ["\n**Game Statistics**\n"]

    if player and isinstance(player, Player):
        lines.append(f"  Player: {player.name}")
        lines.append(f"  Level: {player.level}")
        lines.append(f"  HP: {player.hp}/{player.max_hp}")
        lines.append(f"  ATK: {player.attack} | DEF: {player.defense}")
        lines.append(f"  Gold: {player.gold}")
        lines.append(f"  XP: {player.xp}/{player.level * 50}")
        lines.append(f"  Deaths: {player.death_count}")

    lines.append(f"  Turns: {world.turn_count}")
    lines.append(f"  Rooms explored: {len(world.explored_positions)}")
    lines.append(f"  Rooms generated: {len(world.generated_positions)}")
    lines.append(f"  Entities: {len(world.entities)}")
    lines.append(f"  Items: {len(world.items)}")

    if player and isinstance(player, Player):
        lines.append(f"  Active quests: {len(player.active_quests)}")
        lines.append(f"  Completed quests: {len(player.completed_quests)}")

    # Inventory stats
    if player and isinstance(player, Player):
        inv = player.inventory
        lines.append(f"  Items carried: {len(inv.owned_items)}")
        lines.append(f"  Weight: {inv.current_weight}/{inv.max_weight}")
        lines.append(f"  Slots equipped: {len(inv.equipped)}")

    return {"narrative": "\n".join(lines), "state": {}}