"""Discord bot manager — handles the full Discord game loop with per-player sessions.

Usage::

    from aiventure.client.discord_manager import DiscordGameManager
    manager = DiscordGameManager(config)
    await manager.start()
    # blocks until shutdown
    await manager.stop()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiventure.model import Player, Position, Room, World
from aiventure.model.coords import Direction
from aiventure.llm.service import LLMService
from aiventure.persistence.manager import SaveManager
from aiventure.controller.session import GameSession
from aiventure.utils.config import GameConfig

from .discord import DiscordClient

logger = logging.getLogger("aiventure.client.discord_manager")


class DiscordGameManager:
    """Manages the full Discord bot lifecycle: login, per-player sessions,
    game loops, new game creation, and load game flow.

    Each Discord user gets their own ``GameSession`` and ``SaveManager``.
    """

    def __init__(self, config: GameConfig) -> None:
        self._config = config
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Discord bot and begin accepting players."""
        self._running = True

        # Build shared components
        adapter = _build_adapter(self._config)
        llm_service = LLMService(adapter)
        save_manager = _build_save_manager(self._config)

        # Build the client
        dc = self._config.discord
        client = DiscordClient(
            token=dc.token or "",
            bot_name=dc.bot_name,
            embed_color=dc.embed_color,
            reactions=dc.reactions,
            reactions_timeout=dc.reactions_timeout,
            allow_dms_only=dc.allow_dms_only,
            generate_indicator=dc.generate_indicator,
            death_emoji=dc.death_emoji,
            level_up_emoji=dc.level_up_emoji,
            quest_emoji=dc.quest_emoji,
            loot_emoji=dc.loot_emoji,
        )

        # Store references for per-player game loops
        self._adapter = adapter
        self._llm_service = llm_service
        self._save_manager = save_manager
        self._client = client

        # Start the bot
        await client.start()

        # Monitor loop
        await self._monitor_loop()

    async def stop(self) -> None:
        """Stop the bot and clean up."""
        self._running = False
        if hasattr(self, "_client"):
            await self._client.stop()
        if hasattr(self, "_adapter") and hasattr(self._adapter, "close"):
            await self._adapter.close()
        # Cancel all player tasks
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Discord game manager stopped.")

    # ------------------------------------------------------------------
    # Monitor loop — spawn game loops for new players
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Periodically check for new player sessions and spawn game loops."""
        while self._running:
            try:
                await asyncio.sleep(1)
                client = self._client
                if client is None:
                    continue

                # Find sessions that are in menu flow (not yet active)
                for user_id, ps in list(client._sessions.items()):
                    if ps.session is not None and not ps.game_active:
                        # Player chose new/load — handle menu response
                        await self._handle_menu_choice(user_id, ps)
                    elif ps.session is not None and ps.game_active:
                        # Already active — ensure game loop task exists
                        if not hasattr(ps, "_game_loop_task") or ps._game_loop_task.done():
                            task = asyncio.create_task(
                                self._player_game_loop(user_id, ps.session),
                            )
                            ps._game_loop_task = task
                            self._tasks.append(task)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in monitor loop")

    async def _handle_menu_choice(self, user_id: int, ps: "DiscordClient._PlayerSession") -> None:
        """Process the player's new/load game choice from the menu."""
        try:
            choice = await asyncio.wait_for(ps.message_queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            return

        if choice == "__NEW_GAME__":
            session = await self._create_new_game(user_id)
            if session:
                ps.session = session
                # Show starting room
                room_desc = await session.describe_current_room()
                self._client.set_active_user(user_id)
                await self._client.show_room(user_id, room_desc)

        elif choice == "__LOAD_GAME__":
            session = await self._load_game(user_id)
            if session:
                ps.session = session
                room_desc = await session.describe_current_room()
                self._client.set_active_user(user_id)
                await self._client.show_room(user_id, room_desc)

    # ------------------------------------------------------------------
    # Per-player game loop
    # ------------------------------------------------------------------

    async def _player_game_loop(self, user_id: int, session: GameSession) -> None:
        """Run the main game loop for a single Discord player."""
        logger.info("Starting game loop for user %d", user_id)
        client = self._client

        while self._running:
            try:
                # Set active user context
                client.set_active_user(user_id)
                ps = client.get_session(user_id)
                if ps is None or not ps.game_active:
                    break

                # Send "thinking" indicator
                await client.send_result(
                    __import__("aiventure.client.protocol", fromlist=["CommandResult"]).CommandResult(
                        session_id=f"discord:{user_id}",
                        narrative=f"{client._generate_indicator} Thinking...",
                    )
                )

                # Wait for input
                text = await client.get_input()
                if text is None:
                    break

                # Process quit
                if text.lower() in ("quit", "exit", "q"):
                    from aiventure.client.protocol import CommandResult
                    result = await session.process_command("quit")
                    await client.send_result(
                        CommandResult(
                            session_id=f"discord:{user_id}",
                            narrative=result["narrative"],
                            game_over=True,
                        )
                    )
                    client.remove_session(user_id)
                    break

                # Process command
                result = await session.process_command(text)

                # Build player state snapshot
                player_state = self._build_player_state(session.world)

                from aiventure.client.protocol import CommandResult
                cmd_result = CommandResult(
                    session_id=f"discord:{user_id}",
                    turn=result.get("turn", 0),
                    narrative=result.get("narrative", ""),
                    player_state=player_state,
                    game_over=result.get("game_over", False),
                    death=result.get("death"),
                )
                await client.send_result(cmd_result)

                if result.get("game_over"):
                    client.remove_session(user_id)
                    break

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in game loop for user %d", user_id)

        logger.info("Game loop ended for user %d", user_id)

    # ------------------------------------------------------------------
    # Game creation helpers
    # ------------------------------------------------------------------

    async def _create_new_game(self, user_id: int) -> GameSession | None:
        """Create a new game for a Discord user."""
        llm_service = self._llm_service

        # Generate world theme
        theme = await llm_service.generate_text(
            "Generate a one-sentence dark fantasy dungeon theme for a text adventure. "
            "Keep it to one line, no quotes.",
            max_tokens=64,
        )

        # Generate starting room
        system, messages = (
            "You are a dungeon master. Generate the starting room of a dark fantasy dungeon.\n"
            f"World theme: {theme.strip()}\n"
            "Use the generate_room tool. This is the entrance room — safe but atmospheric.\n"
            "Include at least one exit direction.",
            ["Generate the starting room of the dungeon at position (0, 0, 0)."],
        )
        room_data = await llm_service.generate_room(system, messages)

        starting_room = Room.create_empty(
            Position(0, 0, 0),
            room_data.name or "The Entrance",
            room_data.description or "A dimly lit cavern entrance.",
        )
        starting_room.features = room_data.features

        for exit_dir_name in room_data.exits:
            d = Direction.from_str(exit_dir_name)
            if d:
                starting_room.exits[d] = d.apply_to(Position(0, 0, 0))

        world = World(
            world_seed=theme.strip(),
            world_description=theme.strip(),
        )
        world.add_room(starting_room)
        world.explored_positions.add(Position(0, 0, 0))

        # Add items from generated room
        for item_data in room_data.items:
            from aiventure.model import Item
            from aiventure.model.item import ItemType
            try:
                item_type = ItemType(item_data.get("item_type", "treasure"))
            except ValueError:
                item_type = ItemType.TREASURE
            item = Item(
                name=item_data.get("name", "Unknown Item"),
                description=item_data.get("description", ""),
                item_type=item_type,
                stat_value=item_data.get("stat_value", 0),
            )
            world.items[item.id] = item
            starting_room.connected_items.append(item.id)

        # Ask for player name via Discord
        client = self._client
        ps = client.get_session(user_id)

        try:
            import discord
            channel = await client._get_channel_for_user(user_id)
            if channel:
                embed = discord.Embed(
                    title="📝 New Game",
                    description="What is your adventurer's name?",
                    color=client._embed_color,
                )
                await channel.send(embed=embed)

                name_input = await asyncio.wait_for(
                    ps.message_queue.get(),
                    timeout=60.0,
                )
                if name_input and name_input not in ("__NEW_GAME__", "__LOAD_GAME__"):
                    player_name = name_input.strip()
                else:
                    player_name = f"Player{user_id % 10000}"
            else:
                player_name = f"Player{user_id % 10000}"
        except (asyncio.TimeoutError, Exception):
            player_name = f"Player{user_id % 10000}"

        player = Player.create_default(player_name, Position(0, 0, 0))
        player.room_id = starting_room.id
        world.player = player

        session = GameSession(
            world=world,
            llm_service=llm_service,
            config=self._config,
        )
        session._save_manager = self._save_manager

        return session

    async def _load_game(self, user_id: int) -> GameSession | None:
        """Load a saved game for a Discord user."""
        save_manager = self._save_manager
        client = self._client
        ps = client.get_session(user_id)

        slots = await save_manager.list_slots()
        if not slots:
            try:
                import discord
                channel = await client._get_channel_for_user(user_id)
                if channel:
                    embed = discord.Embed(
                        title="📁 No Saves Found",
                        description="You have no saved games. Type **new** to start a new adventure!",
                        color=0xe74c3c,
                    )
                    await channel.send(embed=embed)
            except Exception:
                pass
            return None

        # Show save list as embed
        slots_text = "\n".join(
            f"**{i + 1}.** {slot.name} — {slot.player_name or 'Unknown'} "
            f"(Lvl {slot.player_level}, turn {slot.turn_count})"
            for i, slot in enumerate(slots)
        )

        try:
            import discord
            channel = await client._get_channel_for_user(user_id)
            if channel:
                embed = discord.Embed(
                    title="📁 Saved Games",
                    description=f"Type a number to load:\n\n{slots_text}",
                    color=client._embed_color,
                )
                await channel.send(embed=embed)

                choice_input = await asyncio.wait_for(
                    ps.message_queue.get(),
                    timeout=60.0,
                )
                try:
                    choice = int(choice_input.strip()) - 1
                    if 0 <= choice < len(slots):
                        slot_name = slots[choice].name
                    else:
                        return None
                except ValueError:
                    return None
            else:
                return None
        except (asyncio.TimeoutError, Exception):
            return None

        world = await save_manager.load_slot(slot_name)
        if world is None:
            return None

        session = GameSession(
            world=world,
            llm_service=self._llm_service,
            config=self._config,
        )
        session._save_manager = save_manager

        return session

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_player_state(world: World) -> dict:
        """Build a player state dict for Discord embeds."""
        player = world.player
        if not player or not isinstance(player, Player):
            return {}

        state = {
            "room_name": "",
            "hp": player.hp,
            "max_hp": player.max_hp,
            "level": player.level,
            "gold": player.gold,
        }

        # Room name
        if player.position:
            room = world.get_room(player.position)
            if room:
                state["room_name"] = room.name

        # Equipped items
        equipped = []
        from aiventure.model.item import EquipSlot
        for slot in EquipSlot:
            if slot == EquipSlot.NONE:
                continue
            item = player.inventory.get_equipped(slot)
            if item:
                equipped.append(f"{slot.value}: {item.name}")
        state["equipped"] = equipped

        # Inventory items
        inv_items = [item.name for item in player.inventory.owned_items.values()]
        state["inventory_items"] = inv_items

        return state


# ---------------------------------------------------------------------------
# Shared builder functions (mirrors main.py)
# ---------------------------------------------------------------------------

def _build_adapter(config: GameConfig):
    """Build an LLM adapter from config."""
    from aiventure.llm.adapters.openai import OpenAIAdapter
    from aiventure.llm.adapters.custom import OpenAICompatibleAdapter
    from aiventure.llm.adapters.ollama import OllamaAdapter

    llm = config.llm
    if llm.provider == "openai":
        return OpenAIAdapter(
            model=llm.model,
            api_key=llm.api_key,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
        )
    elif llm.provider == "ollama":
        return OllamaAdapter(
            endpoint=llm.endpoint,
            model=llm.model,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
        )
    elif llm.provider == "custom":
        return OpenAICompatibleAdapter(
            endpoint=llm.endpoint,
            model=llm.model,
            api_key=llm.api_key,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {llm.provider}")


def _build_save_manager(config: GameConfig):
    """Build a SaveManager from config."""
    from aiventure.persistence.providers.json_file import JsonFileProvider
    from aiventure.persistence.providers.memory import MemoryProvider
    from aiventure.persistence.providers.sqlite import SQLiteProvider

    persist = config.persistence
    if persist.provider == "json":
        return SaveManager(JsonFileProvider(persist.path))
    elif persist.provider == "memory":
        return SaveManager(MemoryProvider())
    elif persist.provider == "sqlite":
        return SaveManager(SQLiteProvider(persist.path))
    else:
        raise ValueError(f"Unknown persistence provider: {persist.provider}")