"""Protocol types for client ↔ controller communication."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CommandRequest:
    session_id: str
    input_text: str


@dataclass
class CommandResult:
    session_id: str
    turn: int = 0
    narrative: str = ""
    room_description: str = ""
    player_state: dict = field(default_factory=dict)
    entities_visible: list[dict] = field(default_factory=list)
    items_visible: list[dict] = field(default_factory=list)
    new_quests: list[dict] = field(default_factory=list)
    game_over: bool = False
    death: bool | None = None