"""Tests for the Discord client — embed classification, truncation, and session management.

These tests do NOT require a live Discord connection or the ``discord`` package.
They exercise the pure-Python parts of the DiscordClient.
"""

from __future__ import annotations

import pytest
from aiventure.client.protocol import CommandResult
from aiventure.client.discord import (
    DiscordClient,
    REACTION_ACTIONS,
    DIRECTION_REACTIONS,
)


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_no_truncate_needed(self):
        assert DiscordClient._truncate("short", 100) == "short"

    def test_exact_length(self):
        text = "x" * 50
        assert DiscordClient._truncate(text, 50) == text

    def test_truncates_long_text(self):
        text = "x" * 200
        result = DiscordClient._truncate(text, 50)
        assert result == "x" * 47 + "..."
        assert len(result) == 50


# ---------------------------------------------------------------------------
# Reaction mappings (module-level constants)
# ---------------------------------------------------------------------------

class TestReactionMappings:
    def test_reaction_actions_defined(self):
        assert "⚔️" in REACTION_ACTIONS
        assert "🔍" in REACTION_ACTIONS
        assert "🎒" in REACTION_ACTIONS
        assert "👀" in REACTION_ACTIONS

    def test_direction_reactions_defined(self):
        assert "⬆️" in DIRECTION_REACTIONS
        assert DIRECTION_REACTIONS["⬆️"] == "north"
        assert DIRECTION_REACTIONS["➡️"] == "east"
        assert DIRECTION_REACTIONS["⬅️"] == "west"
        assert DIRECTION_REACTIONS["⬇️"] == "south"

    def test_reaction_action_mapping(self):
        verb, target = REACTION_ACTIONS["⚔️"]
        assert verb == "attack"
        assert target is None

    def test_direction_up_down(self):
        assert DIRECTION_REACTIONS["🔼"] == "up"
        assert DIRECTION_REACTIONS["🔽"] == "down"


# ---------------------------------------------------------------------------
# Embed builders — return plain dicts (no discord needed)
# ---------------------------------------------------------------------------

