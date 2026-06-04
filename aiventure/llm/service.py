"""LLM Service — orchestrates LLM calls with tool schemas."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .adapter import LLMAdapter, LLMResponse, ToolSchema
from .tools import TOOLS_BY_NAME

logger = logging.getLogger("aiventure.llm.service")


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

@dataclass
class RoomData:
    """Structured room data returned by the LLM."""
    name: str = ""
    description: str = ""
    exits: list[str] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    features: list[str] = field(default_factory=list)


@dataclass
class ActionOutcomeData:
    """Structured action outcome returned by the LLM."""
    success: bool = False
    narrative: str = ""
    discovered_items: list[dict] = field(default_factory=list)
    discovered_entities: list[dict] = field(default_factory=list)
    new_exits: list[str] = field(default_factory=list)


@dataclass
class CombatOutcomeData:
    """Structured combat outcome returned by the LLM."""
    narrative: str = ""
    player_damage_dealt: int = 0
    enemy_damage_dealt: int = 0
    player_alive: bool = True
    enemy_alive: bool = True
    loot_dropped: list[dict] = field(default_factory=list)


@dataclass
class ItemUseOutcomeData:
    """Structured item-use outcome returned by the LLM."""
    narrative: str = ""
    effects: list[str] = field(default_factory=list)
    charges_consumed: int = 1
    new_items: list[dict] = field(default_factory=list)
    hp_change: int = 0


@dataclass
class NPCDialogueData:
    """Structured NPC dialogue returned by the LLM."""
    npc_name: str = ""
    dialogue: str = ""
    mood: str = ""
    quest_offered: dict | None = None
    items_traded: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class LLMService:
    """Wraps an LLMAdapter and provides game-specific high-level calls."""

    def __init__(
        self,
        adapter: LLMAdapter,
        max_retries: int = 2,
    ) -> None:
        self._adapter = adapter
        self._max_retries = max_retries

    # -- public API -- #

    async def generate_room(
        self,
        system_prompt: str,
        user_messages: list[str],
    ) -> RoomData:
        tool = TOOLS_BY_NAME["generate_room"]
        return await self._call_with_tool(tool, system_prompt, user_messages)

    async def describe_action_outcome(
        self,
        system_prompt: str,
        user_messages: list[str],
    ) -> ActionOutcomeData:
        tool = TOOLS_BY_NAME["describe_action_outcome"]
        return await self._call_with_tool(tool, system_prompt, user_messages)

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 256,
    ) -> str:
        return await self._adapter.generate_text(prompt, max_tokens=max_tokens)

    async def describe_combat_outcome(
        self,
        system_prompt: str,
        user_messages: list[str],
    ) -> CombatOutcomeData:
        tool = TOOLS_BY_NAME["describe_combat_outcome"]
        return await self._call_with_tool(tool, system_prompt, user_messages)  # type: ignore[return-value]

    async def describe_item_use(
        self,
        system_prompt: str,
        user_messages: list[str],
    ) -> ItemUseOutcomeData:
        tool = TOOLS_BY_NAME["describe_item_use"]
        return await self._call_with_tool(tool, system_prompt, user_messages)  # type: ignore[return-value]

    async def generate_npc_dialogue(
        self,
        system_prompt: str,
        user_messages: list[str],
    ) -> NPCDialogueData:
        tool = TOOLS_BY_NAME["generate_npc_dialogue"]
        return await self._call_with_tool(tool, system_prompt, user_messages)  # type: ignore[return-value]

    # -- internal -- #

    async def _call_with_tool(
        self,
        tool: ToolSchema,
        system_prompt: str,
        user_messages: list[str],
    ) -> RoomData | ActionOutcomeData | CombatOutcomeData | ItemUseOutcomeData | NPCDialogueData:
        """Call the LLM with a single tool, retrying on failure."""
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._adapter.chat(
                    system_prompt=system_prompt,
                    user_messages=list(user_messages),
                    tools=[tool],
                )
                return self._parse_tool_response(resp, tool)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM call attempt %d/%d failed: %s",
                    attempt, self._max_retries, exc,
                )

        # All retries exhausted — return empty result with error narrative
        logger.error("LLM call failed after %d retries: %s", self._max_retries, last_error)
        if tool.get("function", {}).get("name") == "generate_room":
            return RoomData(
                name="Unknown Room",
                description="The room could not be generated. Something went wrong.",
            )
        return ActionOutcomeData(
            success=False,
            narrative="The action could not be resolved. Something went wrong.",
        )

    def _parse_tool_response(
        self,
        resp: LLMResponse,
        tool: ToolSchema,
    ) -> RoomData | ActionOutcomeData | CombatOutcomeData | ItemUseOutcomeData | NPCDialogueData:
        tool_name = tool["function"]["name"]

        if resp.tool_calls:
            call = resp.tool_calls[0]
            if call.name == tool_name:
                return self._build_result(call.arguments, tool_name)

        # Fallback: try parsing text as JSON
        if resp.text:
            try:
                data = json.loads(resp.text)
                return self._build_result(data, tool_name)
            except json.JSONDecodeError:
                pass

        # Last resort: construct minimal result from text
        if tool_name == "generate_room":
            return RoomData(name="Unnamed Room", description=resp.text or "An empty room.")
        return ActionOutcomeData(success=False, narrative=resp.text or "Nothing happened.")

    @staticmethod
    def _build_result(args: dict, tool_name: str) -> RoomData | ActionOutcomeData | CombatOutcomeData | ItemUseOutcomeData | NPCDialogueData:
        if tool_name == "generate_room":
            pos = args.get("position", {})
            return RoomData(
                name=args.get("name", "Unknown"),
                description=args.get("description", ""),
                exits=args.get("exits", []),
                items=args.get("items", []),
                entities=args.get("entities", []),
                features=args.get("features", []),
            )
        elif tool_name == "describe_action_outcome":
            return ActionOutcomeData(
                success=args.get("success", False),
                narrative=args.get("narrative", ""),
                discovered_items=args.get("discovered_items", []),
                discovered_entities=args.get("discovered_entities", []),
                new_exits=args.get("new_exits", []),
            )
        elif tool_name == "describe_combat_outcome":
            return CombatOutcomeData(
                narrative=args.get("narrative", ""),
                player_damage_dealt=args.get("attacker_damage_dealt", 0),
                enemy_damage_dealt=args.get("defender_damage_dealt", 0),
                player_alive=args.get("attacker_alive", True),
                enemy_alive=args.get("defender_alive", True),
                loot_dropped=args.get("loot_dropped", []),
            )
        elif tool_name == "describe_item_use":
            return ItemUseOutcomeData(
                narrative=args.get("narrative", ""),
                effects=args.get("effects", []),
                charges_consumed=args.get("charges_consumed", 1),
                new_items=args.get("new_items", []),
            )
        elif tool_name == "generate_npc_dialogue":
            return NPCDialogueData(
                npc_name=args.get("npc_name", "NPC"),
                dialogue=args.get("dialogue", ""),
                mood=args.get("mood", "neutral"),
                quest_offered=args.get("quest_offered"),
                items_traded=args.get("items_traded", []),
            )
        return ActionOutcomeData(narrative=str(args))