"""Context builder — assembles curated prompts for the LLM."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from aiventure.model import Player, Position, Room, World
from aiventure.model.coords import Direction

if TYPE_CHECKING:
    from aiventure.model.entity import Entity
    from aiventure.model.item import Item


class ContextBuilder:
    """Builds system + user prompts tailored to each LLM task."""

    # -- Room generation context -- #

    @staticmethod
    def build_room_generation_context(
        world: World,
        source_room: Room,
        direction: Direction,
        target_position: Position,
    ) -> tuple[str, list[str]]:
        """Return (system_prompt, user_messages) for generating a new room."""

        system = textwrap.dedent(f"""\
            You are the dungeon master for a MUD-style text adventure.
            World theme: {world.world_seed or "A dark fantasy dungeon"}
            World lore: {world.world_description or ""}

            Generate a new room using the `generate_room` tool.
            The room should feel connected to the world theme and to the room the player is leaving.
            Include 1-3 exits (at least one should lead back to the source room).
            Optionally include items, entities, or interesting features.
            Be creative, atmospheric, and consistent with the world tone.
        """).strip()

        player_summary = _summarize_player(world.player)
        source_summary = (
            f"Current room: {source_room.name} — {source_room.description}"
        )

        user = textwrap.dedent(f"""\
            The player is leaving {source_room.name} by going {direction.value}.
            Generate the new room at position {target_position}.

            {source_summary}

            {player_summary}
        """).strip()

        return system, [user]

    # -- Action outcome context -- #

    @staticmethod
    def build_action_context(
        world: World,
        action_description: str,
    ) -> tuple[str, list[str]]:
        """Return (system_prompt, user_messages) for resolving a freeform action."""

        room = _current_room(world)
        system = textwrap.dedent(f"""\
            You are the dungeon master for a MUD-style text adventure.
            World theme: {world.world_seed or "A dark fantasy dungeon"}

            Determine the outcome of the player's action using the
            `describe_action_outcome` tool.  Be fair but interesting.
            The action may succeed, fail, or have unexpected consequences.
        """).strip()

        player_summary = _summarize_player(world.player)
        room_summary = _summarize_room(room) if room else "Location unknown."

        user = textwrap.dedent(f"""\
            {room_summary}

            {player_summary}

            The player attempts to: {action_description}
        """).strip()

        return system, [user]

    # -- Combat context -- #

    @staticmethod
    def build_combat_context(
        world: World,
        attacker: Player,
        attacker_stats: dict,
        defender: "Entity",
        defender_stats: dict,
    ) -> tuple[str, list[str]]:
        """Return (system_prompt, user_messages) for resolving a combat exchange."""
        system = textwrap.dedent(f"""\
            You are the dungeon master for a MUD-style text adventure.
            World theme: {world.world_seed or "A dark fantasy dungeon"}

            Determine the outcome of a combat exchange using the
            `describe_combat_outcome` tool.
            Be dramatic, fair, and consistent with the stats provided.
            Damage should scale with the attacker's ATK vs defender's DEF.
            The defender always gets a counter-attack unless they are dead.
        """).strip()

        room = _current_room(world)
        room_summary = _summarize_room(room) if room else "Location unknown."

        user = textwrap.dedent(f"""\
            {room_summary}

            Combat exchange:
            Attacker: {attacker.name} — {attacker_stats}
            Defender: {defender.name} — {defender_stats}

            Describe the exchange, damage dealt, and whether either falls.
            If the defender dies, include 0-2 loot items they drop.
        """).strip()

        return system, [user]

    # -- Item use context -- #

    @staticmethod
    def build_item_use_context(
        world: World,
        player: Player,
        item: "Item",
    ) -> tuple[str, list[str]]:
        """Return (system_prompt, user_messages) for resolving an item use."""
        system = textwrap.dedent(f"""\
            You are the dungeon master for a MUD-style text adventure.
            World theme: {world.world_seed or "A dark fantasy dungeon"}

            Determine what happens when the player uses an item.
            Use the `describe_item_use` tool.
            Be creative with effects but respect the item's type and stats.
        """).strip()

        player_summary = _summarize_player(player)

        user = textwrap.dedent(f"""\
            {player_summary}

            The player uses: {item.name}
            Type: {item.item_type.value}
            Stat value: {item.stat_value}
            Charges remaining: {item.charges}
            Description: {item.description}
        """).strip()

        return system, [user]

    # -- NPC dialogue context -- #

    @staticmethod
    def build_npc_dialogue_context(
        world: World,
        player: Player,
        npc: "Entity",
    ) -> tuple[str, list[str]]:
        """Return (system_prompt, user_messages) for NPC dialogue."""
        system = textwrap.dedent(f"""\
            You are the dungeon master for a MUD-style text adventure.
            World theme: {world.world_seed or "A dark fantasy dungeon"}

            Generate NPC dialogue using the `generate_npc_dialogue` tool.
            The NPC should speak in character, revealing information,
            offering quests, or trading items.
            Keep responses concise (2-4 sentences).
        """).strip()

        player_summary = _summarize_player(player)

        active_quest_titles = []
        for qid in player.active_quests:
            q = world.quests.get(qid)
            if q:
                active_quest_titles.append(f"- {q.title}")

        quests_text = "\n".join(active_quest_titles) if active_quest_titles else "(none)"

        user = textwrap.dedent(f"""\
            {player_summary}

            NPC: {npc.name}
            Personality: {npc.personality or "mysterious"}
            Entity type: {npc.entity_type.value}
            AI behavior: {npc.ai_behavior}

            Player's active quests:
            {quests_text}

            The player approaches and talks to {npc.name}.
            Generate a fitting response. Consider offering a quest if the player
            has none, or referencing active quests if relevant.
        """).strip()

        return system, [user]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_room(world: World) -> Room | None:
    player = world.player
    if not player or not isinstance(player, Player):
        return None
    if player.position is None:
        return None
    return world.get_room(player.position)


def _summarize_player(player: object) -> str:
    if not player or not isinstance(player, Player):
        return "Player: unknown"
    equipped_slots = ", ".join(
        slot.value for slot in player.inventory.equipped
    ) or "nothing"
    item_names = ", ".join(
        it.name for it in player.inventory.owned_items.values() if it
    ) or "empty"
    return (
        f"Player: {player.name}, level {player.level}, "
        f"HP {player.hp}/{player.max_hp}, ATK {player.attack}, DEF {player.defense}, "
        f"Gold {player.gold}, XP {player.xp}. "
        f"Equipped: {equipped_slots}. Inventory: {item_names}."
    )


def _summarize_room(room: Room) -> str:
    lines = [f"Room: {room.name}\n{room.description}"]
    if room.connected_entities:
        lines.append(f"Entities here: {len(room.connected_entities)}")
    if room.connected_items:
        lines.append(f"Items here: {len(room.connected_items)}")
    exits = {d.value: f"{p}" for d, p in room.exits.items()}
    if exits:
        lines.append(f"Exits: {', '.join(exits.keys())}")
    return "\n".join(lines)