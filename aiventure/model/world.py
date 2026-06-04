"""World, Room, and serialization helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .coords import Direction, Position


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------

@dataclass
class Room:
    """A single room in the dungeon."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position: Position | None = None
    name: str = "Unknown Room"
    description: str = ""
    exits: dict[Direction, Position] = field(default_factory=dict)
    ambient_details: list[str] = field(default_factory=list)
    connected_entities: list[str] = field(default_factory=list)  # UUIDs
    connected_items: list[str] = field(default_factory=list)      # UUIDs
    features: list[str] = field(default_factory=list)
    visited_count: int = 0

    # -- factories -- #

    @classmethod
    def create_empty(cls, position: Position, name: str, description: str = "") -> Room:
        return cls(
            position=position,
            name=name,
            description=description or f"A plain room called {name}.",
        )

    # -- serialization -- #

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position": self.position.to_dict() if self.position else None,
            "name": self.name,
            "description": self.description,
            "exits": {d.value: p.to_dict() for d, p in self.exits.items()},
            "ambient_details": self.ambient_details,
            "connected_entities": self.connected_entities,
            "connected_items": self.connected_items,
            "features": self.features,
            "visited_count": self.visited_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Room:
        exits = {}
        for d_value, pos_dict in data.get("exits", {}).items():
            d = Direction(d_value)
            exits[d] = Position.from_dict(pos_dict)
        pos = Position.from_dict(data["position"]) if data.get("position") else None
        return cls(
            id=data["id"],
            position=pos,
            name=data.get("name", "Unknown"),
            description=data.get("description", ""),
            exits=exits,
            ambient_details=data.get("ambient_details", []),
            connected_entities=data.get("connected_entities", []),
            connected_items=data.get("connected_items", []),
            features=data.get("features", []),
            visited_count=data.get("visited_count", 0),
        )


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

