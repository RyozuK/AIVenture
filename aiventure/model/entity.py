"""Entities (mobs, NPCs, monsters) and the Player."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from .coords import Position
from .item import Inventory


class EntityType(Enum):
    MONSTER = "monster"
    NPC = "npc"
    PLAYER = "player"
    BOSS = "boss"


@dataclass
class Entity:
    """A creature or character in the world."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unknown Entity"
    description: str = ""
    entity_type: EntityType = EntityType.MONSTER
    room_id: str | None = None
    hp: int = 10
    max_hp: int = 10
    attack: int = 1
    defense: int = 1
    inventory: Inventory = field(default_factory=Inventory)
    personality: str = ""
    is_hostile: bool = False
    is_alive: bool = True
    ai_behavior: str = "wander"  # patrol, guard, wander, follow
    position: Position | None = None

    # -- helpers -- #

    def take_damage(self, amount: int) -> int:
        """Apply damage.  Returns actual damage dealt (after defense)."""
        actual = max(1, amount - self.defense)
        self.hp = max(0, self.hp - actual)
        if self.hp <= 0:
            self.is_alive = False
        return actual

    def heal(self, amount: int) -> int:
        """Restore HP.  Returns actual HP gained."""
        old = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old

    def to_dict(self) -> dict:
        from .coords import Position
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "entity_type": self.entity_type.value,
            "room_id": self.room_id,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "attack": self.attack,
            "defense": self.defense,
            "inventory": self.inventory.to_dict(),
            "personality": self.personality,
            "is_hostile": self.is_hostile,
            "is_alive": self.is_alive,
            "ai_behavior": self.ai_behavior,
        }


@dataclass
class Player(Entity):
    """The player character — extends Entity with RPG stats."""

    gold: int = 0
    xp: int = 0
    level: int = 1
    active_quests: list[str] = field(default_factory=list)   # quest UUIDs
    completed_quests: list[str] = field(default_factory=list)
    death_count: int = 0

    # -- factories -- #

    @classmethod
    def create_default(cls, name: str, position: Position) -> Player:
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            description=f"A brave adventurer named {name}.",
            entity_type=EntityType.PLAYER,
            position=position,
            hp=20,
            max_hp=20,
            attack=3,
            defense=2,
            inventory=Inventory(),
            is_hostile=False,
            is_alive=True,
        )

    # -- leveling -- #

    def gain_xp(self, amount: int) -> bool:
        """Gain XP.  Returns True if the player leveled up."""
        self.xp += amount
        xp_threshold = self.level * 50
        if self.xp >= xp_threshold:
            self.xp -= xp_threshold
            self.level += 1
            self.max_hp += 5
            self.hp = self.max_hp
            self.attack += 1
            self.defense += 1
            return True
        return False