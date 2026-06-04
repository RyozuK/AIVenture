"""Items, Inventory, and related enums."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    POTION = "potion"
    KEY = "key"
    TREASURE = "treasure"
    QUEST_ITEM = "quest_item"
    CONSUMABLE = "consumable"


class EquipSlot(Enum):
    HAND = "hand"
    OFF_HAND = "off_hand"
    HEAD = "head"
    CHEST = "chest"
    LEGS = "legs"
    FEET = "feet"
    ACCESSORY = "accessory"
    NONE = "none"


# Slot → valid item types mapping
VALID_SLOT_TYPES: dict[EquipSlot, set[ItemType]] = {
    EquipSlot.HAND: {ItemType.WEAPON},
    EquipSlot.OFF_HAND: {ItemType.WEAPON},
    EquipSlot.HEAD: {ItemType.ARMOR},
    EquipSlot.CHEST: {ItemType.ARMOR},
    EquipSlot.LEGS: {ItemType.ARMOR},
    EquipSlot.FEET: {ItemType.ARMOR},
    EquipSlot.ACCESSORY: {ItemType.TREASURE, ItemType.QUEST_ITEM},
}


@dataclass
class Item:
    """A single item that can be held, equipped, or found."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unknown Item"
    description: str = ""
    item_type: ItemType = ItemType.TREASURE
    stat_value: int = 0           # Attack bonus, defense bonus, heal amount, etc.
    charges: int = -1             # -1 = unlimited
    is_equippable: bool = False
    equip_slot: EquipSlot = EquipSlot.NONE
    is_key: bool = False
    key_target: str | None = None  # UUID of a room or entity this key opens
    is_quest_item: bool = False
    quest_id: str | None = None


@dataclass
class Inventory:
    """Container for items carried by a player or entity."""

    owned_items: dict[str, Item | None] = field(default_factory=dict)  # UUID → Item (None after drop)
    equipped: dict[EquipSlot, str] = field(default_factory=dict)       # slot → item UUID
    max_weight: int = 100
    current_weight: int = 0

    # -- operations -- #

    def add(self, item: Item) -> bool:
        """Add an item.  Returns False if at weight capacity."""
        if item.item_type == ItemType.TREASURE or item.item_type == ItemType.QUEST_ITEM:
            weight = 0  # Treasures and quest items are weightless
        else:
            weight = 1  # Simplified: 1 unit per item
        if self.current_weight + weight > self.max_weight:
            return False
        self.owned_items[item.id] = item
        self.current_weight += weight
        return True

    def remove(self, item_id: str) -> Item | None:
        """Remove an item by ID.  Auto-unequips if equipped."""
        # Unequip first if active
        for slot, uid in list(self.equipped.items()):
            if uid == item_id:
                del self.equipped[slot]
        item = self.owned_items.pop(item_id, None)
        if item:
            self.current_weight = max(0, self.current_weight - 1)
        return item

    def equip(self, item_id: str) -> bool:
        """Equip an item into its designated slot."""
        item = self.owned_items.get(item_id)
        if not item or not item.is_equippable or item.equip_slot == EquipSlot.NONE:
            return False
        slot = item.equip_slot
        # Unequip current occupant of that slot
        if slot in self.equipped:
            old_id = self.equipped[slot]
            if old_id != item_id:
                self.equipped[slot] = item_id
            else:
                return True
        else:
            self.equipped[slot] = item_id
        return True

    def unequip(self, slot: EquipSlot) -> bool:
        """Remove the item from *slot*."""
        if slot in self.equipped:
            del self.equipped[slot]
            return True
        return False

    def find(self, name_pattern: str) -> list[Item]:
        """Return items whose names contain *name_pattern* (case-insensitive)."""
        pattern = name_pattern.lower()
        return [
            item for item in self.owned_items.values()
            if item and pattern in item.name.lower()
        ]

    def get_equipped(self, slot: EquipSlot) -> Item | None:
        """Return the item equipped in *slot*, or None."""
        item_id = self.equipped.get(slot)
        if item_id:
            return self.owned_items.get(item_id)
        return None

    # -- serialization -- #

    def to_dict(self) -> dict:
        return {
            "owned_items": list(self.owned_items.keys()),  # just UUIDs; real objects filled later
            "equipped": {slot.value: uid for slot, uid in self.equipped.items()},
            "max_weight": self.max_weight,
            "current_weight": self.current_weight,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Inventory:
        owned = {uid: None for uid in data.get("owned_items", [])}
        equipped = {}
        for slot_value, uid in data.get("equipped", {}).items():
            equipped[EquipSlot(slot_value)] = uid
        return cls(
            owned_items=owned,
            equipped=equipped,
            max_weight=data.get("max_weight", 100),
            current_weight=data.get("current_weight", 0),
        )