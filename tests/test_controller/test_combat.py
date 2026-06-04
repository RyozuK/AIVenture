"""Tests for combat actions with a mock LLM service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from aiventure.model import Player, Position, Room, World
from aiventure.model.entity import Entity, EntityType
from aiventure.controller.session import GameSession
from aiventure.controller.actions.combat import do_attack, _effective_stats
from aiventure.llm.service import CombatOutcomeData


@pytest.fixture
def mock_llm_service():
    svc = AsyncMock()
    svc.describe_combat_outcome = AsyncMock(return_value=CombatOutcomeData(
        narrative="You swing your sword at the goblin!",
        player_damage_dealt=0,
        enemy_damage_dealt=5,
        player_alive=True,
        enemy_alive=True,
        loot_dropped=[],
    ))
    return svc


@pytest.fixture
def combat_session(mock_llm_service):
    world = World(world_seed="Dark dungeon")
    room = Room.create_empty(Position(0, 0, 0), "Combat Arena", "A dusty arena.")
    world.add_room(room)
    world.explored_positions.add(Position(0, 0, 0))

    goblin = Entity(
        name="Goblin",
        description="A small green creature.",
        entity_type=EntityType.MONSTER,
        room_id=room.id,
        hp=15,
        max_hp=15,
        attack=3,
        defense=1,
        is_hostile=True,
        is_alive=True,
    )
    world.entities[goblin.id] = goblin
    room.connected_entities.append(goblin.id)

    player = Player.create_default("Hero", Position(0, 0, 0))
    player.room_id = room.id
    world.player = player

    from aiventure.utils.config import GameConfig
    return GameSession(
        world=world,
        llm_service=mock_llm_service,
        config=GameConfig(),
    )


@pytest.mark.asyncio
async def test_attack_hits_enemy(combat_session):
    result = await do_attack(combat_session, "goblin")
    assert "damage" in result["narrative"].lower() or "swing" in result["narrative"].lower()
    assert "goblin" in result["narrative"].lower() or "5" in result["narrative"]


@pytest.mark.asyncio
async def test_attack_no_target(combat_session):
    result = await do_attack(combat_session, "dragon")
    assert "no" in result["narrative"].lower()


@pytest.mark.asyncio
async def test_attack_friendly_npc(combat_session):
    npc = Entity(
        name="Kind Villager",
        entity_type=EntityType.NPC,
        room_id=combat_session.world.player.position,
        is_hostile=False,
        is_alive=True,
    )
    combat_session.world.entities[npc.id] = npc
    room = combat_session.world.get_room(combat_session.world.player.position)
    room.connected_entities.append(npc.id)

    result = await do_attack(combat_session, "villager")
    assert "friendly" in result["narrative"].lower() or "can't" in result["narrative"].lower()


@pytest.mark.asyncio
async def test_attack_dead_enemy(combat_session):
    """A dead entity can't be resolved, so attack returns a not-found message."""
    goblin_id = combat_session.world.get_room(Position(0,0,0)).connected_entities[0]
    enemy = combat_session.world.entities[goblin_id]
    enemy.hp = 0
    enemy.is_alive = False

    result = await do_attack(combat_session, "goblin")
    # Dead entities are filtered out of resolution, so the parser says not found
    assert "no" in result["narrative"].lower() or "not" in result["narrative"].lower()


def test_effective_stats_no_equipment():
    player = Player.create_default("Hero", Position(0, 0, 0))
    stats = _effective_stats(player)
    assert stats["attack"] == 3
    assert stats["defense"] == 2


def test_effective_stats_with_equipment():
    from aiventure.model import Item
    from aiventure.model.item import EquipSlot, ItemType

    player = Player.create_default("Hero", Position(0, 0, 0))

    weapon = Item(
        name="Iron Sword",
        item_type=ItemType.WEAPON,
        stat_value=5,
        is_equippable=True,
        equip_slot=EquipSlot.HAND,
    )
    player.inventory.add(weapon)
    player.inventory.equip(weapon.id)

    armor = Item(
        name="Leather Armor",
        item_type=ItemType.ARMOR,
        stat_value=3,
        is_equippable=True,
        equip_slot=EquipSlot.CHEST,
    )
    player.inventory.add(armor)
    player.inventory.equip(armor.id)

    stats = _effective_stats(player)
    assert stats["attack"] == 8   # 3 + 5
    assert stats["defense"] == 5  # 2 + 3