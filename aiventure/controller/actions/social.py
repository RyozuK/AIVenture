"""Social actions — talking to NPCs, quest handling."""

from __future__ import annotations

import logging

from aiventure.model import Entity, Player
from aiventure.model.entity import EntityType
from aiventure.model.quest import Quest, QuestStatus

logger = logging.getLogger("aiventure.controller.actions.social")


async def do_talk(session: "GameSession", target_name: str) -> dict:
    """Talk to an NPC in the current room."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have no mouth to speak with!", "state": {}}

    current_room = session.world.get_room(player.position) if player.position else None
    if not current_room:
        return {"narrative": "There is no one here to talk to.", "state": {}}

    # Resolve NPC target
    npc = _resolve_npc(current_room, target_name, session.world)
    if npc is None:
        return {"narrative": f"There is no '{target_name}' here to talk to.", "state": {}}

    if not npc.is_alive:
        return {"narrative": f"{npc.name} is dead and cannot speak.", "state": {}}

    # Build dialogue context
    from aiventure.controller.context import ContextBuilder
    system, messages = ContextBuilder.build_npc_dialogue_context(
        session.world, player, npc,
    )

    from aiventure.llm.service import NPCDialogueData
    dialogue_data = await session.llm_service.generate_npc_dialogue(system, messages)

    narrative_parts: list[str] = [
        f"**{dialogue_data.npc_name}**{f' ({dialogue_data.mood})' if dialogue_data.mood else ''}:\n\n"
        f'"{dialogue_data.dialogue}"',
    ]

    # Handle quest offers
    quest_data = dialogue_data.quest_offered
    if quest_data and isinstance(quest_data, dict):
        quest = _create_quest_from_data(quest_data, npc.id)
        session.world.quests[quest.id] = quest
        quest.activate()
        player.active_quests.append(quest.id)
        narrative_parts.append(
            f"\n📜 **New Quest: {quest.title}**\n{quest.description}"
        )

    # Handle item trades
    for trade_item_data in dialogue_data.items_traded:
        from aiventure.model import Item
        from aiventure.model.item import ItemType
        try:
            item_type = ItemType(trade_item_data.get("item_type", "treasure"))
        except ValueError:
            item_type = ItemType.TREASURE
        item = Item(
            name=trade_item_data.get("name", "Unknown Item"),
            description=trade_item_data.get("description", ""),
            item_type=item_type,
            stat_value=trade_item_data.get("stat_value", 0),
            charges=trade_item_data.get("charges", -1),
            is_equippable=trade_item_data.get("is_equippable", False),
        )
        session.world.items[item.id] = item
        player.inventory.add(item)
        narrative_parts.append(f"\n{npc.name} gives you: {item.name}.")

    return {
        "narrative": "\n".join(narrative_parts),
        "state": {"talked_to": npc.name},
    }


async def do_quests(session: "GameSession", target: str = "") -> dict:
    """Display active quests or a specific quest."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have no quests.", "state": {}}

    world = session.world

    if target:
        # Show specific quest
        for qid in player.active_quests:
            quest = world.quests.get(qid)
            if quest and target.lower() in quest.title.lower():
                return {"narrative": _format_quest(quest), "state": {}}

        # Check completed quests too
        for qid in player.completed_quests:
            quest = world.quests.get(qid)
            if quest and target.lower() in quest.title.lower():
                return {"narrative": _format_quest(quest), "state": {}}

        return {"narrative": f"No quest matching '{target}' found.", "state": {}}

    # Show all active quests
    active = [world.quests[qid] for qid in player.active_quests if qid in world.quests]
    if not active:
        return {"narrative": "\n**Quests**\n\nYou have no active quests.", "state": {}}

    lines = ["\n**Active Quests**\n"]
    for quest in active:
        lines.append(_format_quest(quest))
        lines.append("")

    return {"narrative": "\n".join(lines), "state": {}}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_npc(room, target_name: str, world) -> Entity | None:
    for eid in room.connected_entities:
        entity = world.get_entity(eid)
        if (
            entity
            and isinstance(entity, Entity)
            and entity.is_alive
            and entity.entity_type == EntityType.NPC
            and target_name.lower() in entity.name.lower()
        ):
            return entity
    return None


def _create_quest_from_data(data: dict, giver_id: str | None) -> Quest:
    from aiventure.model.quest import Objective, Reward

    objectives = []
    for obj_data in data.get("objectives", []):
        objectives.append(Objective(
            type=obj_data.get("type", "explore"),
            target=obj_data.get("target", ""),
            required_count=obj_data.get("required_count", 1),
            current_count=0,
        ))

    rewards = []
    for rew_data in data.get("rewards", []):
        rewards.append(Reward(
            type=rew_data.get("type", "xp"),
            value=rew_data.get("value", {}),
        ))

    return Quest(
        title=data.get("title", "Mysterious Quest"),
        description=data.get("description", ""),
        giver_entity_id=giver_id,
        objectives=objectives if objectives else [Objective()],
        rewards=rewards,
    )


def _format_quest(quest: Quest) -> str:
    lines = [
        f"📜 **{quest.title}**",
        f"   Status: {quest.status.value}",
        f"   {quest.description}",
        "",
        "   Objectives:",
    ]
    for obj in quest.objectives:
        marker = "✓" if obj.is_complete else "○"
        lines.append(
            f"   {marker} [{obj.type}] {obj.target}: "
            f"{obj.current_count}/{obj.required_count}"
        )

    if quest.rewards:
        lines.append("")
        lines.append("   Rewards:")
        for rew in quest.rewards:
            if rew.type == "xp":
                lines.append(f"   - XP: {rew.value.get('amount', 0)}")
            elif rew.type == "gold":
                lines.append(f"   - Gold: {rew.value.get('amount', 0)}")
            else:
                lines.append(f"   - {rew.type}: {rew.value}")

    return "\n".join(lines)