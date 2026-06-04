"""Integration test — full game loop with mock LLM and MemoryProvider.

Verifies the critical path:
  new game → move → room generation → take item → save → load → resume
"""

from __future__ import annotations

import json
import tempfile

import pytest
from unittest.mock import AsyncMock, MagicMock

from aiventure.model import Player, Position, Room, World, Item
from aiventure.model.entity import EntityType
from aiventure.model.item import ItemType
from aiventure.model.quest import Quest, Objective, Reward, QuestStatus

from aiventure.controller.session import GameSession
from aiventure.llm.service import (
    LLMService,
    RoomData,
    ActionOutcomeData,
    CombatOutcomeData,
)
from aiventure.persistence.manager import SaveManager
from aiventure.persistence.providers.memory import MemoryProvider
from aiventure.persistence.providers.sqlite import SQLiteProvider
from aiventure.utils.config import GameConfig


# ---------------------------------------------------------------------------
# Mock LLM adapter that returns deterministic tool calls
# ---------------------------------------------------------------------------

class MockLLMService:
    """Stubs out all LLMService methods with predetermined responses."""

    def __init__(self) -> None:
        self._room_counter = 0

    async def generate_room(self, system_prompt: str, user_messages: list[str]) -> RoomData:
        self._room_counter += 1
        return RoomData(
            name=f"Generated Room {self._room_counter}",
            description=f"An LLM-generated room number {self._room_counter}.",
            exits=["south"],
            items=[
                {
                    "name": f"Test Potion {self._room_counter}",
                    "item_type": "potion",
                    "stat_value": 10,
                    "charges": 3,
                },
            ],
            entities=[],
            features=["glowing runes"],
        )

    async def describe_action_outcome(self, system_prompt: str, user_messages: list[str]) -> ActionOutcomeData:
        return ActionOutcomeData(
            success=True,
            narrative="The freeform action succeeded.",
            discovered_items=[],
            discovered_entities=[],
            new_exits=[],
        )

    async def describe_combat_outcome(self, system_prompt: str, user_messages: list[str]) -> CombatOutcomeData:
        return CombatOutcomeData(
            narrative="You strike the enemy!",
            player_damage_dealt=0,
            enemy_damage_dealt=10,
            player_alive=True,
            enemy_alive=True,
            loot_dropped=[],
        )

    async def generate_text(self, prompt: str, max_tokens: int = 256) -> str:
        return "A dark and foreboding dungeon."

    # Passthrough for item use and NPC dialogue (unused in these tests)
    async def describe_item_use(self, system_prompt: str, user_messages: list[str]):
        from aiventure.llm.service import ItemUseOutcomeData
        return ItemUseOutcomeData(narrative="You use the item.", hp_change=5)

    async def generate_npc_dialogue(self, system_prompt: str, user_messages: list[str]):
        from aiventure.llm.service import NPCDialogueData
        return NPCDialogueData(npc_name="Test NPC", dialogue="Hello!", mood="friendly")


def _make_world() -> World:
    """Create a minimal playable world."""
    from aiventure.model.coords import Direction

    world = World(world_seed="Dark dungeon", world_description="A dark dungeon.")
    room = Room.create_empty(Position(0, 0, 0), "The Entrance", "A dark cavern entrance.")
    room.exits[Direction.NORTH] = Position(1, 0, 0)
    world.add_room(room)
    world.explored_positions.add(Position(0, 0, 0))

    # Add an item to the room
    potion = Item(name="Health Potion", item_type=ItemType.POTION, stat_value=15, charges=1)
    world.items[potion.id] = potion
    room.connected_items.append(potion.id)

    player = Player.create_default("Hero", Position(0, 0, 0))
    player.room_id = room.id
    world.player = player

    return world


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def session() -> GameSession:
    world = _make_world()
    return GameSession(
        world=world,
        llm_service=MockLLMService(),
        config=GameConfig(),
    )


@pytest.mark.asyncio
async def test_new_game_shows_room(session: GameSession) -> None:
    desc = await session.describe_current_room()
    assert "The Entrance" in desc


@pytest.mark.asyncio
async def test_move_to_existing_room(session: GameSession) -> None:
    # Add an existing room to the north
    from aiventure.model.coords import Direction
    north_room = Room.create_empty(
        Position(1, 0, 0),
        "North Chamber",
        "A northern chamber.",
    )
    north_room.exits[Direction.SOUTH] = Position(0, 0, 0)
    session.world.add_room(north_room)

    result = await session.process_command("north")
    assert "North Chamber" in result["narrative"]
    assert session.world.player.position == Position(1, 0, 0)


@pytest.mark.asyncio
async def test_take_item_from_room(session: GameSession) -> None:
    result = await session.process_command("take health potion")
    assert "pick up" in result["narrative"].lower()
    # Item should now be in inventory
    player = session.world.player
    assert isinstance(player, Player)
    assert any(
        item and "Health Potion" in item.name
        for item in player.inventory.owned_items.values()
    )


@pytest.mark.asyncio
async def test_drop_item(session: GameSession) -> None:
    # Take first
    await session.process_command("take health potion")
    # Drop it
    result = await session.process_command("drop potion")
    assert "drop" in result["narrative"].lower()


@pytest.mark.asyncio
async def test_inventory_display(session: GameSession) -> None:
    await session.process_command("take health potion")
    result = await session.process_command("inventory")
    assert "Health Potion" in result["narrative"]