@dataclass
class World:
    """The single source of truth for game state."""

    # Entity containers
    rooms: dict[Position, Room] = field(default_factory=dict)
    entities: dict[str, object] = field(default_factory=dict)   # UUID → Entity
    items: dict[str, object] = field(default_factory=dict)       # UUID → Item
    quests: dict[str, object] = field(default_factory=dict)      # UUID → Quest

    # Player (set during session init)
    player: object | None = None

    # Exploration tracking
    explored_positions: set[Position] = field(default_factory=set)
    generated_positions: set[Position] = field(default_factory=set)

    # Meta
    turn_count: int = 0
    world_seed: str = ""
    world_description: str = ""

    # -- lookups -- #

    def get_room(self, pos: Position) -> Room | None:
        return self.rooms.get(pos)

    def get_entity(self, entity_id: str):
        return self.entities.get(entity_id)

    def get_item(self, item_id: str):
        return self.items.get(item_id)

    def add_room(self, room: Room) -> None:
        if room.position:
            self.rooms[room.position] = room
            self.generated_positions.add(room.position)

    def remove_entity(self, entity_id: str) -> None:
        self.entities.pop(entity_id, None)

    def move_player(self, direction: Direction) -> bool:
        """Move the player one step.  Returns True if successful."""
        from .entity import Player
        player = self.player
        if not player or not isinstance(player, Player):
            return False
        current_pos = player.position
        if current_pos is None:
            return False
        target = direction.apply_to(current_pos)
        if target not in self.rooms:
            return False
        player.position = target
        self.explored_positions.add(target)
        room = self.rooms[target]
        room.visited_count += 1
        return True

    # -- serialization -- #

    def to_dict(self) -> dict:
        return {
            "rooms": {
                _pos_key(p): room.to_dict()
                for p, room in self.rooms.items()
            },
            "entities": {
                uid: _entity_to_dict(e)
                for uid, e in self.entities.items()
            },
            "items": {
                uid: _item_to_dict(i)
                for uid, i in self.items.items()
            },
            "quests": {
                uid: _quest_to_dict(q)
                for uid, q in self.quests.items()
            },
            "player": _entity_to_dict(self.player) if self.player else None,
            "explored_positions": [_pos_key(p) for p in self.explored_positions],
            "generated_positions": [_pos_key(p) for p in self.generated_positions],
            "turn_count": self.turn_count,
            "world_seed": self.world_seed,
            "world_description": self.world_description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> World:
        rooms = {}
        for pos_key, room_data in data.get("rooms", {}).items():
            pos = _pos_from_key(pos_key)
            rooms[pos] = Room.from_dict(room_data)

        world = cls(
            rooms=rooms,
            entities={uid: _entity_from_dict(e) for uid, e in data.get("entities", {}).items()},
            items={uid: _item_from_dict(i) for uid, i in data.get("items", {}).items()},
            quests={uid: _quest_from_dict(q) for uid, q in data.get("quests", {}).items()},
            player=_entity_from_dict(data["player"]) if data.get("player") else None,
            explored_positions={_pos_from_key(k) for k in data.get("explored_positions", [])},
            generated_positions={_pos_from_key(k) for k in data.get("generated_positions", [])},
            turn_count=data.get("turn_count", 0),
            world_seed=data.get("world_seed", ""),
            world_description=data.get("world_description", ""),
        )
        # Re-link player inventory references
        if world.player:
            _relink_player(world.player, world.items)
        return world


# ---------------------------------------------------------------------------
# Serialization helpers (cross-cutting with entity/item/quest)
# ---------------------------------------------------------------------------

def _pos_key(p: Position) -> str:
    return f"{p.x},{p.y},{p.z}"


def _pos_from_key(key: str) -> Position:
    x, y, z = key.split(",")
    return Position(int(x), int(y), int(z))


def _entity_to_dict(e) -> dict:
    """Serialize an Entity or Player."""
    from .entity import Player, EntityType
    d = e.to_dict()
    if isinstance(e, Player):
        d["gold"] = e.gold
        d["xp"] = e.xp
        d["level"] = e.level
        d["active_quests"] = e.active_quests
        d["completed_quests"] = e.completed_quests
        d["death_count"] = e.death_count
        d["_is_player"] = True
        if e.position is not None:
            d["position"] = _pos_key(e.position)
    return d


def _entity_from_dict(d: dict):
    from .entity import Entity, Player, EntityType
    from .item import Inventory
    is_player = d.pop("_is_player", False)
    pos_raw = d.pop("position", None)
    pos = _pos_from_key(pos_raw) if pos_raw else None
    inv_data = d.pop("inventory", {})
    inventory = Inventory.from_dict(inv_data)  # item references filled later
    kwargs = {
        "entity_type": EntityType(d["entity_type"]),
        "room_id": d.get("room_id"),
        "hp": d.get("hp", 10),
        "max_hp": d.get("max_hp", 10),
        "attack": d.get("attack", 1),
        "defense": d.get("defense", 1),
        "inventory": inventory,
        "personality": d.get("personality", ""),
        "is_hostile": d.get("is_hostile", False),
        "is_alive": d.get("is_alive", True),
        "ai_behavior": d.get("ai_behavior", "wander"),
        "position": pos,
        **{k: v for k, v in d.items() if k not in ("gold", "xp", "level", "active_quests", "completed_quests", "death_count", "_is_player", "position", "inventory")},
    }
    if is_player:
        return Player(
            gold=d.get("gold", 0),
            xp=d.get("xp", 0),
            level=d.get("level", 1),
            active_quests=d.get("active_quests", []),
            completed_quests=d.get("completed_quests", []),
            death_count=d.get("death_count", 0),
            **kwargs,
        )
    return Entity(**kwargs)


def _relink_player(player, items_dict):
    """After deserialization, point inventory UUIDs back to real Item objects."""
    for item_id in player.inventory.owned_items:
        if item_id in items_dict:
            player.inventory.owned_items[item_id] = items_dict[item_id]
    for slot, item_id in player.inventory.equipped.items():
        if item_id in items_dict:
            player.inventory.equipped[slot] = items_dict[item_id]


def _item_to_dict(i) -> dict:
    from .item import ItemType, EquipSlot
    return {
        "id": i.id,
        "name": i.name,
        "description": i.description,
        "item_type": i.item_type.value if isinstance(i.item_type, ItemType) else i.item_type,
        "stat_value": i.stat_value,
        "charges": i.charges,
        "is_equippable": i.is_equippable,
        "equip_slot": i.equip_slot.value if isinstance(i.equip_slot, EquipSlot) else (i.equip_slot or "NONE"),
        "is_key": i.is_key,
        "key_target": i.key_target,
        "is_quest_item": i.is_quest_item,
        "quest_id": i.quest_id,
    }


def _item_from_dict(d: dict):
    from .item import Item, ItemType, EquipSlot
    return Item(
        id=d["id"],
        name=d.get("name", "Unknown"),
        description=d.get("description", ""),
        item_type=ItemType(d["item_type"]),
        stat_value=d.get("stat_value", 0),
        charges=d.get("charges", -1),
        is_equippable=d.get("is_equippable", False),
        equip_slot=EquipSlot(d.get("equip_slot", "NONE")),
        is_key=d.get("is_key", False),
        key_target=d.get("key_target"),
        is_quest_item=d.get("is_quest_item", False),
        quest_id=d.get("quest_id"),
    )


def _quest_to_dict(q) -> dict:
    from .quest import QuestStatus
    return {
        "id": q.id,
        "title": q.title,
        "description": q.description,
        "giver_entity_id": q.giver_entity_id,
        "status": q.status.value if isinstance(q.status, QuestStatus) else q.status,
        "objectives": [obj.to_dict() for obj in q.objectives],
        "rewards": [rew.to_dict() for rew in q.rewards],
    }


def _quest_from_dict(d: dict):
    from .quest import Quest, QuestStatus, Objective, Reward
    return Quest(
        id=d["id"],
        title=d.get("title", "Untitled Quest"),
        description=d.get("description", ""),
        giver_entity_id=d.get("giver_entity_id"),
        status=QuestStatus(d["status"]),
        objectives=[Objective.from_dict(o) for o in d.get("objectives", [])],
        rewards=[Reward.from_dict(r) for r in d.get("rewards", [])],
    )