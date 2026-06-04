"""Search action — reveals hidden items via LLM."""

from __future__ import annotations

import logging

from aiventure.model import Item, Player
from aiventure.llm.service import LLMService, ActionOutcomeData

logger = logging.getLogger("aiventure.controller.actions.examine")


async def do_search(session: "GameSession", target: str = "") -> dict:
    """Search the current room for hidden items."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have nothing to search with.", "state": {}}

    current_room = session.world.get_room(player.position) if player.position else None
    if not current_room:
        return {"narrative": "There is nothing to search here.", "state": {}}

    # Call LLM to determine search results
    from aiventure.controller.context import ContextBuilder
    system, messages = ContextBuilder.build_action_context(
        session.world, f"search the room{f' for {target}' if target else ''}"
    )
    outcome = await session.llm_service.describe_action_outcome(system, messages)

    narrative = outcome.narrative

    # Apply discovered items
    for item_data in outcome.discovered_items:
        item = Item(
            name=item_data.get("name", "Unknown Item"),
            description=item_data.get("description", ""),
            item_type=_parse_item_type(item_data.get("item_type", "treasure")),
            stat_value=item_data.get("stat_value", 0),
            charges=item_data.get("charges", -1),
            is_equippable=item_data.get("is_equippable", False),
        )
        session.world.items[item.id] = item
        current_room.connected_items.append(item.id)
        narrative += f"\n\nYou found: {item.name}."

    return {"narrative": narrative, "state": {}}


def _parse_item_type(raw: str):
    from aiventure.model.item import ItemType
    try:
        return ItemType(raw)
    except (ValueError, TypeError):
        return ItemType.TREASURE