"""Discord bot client — full implementation with embeds, reactions, and per-player sessions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from .base import Client
from .protocol import CommandResult

logger = logging.getLogger("aiventure.client.discord")

# ---------------------------------------------------------------------------
# Reaction quick-action mapping
# ---------------------------------------------------------------------------

# emoji → (verb, optional target)
REACTION_ACTIONS: dict[str, tuple[str, str | None]] = {
    "⚔️": ("attack", None),
    "🔍": ("search", None),
    "🎒": ("inventory", None),
    "👀": ("look", None),
    "🗺️": ("quests", None),
    "💾": ("save", None),
    "📊": ("stats", None),
}

# Direction reactions
DIRECTION_REACTIONS: dict[str, str] = {
    "⬆️": "north",
    "⬇️": "south",
    "➡️": "east",
    "⬅️": "west",
    "🔼": "up",
    "🔽": "down",
}

# Colors
EMBED_SUCCESS = 0x2ecc71
EMBED_WARNING = 0xf1c40f
EMBED_DANGER = 0xe74c3c
EMBED_INFO = 0x3498db
EMBED_LOOT = 0xf39c12
EMBED_QUEST = 0x9b59b6
EMBED_DEATH = 0x2c3e50
EMBED_LEVEL_UP = 0xe67e22

# Discord message max length splits
MAX_EMBED_DESCRIPTION = 1990
MAX_EMBED_FIELD_VALUE = 1024
MAX_EMBED_FOOTER = 1024
MAX_EMBED_TITLE = 256


# ---------------------------------------------------------------------------
# Player session wrapper
# ---------------------------------------------------------------------------

@dataclass
class _PlayerSession:
    """Tracks per-player game state for the Discord bot."""

    session: Any  # GameSession
    message_queue: asyncio.Queue[str | None] = field(default_factory=asyncio.Queue)
    current_message_id: int | None = None
    game_active: bool = False
    player_name: str = ""


# ---------------------------------------------------------------------------
# DiscordClient
# ---------------------------------------------------------------------------

class DiscordClient(Client):
    """Full Discord bot client with embeds and reaction quick-actions.

    Supports multiple concurrent players via DMs.  Each player gets their
    own ``GameSession``.  Embeds are used for room descriptions, combat,
    inventory, etc.  Reaction quick-actions let players tap emoji for
    common commands.

    All embed builders produce plain dicts.  Conversion to
    ``discord.Embed.from_dict`` happens only at send time, so the module
    is testable without the ``discord`` package installed.
    """

    def __init__(
        self,
        token: str,
        bot_name: str = "AIVentureBot",
        embed_color: int = 0x4a3728,
        reactions: bool = True,
        reactions_timeout: int = 300,
        allow_dms_only: bool = True,
        generate_indicator: str = "⏳",
        death_emoji: str = "💀",
        level_up_emoji: str = "⬆️",
        quest_emoji: str = "📜",
        loot_emoji: str = "✨",
    ) -> None:
        self._token = token
        self._bot_name = bot_name
        self._embed_color = embed_color
        self._reactions_enabled = reactions
        self._reactions_timeout = reactions_timeout
        self._allow_dms_only = allow_dms_only
        self._generate_indicator = generate_indicator
        self._death_emoji = death_emoji
        self._level_up_emoji = level_up_emoji
        self._quest_emoji = quest_emoji
        self._loot_emoji = loot_emoji

        self._running = False
        self._intents = None
        self._bot = None

        # Per-user sessions keyed by discord User.id
        self._sessions: dict[int, _PlayerSession] = {}

    # ------------------------------------------------------------------
    # Client ABC implementation
    # ------------------------------------------------------------------

    async def send_result(self, result: CommandResult) -> None:
        """Send a CommandResult to a specific player via Discord embeds.

        The caller must have set ``self._active_user_id`` before calling.
        """
        if self._active_user_id is None:
            logger.warning("No active user, cannot send result")
            print(f"[Discord] {result.narrative}")
            return

        await self._send_embed_to_user(self._active_user_id, result)

    async def get_input(self) -> str | None:
        """Wait for player input from Discord DMs.

        Returns text from message or reaction action.
        """
        if self._active_user_id is None:
            return None

        ps = self._sessions.get(self._active_user_id)
        if ps is None:
            return None

        try:
            text = await asyncio.wait_for(ps.message_queue.get(), timeout=60.0)
            return text
        except asyncio.TimeoutError:
            return None

    async def start(self) -> None:
        """Start the Discord bot and connect."""
        try:
            import discord  # noqa: F401
        except ImportError:
            logger.warning(
                "discord package not installed.  DiscordClient will use console fallback.  "
                "Install with: pip install discord"
            )
            print("[Discord] discord.py not installed — falling back to console mode.")
            self._running = True
            return

        self._intents = discord.Intents.default()
        self._intents.message_content = True
        self._intents.members = True
        self._intents.dm_messages = True

        self._bot = discord.Client(intents=self._intents)

        # Wire event handlers
        self._bot.event(self._on_ready)
        self._bot.event(self._on_message)
        self._bot.event(self._on_reaction_add)

        self._running = True
        logger.info("Starting Discord bot '%s'...", self._bot_name)
        await self._bot.login(self._token)
        await self._bot.connect()

    async def stop(self) -> None:
        """Disconnect the bot gracefully."""
        self._running = False
        if self._bot:
            await self._bot.close()
        logger.info("Discord bot stopped.")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def _active_user_id(self) -> int | None:
        """Return the current active user for send_result / get_input."""
        return getattr(self, "_current_user_id", None)

    def set_active_user(self, user_id: int) -> None:
        """Set the active user context for send/get calls."""
        self._current_user_id = user_id

    # ------------------------------------------------------------------
    # Discord event handlers
    # ------------------------------------------------------------------

    async def _on_ready(self):
        try:
            import discord
        except ImportError:
            return
        logger.info("Logged in as %s (ID: %s)", self._bot.user, self._bot.user.id)

    async def _on_message(self, message):
        try:
            import discord
        except ImportError:
            return

        # Ignore own messages and non-DMs if configured
        if message.author == self._bot.user:
            return
        if self._allow_dms_only and not isinstance(message.channel, discord.DMChannel):
            await message.channel.send("Please start a game via DMs with the bot.")
            return
        if message.content.startswith("/"):
            return

        user_id = message.author.id

        # --- New game flow ---
        if user_id not in self._sessions:
            await self._send_new_game_menu(message.channel, message.author)
            return

        ps = self._sessions[user_id]
        if not ps.game_active:
            # In menu flow — handle new/load choice
            if message.content.strip().lower() in ("new", "1", "n"):
                await ps.message_queue.put("__NEW_GAME__")
            elif message.content.strip().lower() in ("load", "2", "l"):
                await ps.message_queue.put("__LOAD_GAME__")
            else:
                await message.channel.send(
                    "Type **new** for a new game or **load** to load a save.",
                )
            return

        # Active game — enqueue the text
        text = message.content.strip()
        if text:
            await ps.message_queue.put(text)

    async def _on_reaction_add(self, reaction, user):
        if user == self._bot.user:
            return

        user_id = user.id
        ps = self._sessions.get(user_id)
        if ps is None or not ps.game_active:
            return

        emoji = str(reaction.emoji)

        # Check direction reactions
        if emoji in DIRECTION_REACTIONS:
            await ps.message_queue.put(DIRECTION_REACTIONS[emoji])
            return

        # Check action reactions
        if emoji in REACTION_ACTIONS:
            verb, target = REACTION_ACTIONS[emoji]
            await ps.message_queue.put(f"{verb} {target}" if target else verb)
            return

    # ------------------------------------------------------------------
    # Embed builders — return plain dicts (no discord dependency)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_embed(title: str, description: str, color: int, fields: list[dict] | None = None) -> dict:
        """Build a plain-dict embed representation."""
        embed: dict[str, Any] = {
            "title": DiscordClient._truncate(title, MAX_EMBED_TITLE),
            "description": DiscordClient._truncate(description, MAX_EMBED_DESCRIPTION),
            "color": color,
        }
        if fields:
            embed["fields"] = [
                {
                    "name": DiscordClient._truncate(f.get("name", ""), 256),
                    "value": DiscordClient._truncate(f.get("value", ""), MAX_EMBED_FIELD_VALUE),
                    "inline": f.get("inline", False),
                }
                for f in fields
            ]
        return embed

    def _build_room_embed(self, narrative: str, player_state: dict | None = None) -> dict:
        """Build an embed dict for a room description."""
        room_name = (player_state or {}).get("room_name", "Unknown Location")
        fields = []

        if player_state:
            hp = player_state.get("hp", "?")
            max_hp = player_state.get("max_hp", "?")
            level = player_state.get("level", "?")
            gold = player_state.get("gold", "?")
            fields.append({
                "name": "🧙 Player Status",
                "value": f"**HP:** {hp}/{max_hp}\n**Level:** {level}\n**Gold:** {gold}",
                "inline": True,
            })

            equipped = player_state.get("equipped", [])
            if equipped:
                fields.append({
                    "name": "⚔️ Equipped",
                    "value": "\n".join(equipped),
                    "inline": True,
                })

            inv_items = player_state.get("inventory_items", [])
            if inv_items:
                display = ", ".join(inv_items[:10])
                if len(inv_items) > 10:
                    display += f" (+{len(inv_items) - 10})"
                fields.append({
                    "name": "🎒 Inventory",
                    "value": display,
                    "inline": True,
                })

        return self._make_embed(
            title=f"📍 {room_name}",
            description=narrative,
            color=self._embed_color,
            fields=fields if fields else None,
        )

    def _build_combat_embed(self, narrative: str, player_state: dict | None = None) -> dict:
        """Build an embed for combat results."""
        lower = narrative.lower()
        is_death = player_state and player_state.get("hp", 1) <= 0
        is_level_up = "level up" in lower

        if is_level_up:
            color = EMBED_LEVEL_UP
        elif is_death:
            color = EMBED_DEATH
        elif "slain" in lower or "defeated" in lower:
            color = EMBED_SUCCESS
        else:
            color = EMBED_WARNING

        fields = []
        if player_state:
            fields.append({
                "name": "🩸 Your HP",
                "value": f"{player_state.get('hp', '?')}/{player_state.get('max_hp', '?')}",
                "inline": True,
            })

        return self._make_embed(
            title="⚔️ Combat",
            description=narrative,
            color=color,
            fields=fields if fields else None,
        )

    def _build_narrative_embed(self, narrative: str, title: str = "📖 Narrative", color: int | None = None) -> dict:
        """Build a generic narrative embed."""
        return self._make_embed(
            title=title,
            description=narrative,
            color=color or self._embed_color,
        )

    def _build_inventory_embed(self, narrative: str) -> dict:
        """Build an embed for inventory display."""
        return self._make_embed(
            title="🎒 Inventory",
            description=narrative,
            color=EMBED_INFO,
        )

    def _build_death_embed(self, narrative: str) -> dict:
        """Build an embed for player death."""
        return self._make_embed(
            title=f"{self._death_emoji} You Have Died",
            description=narrative,
            color=EMBED_DEATH,
        )

    def _build_quest_embed(self, narrative: str) -> dict:
        """Build an embed for quest updates."""
        return self._make_embed(
            title=f"{self._quest_emoji} Quest Update",
            description=narrative,
            color=EMBED_QUEST,
        )

    def _build_menu_embed(self, title: str, description: str) -> dict:
        """Build a menu embed."""
        return self._make_embed(
            title=title,
            description=description,
            color=self._embed_color,
        )

    # ------------------------------------------------------------------
    # Sending messages
    # ------------------------------------------------------------------

    async def _send_embed_to_user(self, user_id: int, result: CommandResult) -> None:
        """Send a formatted embed to a Discord user based on result content."""
        narrative = result.narrative or ""
        player_state = result.player_state or {}

        # Build embed dict (no discord dependency here)
        embed_dict = self._classify_and_build_embed(narrative, result, player_state)

        # Try to send via discord.py if available
        try:
            import discord
            channel = await self._get_channel_for_user(user_id)
            if channel is None:
                logger.warning("Cannot find channel for user %d", user_id)
                return

            try:
                embed = discord.Embed.from_dict(embed_dict)
            except Exception as e:
                logger.error("Failed to build embed: %s", e)
                embed = discord.Embed(
                    description=self._truncate(narrative, MAX_EMBED_DESCRIPTION),
                    color=self._embed_color,
                )

            message = await channel.send(embed=embed)

            # Add reaction quick-actions if enabled and game is active
            if self._reactions_enabled and not result.game_over:
                await self._add_reactions(message)

            # Store message reference
            ps = self._sessions.get(user_id)
            if ps and message:
                ps.current_message_id = message.id

        except ImportError:
            # Fallback: print to console
            logger.warning("discord not installed, printing to console")
            print(f"[Discord] {narrative}")
        except Exception as e:
            logger.error("Failed to send embed: %s", e)
            print(f"[Discord] {narrative}")

    def _classify_and_build_embed(
        self,
        narrative: str,
        result: CommandResult,
        player_state: dict,
    ) -> dict:
        """Classify the narrative and pick the appropriate embed builder."""
        lower = narrative.lower()

        # Death
        if result.death or "you have died" in lower or "you are dead" in lower:
            return self._build_death_embed(narrative)

        # Level up
        if "level up" in lower:
            return self._build_combat_embed(narrative, player_state)

        # Combat
        if any(kw in lower for kw in ("damage", "attack", "swing", "strike", "slain", "hit ", "miss")):
            return self._build_combat_embed(narrative, player_state)

        # Quest
        if any(kw in lower for kw in ("quest", "objective", "reward", "completed")):
            return self._build_quest_embed(narrative)

        # Inventory
        if "inventory" in lower or "you carry" in lower or "equipped" in lower:
            return self._build_inventory_embed(narrative)

        # Loot / item pickup
        if any(kw in lower for kw in ("picked up", "you find", "you found", "loot", "dropped", "gained")):
            return self._build_narrative_embed(narrative, f"{self._loot_emoji} Discovery", EMBED_LOOT)

        # NPC dialogue
        if "says" in lower or "replies" in lower or "answers" in lower:
            return self._build_narrative_embed(narrative, "💬 Dialogue", EMBED_INFO)

        # Default narrative
        return self._build_narrative_embed(narrative)

    async def _add_reactions(self, message) -> None:
        """Add direction and action reaction emoji to a message."""
        try:
            import discord
        except ImportError:
            return

        for emoji in ("⬆️", "➡️", "⬇️", "⬅️", "🔍", "🎒", "⚔️"):
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                break

    async def _send_new_game_menu(self, channel, author):
        """Send the new game / load game menu to a user."""
        try:
            import discord
        except ImportError:
            return

        embed = discord.Embed(
            title=f"🏰 Welcome to {self._bot_name}!",
            description=(
                "An AI-generated dungeon crawl adventure.\n\n"
                "Type **new** to start a new game.\n"
                "Type **load** to load a saved game.\n"
                "Type **help** for command reference."
            ),
            color=self._embed_color,
        )
        embed.set_footer(text="This game uses an AI to generate the world in real-time.")

        await channel.send(embed=embed)

        # Create a placeholder session for menu flow
        self._sessions[author.id] = _PlayerSession(session=None)

    async def _get_channel_for_user(self, user_id: int):
        """Get a DM channel for the given user."""
        if self._bot is None:
            return None
        try:
            user = await self._bot.fetch_user(user_id)
            return await user.create_dm()
        except Exception as e:
            logger.error("Failed to get channel for user %d: %s", user_id, e)
            return None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text to max length, adding '...' if needed."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    # ------------------------------------------------------------------
    # Convenience methods for the game loop
    # ------------------------------------------------------------------

    def get_session(self, user_id: int) -> _PlayerSession | None:
        """Get the player session for a Discord user."""
        return self._sessions.get(user_id)

    def create_session(self, user_id: int, game_session: Any, player_name: str = "") -> _PlayerSession:
        """Create a new player session."""
        ps = _PlayerSession(session=game_session, player_name=player_name, game_active=True)
        self._sessions[user_id] = ps
        return ps

    def remove_session(self, user_id: int) -> None:
        """Remove a player session (game over / quit)."""
        self._sessions.pop(user_id, None)

    async def show_room(self, user_id: int, room_description: str, player_state: dict | None = None) -> None:
        """Show a room description to a player."""
        result = CommandResult(
            session_id=f"discord:{user_id}",
            narrative=room_description,
            player_state=player_state or {},
        )
        self._current_user_id = user_id
        await self._send_embed_to_user(user_id, result)