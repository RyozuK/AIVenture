"""Combat action — attack entity, resolve via LLM, apply damage."""

from __future__ import annotations

import logging

from aiventure.model import Entity, Item, Player
from aiventure.model.entity import EntityType
from aiventure.model.item import ItemType

logger = logging.getLogger("aiventure.controller.actions.combat")


async def do_attack(session: "GameSession", target_name: str) -> dict:
    """Attack a hostile entity in the current room.

    Uses the LLM to resolve the combat exchange and apply damage to both sides.
    """
    player = session.world.player
    if not player or not isinstance(player, Player):
        return {"narrative": "You have no body to fight with!", "state": {}}

    if not player.is_alive:
        return {"narrative": "You are dead. You cannot attack.", "state": {}}

    current_room = session.world.get_room(player.position) if player.position else None
    if not current_room:
        return {"narrative": "There is nothing here to fight.", "state": {}}

    # Resolve target entity
    target = _resolve_entity(current_room, target_name, session.world)
    if target is None:
        return {"narrative": f"There is no '{target_name}' here to attack.", "state": {}}

    if not target.is_alive:
        return {"narrative": f"{target.name} is already dead.", "state": {}}

    if target.entity_type == EntityType.NPC and not target.is_hostile:
        return {"narrative": f"You can't attack {target.name} — they are friendly.", "state": {}}

    # Build combat context
    player_stats = _effective_stats(player)
    enemy_stats = _effective_stats(target)

    from aiventure.controller.context import ContextBuilder
    system, messages = ContextBuilder.build_combat_context(
        session.world, player, player_stats, target, enemy_stats,
    )

    from aiventure.llm.service import CombatOutcomeData
    outcome = await session.llm_service.describe_combat_outcome(system, messages)

    # Apply damage
    player_damage_taken = max(0, outcome.player_damage_dealt or 0)
    enemy_damage_taken = max(0, outcome.enemy_damage_dealt or 0)

    player_narrative_parts: list[str] = [outcome.narrative]
    quests_completed: list[str] = []

    if enemy_damage_taken > 0:
        actual_enemy_dmg = target.take_damage(enemy_damage_taken)
        player_narrative_parts.append(
            f"You dealt {actual_enemy_dmg} damage to {target.name} "
            f"(HP: {target.hp}/{target.max_hp})."
        )
    else:
        player_narrative_parts.append(f"Your attack missed {target.name}!")

    if player_damage_taken > 0:
        actual_player_dmg = player.take_damage(player_damage_taken)
        player_narrative_parts.append(
            f"{target.name} dealt {actual_player_dmg} damage to you "
            f"(HP: {player.hp}/{player.max_hp})."
        )

    # Check enemy death
    if not target.is_alive:
        player_narrative_parts.append(f"\n**{target.name} has been slain!**")
        # Grant XP
        xp_reward = max(5, target.attack * 3 + target.defense * 2)
        leveled = player.gain_xp(xp_reward)
        player_narrative_parts.append(f"You gain {xp_reward} XP.")
        if leveled:
            player_narrative_parts.append(
                f"\n**LEVEL UP!** You are now level {player.level}!"
            )

        # Loot drops
        for item_data in outcome.loot_dropped:
            try:
                item_type = ItemType(item_data.get("item_type", "treasure"))
            except ValueError:
                item_type = ItemType.TREASURE
            equip_slot_raw = item_data.get("equip_slot", "none")
            try:
                from aiventure.model.item import EquipSlot
                equip_slot = EquipSlot(equip_slot_raw) if equip_slot_raw != "none" else EquipSlot.NONE
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
            session.world.items[item.id] = item
            current_room.connected_items.append(item.id)
            player_narrative_parts.append(f"\n{target.name} dropped: {item.name}.")

        # Remove dead entity from room
        current_room.connected_entities = [
            eid for eid in current_room.connected_entities if eid != target.id
        ]

        # Advance any kill-based quests
        quests_completed = _advance_kill_quests(session, target.name)

    # Check player death
    if not player.is_alive:
        from .death import handle_death
        return await handle_death(session, player)

    return {
        "narrative": "\n".join(player_narrative_parts),
        "state": {
            "player_hp": player.hp,
            "player_max_hp": player.max_hp,
        },
        "quest_completed": bool(quests_completed),
    }


