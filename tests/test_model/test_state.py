"""Tests for World-level round-trip serialization."""

from __future__ import annotations

from aiventure.model import Position
from aiventure.model.world import Room, World
from aiventure.model.entity import Player
from aiventure.model.item import Item, ItemType
from aiventure.model.quest import Quest, Objective, Reward, QuestStatus


def test_world_roundtrip(origin: Position, starting_room: Room, player: Player):
    """Full round-trip: World -> dict -> World should preserve all state."""
    world = World(
        world_seed="dark dungeon",
        world_description="A treacherous underground labyrinth.",
    )
    world.add_room(starting_room)
    world.player = player
    world.explored_positions.add(origin)
    world.turn_count = 42

    data = world.to_dict()
    restored = World.from_dict(data)

    assert restored.world_seed == "dark dungeon"
    assert restored.world_description == "A treacherous underground labyrinth."
    assert restored.turn_count == 42
    assert origin in restored.rooms
    assert origin in restored.explored_positions
    assert restored.player is not None
    assert restored.player.name == "Hero"
    assert restored.player.level == 1


def test_world_roundtrip_with_items(origin: Position, starting_room: Room, player: Player):
    """Serialization includes items in inventory."""
    world = World()
    world.add_room(starting_room)
    world.player = player
    world.explored_positions.add(origin)

    sword = Item(name="Iron Sword", item_type=ItemType.WEAPON, stat_value=5)
    world.items[sword.id] = sword
    player.inventory.add(sword)

    data = world.to_dict()
    restored = World.from_dict(data)

    assert sword.id in restored.items
    restored_item = restored.items[sword.id]
    assert restored_item.name == "Iron Sword"
    assert restored_item.stat_value == 5


def test_world_roundtrip_with_quests(origin: Position, starting_room: Room, player: Player):
    """Serialization includes quests."""
    world = World()
    world.add_room(starting_room)
    world.player = player
    world.explored_positions.add(origin)

    quest = Quest(
        title="Slay the Dragon",
        objectives=[Objective(type="kill", target="dragon", required_count=1)],
        rewards=[Reward(type="xp", value={"amount": 100})],
        status=QuestStatus.ACTIVE,
    )
    world.quests[quest.id] = quest
    player.active_quests.append(quest.id)

    data = world.to_dict()
    restored = World.from_dict(data)

    assert quest.id in restored.quests
    restored_quest = restored.quests[quest.id]
    assert restored_quest.title == "Slay the Dragon"
    assert restored_quest.status == QuestStatus.ACTIVE
    assert len(restored_quest.objectives) == 1


def test_world_empty_roundtrip():
    """An empty world should round-trip without error."""
    world = World()
    data = world.to_dict()
    restored = World.from_dict(data)
    assert not restored.rooms
    assert not restored.entities
    assert restored.player is None
    assert restored.turn_count == 0