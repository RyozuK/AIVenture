"""Quests, objectives, and rewards."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class QuestStatus(Enum):
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class Objective:
    """A single goal within a quest."""

    type: str = "explore"  # kill | collect | deliver | explore | talk
    target: str = ""       # entity name, item name, room description, etc.
    required_count: int = 1
    current_count: int = 0

    @property
    def is_complete(self) -> bool:
        return self.current_count >= self.required_count

    def advance(self, amount: int = 1) -> None:
        self.current_count = min(self.current_count + amount, self.required_count)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "target": self.target,
            "required_count": self.required_count,
            "current_count": self.current_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Objective:
        return cls(
            type=data.get("type", "explore"),
            target=data.get("target", ""),
            required_count=data.get("required_count", 1),
            current_count=data.get("current_count", 0),
        )


@dataclass
class Reward:
    """A reward granted on quest completion."""

    type: str = "xp"       # item | xp | gold
    value: dict = field(default_factory=dict)
    # value keys depend on type:
    #   xp     → {"amount": int}
    #   gold   → {"amount": int}
    #   item   → {"item_type": str, "name": str, "stat_value": int, ...}

    def to_dict(self) -> dict:
        return {"type": self.type, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict) -> Reward:
        return cls(type=data.get("type", "xp"), value=data.get("value", {}))


@dataclass
class Quest:
    """A quest given by an NPC or discovered in the world."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Quest"
    description: str = ""
    giver_entity_id: str | None = None
    status: QuestStatus = QuestStatus.AVAILABLE
    objectives: list[Objective] = field(default_factory=list)
    rewards: list[Reward] = field(default_factory=list)

    # -- state helpers -- #

    @property
    def all_objectives_complete(self) -> bool:
        if not self.objectives:
            return False
        return all(obj.is_complete for obj in self.objectives)

    def advance(self, obj_type: str, target: str = "", amount: int = 1) -> bool:
        """Increment matching objectives.  Returns True if this quest is now complete."""
        for obj in self.objectives:
            if obj.type == obj_type and (not target or target.lower() in obj.target.lower()):
                obj.advance(amount)
        if self.all_objectives_complete:
            self.status = QuestStatus.COMPLETE
            return True
        return False

    def activate(self) -> None:
        self.status = QuestStatus.ACTIVE

    def fail(self) -> None:
        self.status = QuestStatus.FAILED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "giver_entity_id": self.giver_entity_id,
            "status": self.status.value,
            "objectives": [obj.to_dict() for obj in self.objectives],
            "rewards": [rew.to_dict() for rew in self.rewards],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Quest:
        return cls(
            id=data["id"],
            title=data.get("title", "Untitled Quest"),
            description=data.get("description", ""),
            giver_entity_id=data.get("giver_entity_id"),
            status=QuestStatus(data["status"]),
            objectives=[Objective.from_dict(o) for o in data.get("objectives", [])],
            rewards=[Reward.from_dict(r) for r in data.get("rewards", [])],
        )