class TestEmbedBuilders:
    def test_room_embed_basic(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_room_embed("A dark room.")
        assert embed["description"] == "A dark room."
        assert embed["title"].startswith("📍")
        assert "color" in embed

    def test_room_embed_with_player_state(self):
        dc = DiscordClient(token="fake")
        state = {"hp": 50, "max_hp": 100, "level": 3, "gold": 250, "room_name": "Hall"}
        embed = dc._build_room_embed("A room.", state)
        assert "Hall" in embed["title"]
        assert "fields" in embed
        status_field = next(f for f in embed["fields"] if "Player" in f["name"])
        assert "50/100" in status_field["value"]
        assert "Level: 3" in status_field["value"].replace("**", "")

    def test_room_embed_equipped_and_inventory(self):
        dc = DiscordClient(token="fake")
        state = {
            "hp": 50, "max_hp": 100, "level": 1, "gold": 0, "room_name": "Cellar",
            "equipped": ["HAND: Sword"],
            "inventory_items": ["Shield", "Potion"],
        }
        embed = dc._build_room_embed("Room.", state)
        names = [f["name"] for f in embed["fields"]]
        assert any("Equipped" in n for n in names)
        assert any("Inventory" in n for n in names)

    def test_combat_embed_default(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_combat_embed("You hit for 10 damage!")
        assert "combat" in embed["title"].lower()
        # Default warning color since no death or level up
        assert embed["color"] == 0xf1c40f

    def test_combat_embed_level_up(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_combat_embed("You deal 20 damage! LEVEL UP!", {})
        assert embed["color"] == 0xe67e22  # EMBED_LEVEL_UP

    def test_combat_embed_death(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_combat_embed("You are slain!", {"hp": 0, "max_hp": 100})
        assert embed["color"] == 0x2c3e50  # EMBED_DEATH

    def test_combat_embed_with_hp_field(self):
        dc = DiscordClient(token="fake")
        state = {"hp": 45, "max_hp": 100}
        embed = dc._build_combat_embed("Combat!", state)
        hp_field = next(f for f in embed["fields"] if "HP" in f["name"])
        assert "45/100" in hp_field["value"]

    def test_death_embed(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_death_embed("You died.")
        assert embed["description"] == "You died."
        assert "died" in embed["title"].lower() or "death" in embed["title"].lower() or "died" in embed["title"]

    def test_quest_embed(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_quest_embed("Quest updated.")
        assert "quest" in embed["title"].lower()
        assert embed["description"] == "Quest updated."

    def test_inventory_embed(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_inventory_embed("Sword, Shield")
        assert "inventory" in embed["title"].lower()
        assert embed["color"] == 0x3498db  # EMBED_INFO

    def test_narrative_embed_default(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_narrative_embed("You walk.")
        assert "narrative" in embed["title"].lower()
        assert embed["description"] == "You walk."

    def test_narrative_embed_custom_title_color(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_narrative_embed("Found it!", "🔮 Magic", 0xff0000)
        assert embed["title"] == "🔮 Magic"
        assert embed["color"] == 0xff0000

    def test_menu_embed(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_menu_embed("Menu", "Choose wisely")
        assert embed["title"] == "Menu"
        assert embed["description"] == "Choose wisely"

    def test_embed_title_truncation(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_narrative_embed("x", "x" * 300)
        assert len(embed["title"]) <= 256

    def test_embed_description_truncation(self):
        dc = DiscordClient(token="fake")
        embed = dc._build_narrative_embed("x" * 3000)
        assert len(embed["description"]) <= 1990


# ---------------------------------------------------------------------------
# Embed classification
# ---------------------------------------------------------------------------

class TestClassifyEmbed:
    def _build_result(self, narrative: str, **kwargs) -> CommandResult:
        return CommandResult(
            session_id="test",
            narrative=narrative,
            **kwargs,
        )

    def test_death_via_flag(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("You fell from the bridge.", death=True)
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert any(kw in embed["title"].lower() for kw in ("died", "death", "dead"))

    def test_death_via_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("You are dead.")
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert any(kw in embed["title"].lower() for kw in ("died", "death", "dead"))

    def test_combat_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("You swing your sword and deal 15 damage!")
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert "combat" in embed["title"].lower()

    def test_level_up_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("You deal 20 damage. LEVEL UP!")
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert "combat" in embed["title"].lower()
        assert embed["color"] == 0xe67e22

    def test_quest_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("Quest completed: Find the Lost Blade!")
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert "quest" in embed["title"].lower()

    def test_inventory_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("Your inventory contains: Rusty Sword")
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert "inventory" in embed["title"].lower()

    def test_loot_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("You picked up a glowing crystal.")
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert "discovery" in embed["title"].lower()
        assert embed["color"] == 0xf39c12

    def test_dialogue_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result('The guard says, "Halt, adventurer!"')
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert "dialogue" in embed["title"].lower()
        assert embed["color"] == 0x3498db

    def test_default_narrative(self):
        dc = DiscordClient(token="fake")
        result = self._build_result("You walk down the hallway.")
        embed = dc._classify_and_build_embed(result.narrative, result, {})
        assert "narrative" in embed["title"].lower()


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestSessionManagement:
    def test_create_and_get_session(self):
        dc = DiscordClient(token="fake")
        ps = dc.create_session(123, None, "Hero")
        assert dc.get_session(123) is ps
        assert ps.player_name == "Hero"
        assert ps.game_active is True

    def test_remove_session(self):
        dc = DiscordClient(token="fake")
        dc.create_session(456, None, "Villain")
        assert dc.get_session(456) is not None
        dc.remove_session(456)
        assert dc.get_session(456) is None

    def test_get_nonexistent_session(self):
        dc = DiscordClient(token="fake")
        assert dc.get_session(999) is None

    def test_set_active_user(self):
        dc = DiscordClient(token="fake")
        dc.set_active_user(789)
        assert dc._active_user_id == 789

    def test_active_user_none_by_default(self):
        dc = DiscordClient(token="fake")
        assert dc._active_user_id is None


# ---------------------------------------------------------------------------
# DiscordConfig
# ---------------------------------------------------------------------------

class TestDiscordConfig:
    def test_defaults(self):
        from aiventure.utils.config import GameConfig
        cfg = GameConfig()
        assert cfg.discord.bot_name == "AIVentureBot"
        assert cfg.discord.reactions is True
        assert cfg.discord.reactions_timeout == 300
        assert cfg.discord.allow_dms_only is True
        assert cfg.discord.token is None

    def test_from_dict(self):
        from aiventure.utils.config import _build_from_dict
        data = {
            "discord": {
                "bot_name": "MyBot",
                "reactions": False,
                "token": "test-token",
            },
        }
        cfg = _build_from_dict(data)
        assert cfg.discord.bot_name == "MyBot"
        assert cfg.discord.reactions is False
        assert cfg.discord.token == "test-token"

    def test_embed_color_default(self):
        from aiventure.utils.config import GameConfig
        cfg = GameConfig()
        assert cfg.discord.embed_color == 0x4a3728


# ---------------------------------------------------------------------------
# DiscordClient initialization
# ---------------------------------------------------------------------------

class TestDiscordClientInit:
    def test_default_values(self):
        dc = DiscordClient(token="tok")
        assert dc._bot_name == "AIVentureBot"
        assert dc._embed_color == 0x4a3728
        assert dc._reactions_enabled is True
        assert dc._reactions_timeout == 300
        assert dc._allow_dms_only is True
        assert dc._running is False

    def test_custom_values(self):
        dc = DiscordClient(
            token="tok",
            bot_name="CustomBot",
            embed_color=0xff0000,
            reactions=False,
            reactions_timeout=60,
        )
        assert dc._bot_name == "CustomBot"
        assert dc._embed_color == 0xff0000
        assert dc._reactions_enabled is False
        assert dc._reactions_timeout == 60


# ---------------------------------------------------------------------------
# Async stubs (no real discord connection)
# ---------------------------------------------------------------------------

class TestAsyncStub:
    @pytest.mark.asyncio
    async def test_send_result_no_user(self):
        dc = DiscordClient(token="fake")
        result = CommandResult(session_id="t", narrative="Hi")
        await dc.send_result(result)
        # Should not crash, just warn

    @pytest.mark.asyncio
    async def test_get_input_no_user(self):
        dc = DiscordClient(token="fake")
        assert await dc.get_input() is None

    @pytest.mark.asyncio
    async def test_get_input_no_session(self):
        dc = DiscordClient(token="fake")
        dc.set_active_user(999)
        assert await dc.get_input() is None

    @pytest.mark.asyncio
    async def test_get_input_with_session(self):
        dc = DiscordClient(token="fake")
        dc.create_session(111, None, "Player")
        dc.set_active_user(111)
        ps = dc.get_session(111)
        await ps.message_queue.put("north")
        assert await dc.get_input() == "north"

    @pytest.mark.asyncio
    async def test_stop(self):
        dc = DiscordClient(token="fake")
        await dc.stop()
        assert dc._running is False