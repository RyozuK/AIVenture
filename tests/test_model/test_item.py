"""Tests for Item, Inventory, and enums."""

from aiventure.model.item import (
    EquipSlot,
    Inventory,
    Item,
    ItemType,
    VALID_SLOT_TYPES,
)


class TestItem:
    def test_defaults(self):
        item = Item()
        assert item.name == "Unknown Item"
        assert item.item_type == ItemType.TREASURE
        assert item.stat_value == 0
        assert item.charges == -1
        assert not item.is_equippable
        assert not item.is_key
        assert not item.is_quest_item

    def test_create_weapon(self):
        item = Item(
            name="Rusty Sword",
            description="A dull but serviceable blade.",
            item_type=ItemType.WEAPON,
            stat_value=3,
            is_equippable=True,
            equip_slot=EquipSlot.HAND,
        )
        assert item.stat_value == 3
        assert item.equip_slot == EquipSlot.HAND


class TestInventory:
    def _make_item(self, name: str = "Sword", item_type: ItemType = ItemType.WEAPON) -> Item:
        return Item(name=name, item_type=item_type)

    def test_add(self):
        inv = Inventory()
        item = self._make_item()
        assert inv.add(item)
        assert item.id in inv.owned_items

    def test_remove(self):
        inv = Inventory()
        item = self._make_item()
        inv.add(item)
        removed = inv.remove(item.id)
        assert removed is item
        assert item.id not in inv.owned_items

    def test_remove_nonexistent(self):
        inv = Inventory()
        assert inv.remove("nonexistent") is None

    def test_equip(self):
        inv = Inventory()
        item = self._make_item()
        item.is_equippable = True
        item.equip_slot = EquipSlot.HAND
        inv.add(item)
        assert inv.equip(item.id)
        assert inv.equipped[EquipSlot.HAND] == item.id

    def test_equip_non_equippable(self):
        inv = Inventory()
        item = self._make_item()
        inv.add(item)
        assert not inv.equip(item.id)

    def test_unequip(self):
        inv = Inventory()
        item = self._make_item()
        item.is_equippable = True
        item.equip_slot = EquipSlot.CHEST
        inv.add(item)
        inv.equip(item.id)
        assert inv.unequip(EquipSlot.CHEST)
        assert EquipSlot.CHEST not in inv.equipped

    def test_remove_auto_unequips(self):
        inv = Inventory()
        item = self._make_item()
        item.is_equippable = True
        item.equip_slot = EquipSlot.HAND
        inv.add(item)
        inv.equip(item.id)
        inv.remove(item.id)
        assert EquipSlot.HAND not in inv.equipped

    def test_find(self):
        inv = Inventory()
        sword = Item(name="Rusty Sword")
        potion = Item(name="Health Potion", item_type=ItemType.POTION)
        inv.add(sword)
        inv.add(potion)
        assert len(inv.find("sword")) == 1
        assert len(inv.find("potion")) == 1
        assert len(inv.find("nonexistent")) == 0

    def test_to_dict_and_back(self):
        inv = Inventory()
        item = Item(name="Shield", is_equippable=True, equip_slot=EquipSlot.OFF_HAND)
        inv.add(item)
        inv.equip(item.id)

        data = inv.to_dict()
        assert item.id in data["owned_items"]
        assert data["equipped"]["off_hand"] == item.id

        restored = Inventory.from_dict(data)
        assert item.id in restored.owned_items
        assert restored.equipped[EquipSlot.OFF_HAND] == item.id

    def test_weight_tracking(self):
        inv = Inventory(max_weight=2)
        inv.add(self._make_item("A", ItemType.WEAPON))
        inv.add(self._make_item("B", ItemType.ARMOR))
        assert inv.current_weight == 2
        # Third item should fail
        assert not inv.add(self._make_item("C", ItemType.POTION))

    def test_treasure_is_weightless(self):
        inv = Inventory(max_weight=1)
        treasure = Item(name="Gold Coin", item_type=ItemType.TREASURE)
        inv.add(treasure)
        assert inv.current_weight == 0  # weightless
        # Should still be able to add a normal item
        assert inv.add(self._make_item("Sword"))