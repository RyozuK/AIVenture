"""AIVenture — Main entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys

from aiventure.utils.config import load_config, GameConfig
from aiventure.utils.logging import setup_logging
from aiventure.model import Player, Position, Room, World
from aiventure.model.coords import Direction
from aiventure.llm.adapter import LLMAdapter
from aiventure.llm.adapters.openai import OpenAIAdapter
from aiventure.llm.adapters.custom import OpenAICompatibleAdapter
from aiventure.llm.adapters.ollama import OllamaAdapter
from aiventure.llm.service import LLMService
from aiventure.persistence.manager import SaveManager
from aiventure.persistence.providers.json_file import JsonFileProvider
from aiventure.persistence.providers.memory import MemoryProvider
from aiventure.persistence.providers.sqlite import SQLiteProvider
from aiventure.controller.session import GameSession
from aiventure.client.console import ConsoleClient
from aiventure.client.protocol import CommandResult


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_adapter(cfg: GameConfig) -> LLMAdapter:
    """Construct an LLM adapter from config."""
    llm = cfg.llm
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


def _build_save_manager(cfg: GameConfig) -> SaveManager:
    """Construct a SaveManager from config."""
    persist = cfg.persistence
    if persist.provider == "json":
        return SaveManager(JsonFileProvider(persist.path))
    elif persist.provider == "memory":
        return SaveManager(MemoryProvider())
    elif persist.provider == "sqlite":
        return SaveManager(SQLiteProvider(persist.path))
    else:
        raise ValueError(f"Unknown persistence provider: {persist.provider}")


# ---------------------------------------------------------------------------
# New / Load helpers (console mode)
# ---------------------------------------------------------------------------

async def _create_new_game(
    config: GameConfig,
    adapter: LLMAdapter,
    save_manager: SaveManager,
) -> GameSession:
    """Create a new game: generate world theme + starting room."""
    llm_service = LLMService(adapter)

    print("Generating world theme...")
    theme = await llm_service.generate_text(
        "Generate a one-sentence dark fantasy dungeon theme for a text adventure. "
        "Keep it to one line, no quotes.",
        max_tokens=64,
    )

    print("Generating starting room...")
    world = World(
        world_seed=theme.strip(),
        world_description=theme.strip(),
    )

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

    world.add_room(starting_room)
    world.explored_positions.add(Position(0, 0, 0))

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

    player_name = "Adventurer"
    try:
        player_name_input = input("Enter your name: ").strip()
        if player_name_input:
            player_name = player_name_input
    except (EOFError, KeyboardInterrupt):
        pass

    player = Player.create_default(player_name, Position(0, 0, 0))
    player.room_id = starting_room.id
    world.player = player

    session = GameSession(
        world=world,
        llm_service=llm_service,
        config=config,
    )
    session._save_manager = save_manager

    print(f"\nWelcome to {config.title}!")
    print(f"World: {theme.strip()}\n")

    return session


async def _load_game(
    config: GameConfig,
    adapter: LLMAdapter,
    save_manager: SaveManager,
) -> GameSession | None:
    """Load an existing game from a save slot."""
    slots = await save_manager.list_slots()
    if not slots:
        print("No saved games found.")
        return None

    print("\nSaved games:")
    for i, slot in enumerate(slots, 1):
        print(f"  {i}. {slot.name} — {slot.player_name or 'Unknown'} "
              f"(Lvl {slot.player_level}, turn {slot.turn_count})")

    try:
        choice = int(input("Select slot: ").strip()) - 1
        if choice < 0 or choice >= len(slots):
            print("Invalid choice.")
            return None
    except (ValueError, EOFError, KeyboardInterrupt):
        print("Invalid choice.")
        return None

    slot_name = slots[choice].name
    world = await save_manager.load_slot(slot_name)
    if world is None:
        print("Failed to load save.")
        return None

    llm_service = LLMService(adapter)
    session = GameSession(
        world=world,
        llm_service=llm_service,
        config=config,
    )
    session._save_manager = save_manager

    print(f"\nLoaded save '{slot_name}' (turn {world.turn_count})\n")
    return session


# ---------------------------------------------------------------------------
# Console game loop
# ---------------------------------------------------------------------------

async def _game_loop(session: GameSession, client: ConsoleClient) -> None:
    """Main game loop: show room, get input, process, display."""
    await client.start()

    room_desc = await session.describe_current_room()
    await client.send_result(CommandResult(
        session_id="console",
        narrative=room_desc,
    ))

    while session.world.player and session.world.player.is_alive:
        text = await client.get_input()
        if text is None:
            break

        if text.lower() in ("quit", "exit", "q"):
            result = await session.process_command("quit")
            await client.send_result(CommandResult(
                session_id="console",
                narrative=result["narrative"],
                game_over=True,
            ))
            break

        result = await session.process_command(text)

        if result.get("game_over"):
            await client.send_result(CommandResult(
                session_id="console",
                narrative=result["narrative"],
                game_over=True,
            ))
            break

        await client.send_result(CommandResult(
            session_id="console",
            turn=result.get("turn", 0),
            narrative=result["narrative"],
        ))

    await client.stop()


# ---------------------------------------------------------------------------
# Discord game mode
# ---------------------------------------------------------------------------

async def _run_discord(config: GameConfig) -> None:
    """Run the Discord bot game manager."""
    from aiventure.client.discord_manager import DiscordGameManager

    dc = config.discord
    if not dc.token:
        print("Error: Discord token not configured.")
        print("Set discord.token in config.yaml or use ${DISCORD_TOKEN} env var.")
        sys.exit(1)

    print("Starting Discord bot...")
    manager = DiscordGameManager(config)
    try:
        await manager.start()
    except (ImportError, KeyError) as e:
        print(f"Failed to start Discord bot: {e}")
        print("Make sure 'discord' is installed: pip install discord")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down Discord bot...")
    finally:
        await manager.stop()


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

async def _main_async(client_override: str | None = None) -> None:
    config = load_config()
    setup_logging(level="INFO")

    active_client = client_override or config.client.type

    # Discord mode — delegate to DiscordGameManager
    if active_client == "discord":
        await _run_discord(config)
        return

    # Default: console mode
    adapter = _build_adapter(config)
    save_manager = _build_save_manager(config)

    try:
        print("AIVenture")
        print("1. New Game")
        print("2. Load Game")
        choice = input("Select: ").strip()

        if choice == "1":
            session = await _create_new_game(config, adapter, save_manager)
        elif choice == "2":
            session = await _load_game(config, adapter, save_manager)
        else:
            print("Starting new game.")
            session = await _create_new_game(config, adapter, save_manager)

        if session:
            client = ConsoleClient(prompt=config.client.prompt)
            await _game_loop(session, client)
    finally:
        if hasattr(adapter, "close"):
            await adapter.close()


def main() -> None:
    """Entry point for the ``aiventure`` console script."""
    parser = argparse.ArgumentParser(description="AIVenture — AI dungeon crawl")
    parser.add_argument(
        "--client",
        choices=["console", "discord"],
        default=None,
        help="Client type to use (overrides config.yaml)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_main_async(client_override=args.client))
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()