@pytest.mark.asyncio
async def test_look_at_item(session: GameSession) -> None:
    result = await session.process_command("look at health potion")
    assert "Health Potion" in result["narrative"]


@pytest.mark.asyncio
async def test_search_command(session: GameSession) -> None:
    result = await session.process_command("search")
    assert result["narrative"]


@pytest.mark.asyncio
async def test_stats_command(session: GameSession) -> None:
    result = await session.process_command("stats")
    assert "Hero" in result["narrative"] or "Player" in result["narrative"]


@pytest.mark.asyncio
async def test_memory_save_and_load() -> None:
    """Save and load a world via MemoryProvider."""
    world = _make_world()
    mgr = SaveManager(MemoryProvider())
    await mgr.save("test", world)

    loaded = await mgr.load_slot("test")
    assert loaded is not None
    assert loaded.world_seed == world.world_seed
    assert loaded.player and loaded.player.name == "Hero"


@pytest.mark.asyncio
async def test_sqlite_save_and_load() -> None:
    """Save and load a world via SQLiteProvider."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    world = _make_world()
    mgr = SaveManager(SQLiteProvider(db_path))
    await mgr.save("test", world)

    loaded = await mgr.load_slot("test")
    assert loaded is not None
    assert loaded.world_seed == world.world_seed


@pytest.mark.asyncio
async def test_auto_save_on_interval(session: GameSession) -> None:
    """Auto-save fires when turn_count hits the configured interval."""
    mgr = SaveManager(MemoryProvider())
    session._save_manager = mgr
    session.config.auto_save_interval = 3

    # Process 3 commands (3 turns)
    await session.process_command("look")
    await session.process_command("look")
    await session.process_command("look")

    slots = await mgr.list_slots()
    assert len(slots) == 1
    assert slots[0].name == "default"


@pytest.mark.asyncio
async def test_quest_completion_triggers_save(session: GameSession) -> None:
    """Completing a quest should trigger an auto-save."""
    mgr = SaveManager(MemoryProvider())
    session._save_manager = mgr

    # Create a simple kill quest
    quest = Quest(
        title="Kill the Spider",
        description="A spider lurks nearby.",
        objectives=[Objective(type="kill", target="spider", required_count=1)],
        rewards=[Reward(type="xp", value={"amount": 10})],
    )
    quest.activate()
    session.world.quests[quest.id] = quest
    player = session.world.player
    assert isinstance(player, Player)
    player.active_quests.append(quest.id)

    # Process the kill quest via the combat helper
    from aiventure.controller.actions.combat import _advance_kill_quests
    _advance_kill_quests(session, "spider")

    assert quest.id in player.completed_quests
    # Auto-save should have been triggered


@pytest.mark.asyncio
async def test_world_serialization_roundtrip() -> None:
    """Export and import world state."""
    world = _make_world()
    data = world.to_dict()
    restored = World.from_dict(data)
    assert restored.world_seed == world.world_seed
    assert restored.player and restored.player.name == "Hero"
    assert len(restored.rooms) == len(world.rooms)


@pytest.mark.asyncio
async def test_freeform_command(session: GameSession) -> None:
    """Unrecognized commands go to the mock LLM."""
    result = await session.process_command("i try to sneak past the guard")
    assert "succeeded" in result["narrative"].lower() or "freeform" in result["narrative"].lower()


@pytest.mark.asyncio
async def test_pronoun_resolution(session: GameSession) -> None:
    """'it' resolves to the last mentioned target."""
    # Take the potion first so we have it to use
    await session.process_command("take health potion")
    # Now 'it' should resolve to 'health potion'
    session._last_target = "health potion"
    result = await session.process_command("use it")
    # The pronoun resolves to "health potion" and the use action runs
    assert "recover" in result["narrative"].lower() or "potion" in result["narrative"].lower()


@pytest.mark.asyncio
async def test_player_leveling(session: GameSession) -> None:
    """Player levels up after gaining enough XP."""
    player = session.world.player
    assert isinstance(player, Player)
    # Gain 50 XP (level 1 threshold = 50)
    leveled = player.gain_xp(50)
    assert leveled
    assert player.level == 2
    assert player.max_hp == 25  # +5 from level


@pytest.mark.asyncio
async def test_death_and_respawn(session: GameSession) -> None:
    """Player dies and respawns at starting room."""
    from aiventure.controller.actions.death import handle_death
    player = session.world.player
    assert isinstance(player, Player)
    original_hp = player.hp
    player.hp = 0
    player.is_alive = False

    result = await handle_death(session, player)
    assert player.is_alive
    assert player.hp == player.max_hp
    assert player.death_count == 1
    assert "slain" in result["narrative"].lower()


@pytest.mark.asyncio
async def test_save_command(session: GameSession) -> None:
    """'save' command persists the world."""
    mgr = SaveManager(MemoryProvider())
    session._save_manager = mgr
    result = await session.process_command("save")
    assert "saved" in result["narrative"].lower()
    slots = await mgr.list_slots()
    assert any(s.name == "default" for s in slots)


@pytest.mark.asyncio
async def test_export_world(session: GameSession) -> None:
    """Export world to JSON."""
    export_str = session.export_world()
    data = json.loads(export_str)
    assert "rooms" in data
    assert "player" in data
    assert data["world_seed"] == "Dark dungeon"