def _resolve_entity(room, target_name: str, world) -> Entity | None:
    """Find a living entity in the room matching the name pattern."""
    for eid in room.connected_entities:
        entity = world.get_entity(eid)
        if (
            entity
            and isinstance(entity, Entity)
            and entity.is_alive
            and target_name.lower() in entity.name.lower()
        ):
            return entity
    return None


def _effective_stats(entity: Player | Entity) -> dict:
    """Compute effective stats including equipment bonuses."""
    stats = {
        "name": entity.name,
        "hp": entity.hp,
        "max_hp": entity.max_hp,
        "attack": entity.attack,
        "defense": entity.defense,
    }

    if isinstance(entity, Player):
        from aiventure.model.item import EquipSlot

        weapon = entity.inventory.get_equipped(EquipSlot.HAND)
        if weapon:
            stats["attack"] += weapon.stat_value
            stats["weapon"] = weapon.name

        armor = entity.inventory.get_equipped(EquipSlot.CHEST)
        if armor:
            stats["defense"] += armor.stat_value
            stats["armor"] = armor.name

        # Other armor slots contribute defense too
        for slot in (EquipSlot.HEAD, EquipSlot.LEGS, EquipSlot.FEET):
            piece = entity.inventory.get_equipped(slot)
            if piece:
                stats["defense"] += piece.stat_value

    stats["attack"] = max(1, stats["attack"])
    stats["defense"] = max(0, stats["defense"])
    return stats


def _advance_kill_quests(session, target_name: str) -> list[str]:
    """Advance any active quests that have a 'kill' objective matching *target_name*.
    Returns list of completed quest titles."""
    return _advance_quests(session, "kill", target_name)


def _advance_collect_quests(session, item_name: str) -> list[str]:
    """Advance any active quests that have a 'collect' objective matching *item_name*.
    Returns list of completed quest titles."""
    return _advance_quests(session, "collect", item_name)


def _advance_explore_quests(session, room_name: str) -> list[str]:
    """Advance any active quests that have an 'explore' objective matching *room_name*.
    Returns list of completed quest titles."""
    return _advance_quests(session, "explore", room_name)


def _advance_quests(session, obj_type: str, target: str) -> list[str]:
    """Core helper: advance all matching objectives and complete quests.
    Returns list of completed quest titles."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return []

    completed: list[str] = []
    for qid in list(player.active_quests):
        quest = session.world.quests.get(qid)
        if quest and quest.advance(obj_type, target):
            logger.info("Quest '%s' completed by %s!", quest.title, obj_type)
            _grant_quest_rewards(session, quest)
            player.active_quests.remove(qid)
            player.completed_quests.append(qid)
            completed.append(quest.title)
    return completed

def _grant_quest_rewards(session, quest) -> None:
    """Apply all rewards from a completed quest to the player."""
    player = session.world.player
    if not player or not isinstance(player, Player):
        return

    for reward in quest.rewards:
        if reward.type == "xp":
            amount = reward.value.get("amount", 0)
            leveled = player.gain_xp(amount)
            logger.info("Quest reward: %d XP (leveled=%s)", amount, leveled)
        elif reward.type == "gold":
            amount = reward.value.get("amount", 0)
            player.gold += amount
            logger.info("Quest reward: %d gold", amount)
        elif reward.type == "item":
            try:
                item_type = ItemType(reward.value.get("item_type", "treasure"))
            except ValueError:
                item_type = ItemType.TREASURE
            item = Item(
                name=reward.value.get("name", "Mystery Item"),
                description=reward.value.get("description", ""),
                item_type=item_type,
                stat_value=reward.value.get("stat_value", 0),
                charges=reward.value.get("charges", -1),
                is_equippable=reward.value.get("is_equippable", False),
            )
            session.world.items[item.id] = item
            player.inventory.add(item)
            logger.info("Quest reward: item '%s'", item.name)