"""Configuration loader — YAML → Pydantic dataclasses."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nested config sections
# ---------------------------------------------------------------------------

class LLMConfig(BaseModel):
    """LLM backend configuration."""

    provider: str = "openai"  # openai | ollama | custom
    endpoint: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    temperature: float = 0.9
    max_tokens: int = 1024
    supports_tool_calling: bool = True

    # Optional lighter model for simple tasks (item names, short descriptions)
    light_model: dict[str, Any] | None = None


class PersistenceConfig(BaseModel):
    """Persistence / save configuration."""

    provider: str = "json"  # json | sqlite | memory | cloud
    path: str = "saves"


class ClientConfig(BaseModel):
    """Client configuration."""

    type: str = "console"  # console | websocket | discord
    prompt: str = ":> "
    show_room_on_entry: bool = True


class DiscordConfig(BaseModel):
    """Discord bot configuration."""

    token: str | None = None
    bot_name: str = "AIVentureBot"
    embed_color: int = 0x4a3728  # warm brown, dungeon feel
    reactions: bool = True  # add reaction quick-actions to messages
    reactions_timeout: int = 300  # seconds before reaction listeners expire
    allow_dms_only: bool = True  # restrict gameplay to DMs
    generate_indicator: str = "⏳"  # emoji shown while LLM generates
    death_emoji: str = "💀"
    level_up_emoji: str = "⬆️"
    quest_emoji: str = "📜"
    loot_emoji: str = "✨"


class GameConfig(BaseModel):
    """Top-level game configuration."""

    title: str = "AIVenture"
    max_context_turns: int = Field(15, description="Turns of history to send to the LLM")
    auto_save_interval: int = Field(10, description="Turns between auto-saves")
    death_retains_xp: bool = True
    death_gold_loss_pct: float = Field(0.1, description="Fraction of gold lost on death (0.0-1.0)")
    death_item_loss: bool = Field(False, description="Whether items can be lost on death")
    death_item_loss_pct: float = Field(0.2, description="Fraction of items lost on death (0.0-1.0)")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    client: ClientConfig = Field(default_factory=ClientConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_NAME = "config.yaml"


def load_config(path: str | None = None) -> GameConfig:
    """Load configuration from a YAML file, falling back to defaults.

    Args:
        path: Optional path to a config file.  If *None*, looks for
              ``config.yaml`` in the current working directory.

    Returns:
        A fully-populated :class:`GameConfig`.
    """
    if path is None:
        path = _DEFAULT_CONFIG_NAME

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}
        return _build_from_dict(data)

    # No file found — return pure defaults
    return GameConfig()


def _build_from_dict(data: dict[str, Any]) -> GameConfig:
    """Merge a (partial) dict into the pydantic model with defaults."""
    # Recursively nest the known sub-sections
    llm_data = data.pop("llm", {})
    if isinstance(llm_data, dict):
        llm_data = _apply_env_overrides(llm_data)
    llm_config = LLMConfig(**llm_data)

    persist_data = data.pop("persistence", {})
    if isinstance(persist_data, dict):
        persist_data = _apply_env_overrides(persist_data)
    persist_config = PersistenceConfig(**persist_data)

    client_data = data.pop("client", {})
    if isinstance(client_data, dict):
        client_data = _apply_env_overrides(client_data)
    client_config = ClientConfig(**client_data)

    discord_data = data.pop("discord", {})
    if isinstance(discord_data, dict):
        discord_data = _apply_env_overrides(discord_data)
    discord_config = DiscordConfig(**discord_data)

    data = _apply_env_overrides(data)
    return GameConfig(
        llm=llm_config,
        persistence=persist_config,
        client=client_config,
        discord=discord_config,
        **data,
    )


def _apply_env_overrides(d: dict[str, Any]) -> dict[str, Any]:
    """Replace ``${ENV_VAR}`` placeholders with actual env values."""
    out: dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_name = value[2:-1]
            out[key] = os.environ.get(env_name, value)
        else:
            out[key] = value
    return out