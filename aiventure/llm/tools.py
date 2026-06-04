"""Tool schema definitions for LLM structured calls."""

from __future__ import annotations

from typing import Any

from .adapter import ToolSchema

# ---------------------------------------------------------------------------
# Shared sub-schemas (referenced by multiple tools)
# ---------------------------------------------------------------------------

_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "item_type": {
            "type": "string",
            "enum": ["weapon", "armor", "potion", "key", "treasure", "quest_item", "consumable"],
        },
        "stat_value": {"type": "integer"},
        "charges": {"type": "integer"},
        "is_equippable": {"type": "boolean"},
        "equip_slot": {
            "type": "string",
            "enum": ["hand", "off_hand", "head", "chest", "legs", "feet", "accessory", "none"],
        },
    },
    "required": ["name"],
}

_ENTITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "entity_type": {
            "type": "string",
            "enum": ["monster", "npc", "boss"],
        },
        "hp": {"type": "integer"},
        "max_hp": {"type": "integer"},
        "attack": {"type": "integer"},
        "defense": {"type": "integer"},
        "personality": {"type": "string"},
        "is_hostile": {"type": "boolean"},
        "ai_behavior": {
            "type": "string",
            "enum": ["patrol", "guard", "wander", "follow"],
        },
    },
    "required": ["name"],
}

_DIRECTION_ENUM = [
    "north", "south", "east", "west", "up", "down",
]

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOL_generate_room: ToolSchema = {
    "type": "function",
    "function": {
        "name": "generate_room",
        "description": "Generate a new room adjacent to an existing position.",
        "parameters": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "z": {"type": "integer"},
                    },
                    "required": ["x", "y", "z"],
                },
                "name": {"type": "string"},
                "description": {"type": "string"},
                "exits": {
                    "type": "array",
                    "items": {"type": "string", "enum": _DIRECTION_ENUM},
                },
                "items": {"type": "array", "items": _ITEM_SCHEMA},
                "entities": {"type": "array", "items": _ENTITY_SCHEMA},
                "features": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["position", "name", "description"],
        },
    },
}

TOOL_describe_combat_outcome: ToolSchema = {
    "type": "function",
    "function": {
        "name": "describe_combat_outcome",
        "description": "Determine the outcome of a combat exchange.",
        "parameters": {
            "type": "object",
            "properties": {
                "attacker": {"type": "string"},
                "defender": {"type": "string"},
                "attacker_stats": {"type": "object"},
                "defender_stats": {"type": "object"},
                "narrative": {"type": "string"},
                "attacker_damage_dealt": {"type": "integer"},
                "defender_damage_dealt": {"type": "integer"},
                "attacker_alive": {"type": "boolean"},
                "defender_alive": {"type": "boolean"},
                "loot_dropped": {"type": "array", "items": _ITEM_SCHEMA},
            },
            "required": ["attacker", "defender", "narrative",
                         "attacker_damage_dealt", "defender_damage_dealt",
                         "attacker_alive", "defender_alive"],
        },
    },
}

TOOL_describe_item_use: ToolSchema = {
    "type": "function",
    "function": {
        "name": "describe_item_use",
        "description": "Determine what happens when an item is used.",
        "parameters": {
            "type": "object",
            "properties": {
                "narrative": {"type": "string"},
                "effects": {"type": "array", "items": {"type": "string"}},
                "charges_consumed": {"type": "integer"},
                "new_items": {"type": "array", "items": _ITEM_SCHEMA},
            },
            "required": ["narrative"],
        },
    },
}

TOOL_generate_npc_dialogue: ToolSchema = {
    "type": "function",
    "function": {
        "name": "generate_npc_dialogue",
        "description": "Generate a response from an NPC.",
        "parameters": {
            "type": "object",
            "properties": {
                "npc_name": {"type": "string"},
                "dialogue": {"type": "string"},
                "mood": {"type": "string"},
                "quest_offered": {"type": "object", "nullable": True},
                "items_traded": {"type": "array", "nullable": True},
            },
            "required": ["npc_name", "dialogue"],
        },
    },
}

TOOL_describe_action_outcome: ToolSchema = {
    "type": "function",
    "function": {
        "name": "describe_action_outcome",
        "description": "Determine the outcome of a player action (searching, opening, or any freeform action).",
        "parameters": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "narrative": {"type": "string"},
                "discovered_items": {"type": "array", "items": _ITEM_SCHEMA},
                "discovered_entities": {"type": "array", "items": _ENTITY_SCHEMA},
                "new_exits": {"type": "array", "items": {"type": "string", "enum": _DIRECTION_ENUM}},
            },
            "required": ["success", "narrative"],
        },
    },
}

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TOOLS: list[ToolSchema] = [
    TOOL_generate_room,
    TOOL_describe_combat_outcome,
    TOOL_describe_item_use,
    TOOL_generate_npc_dialogue,
    TOOL_describe_action_outcome,
]

TOOLS_BY_NAME: dict[str, ToolSchema] = {
    t["function"]["name"]: t for t in ALL_TOOLS
}