"""Tests for Room."""

from aiventure.model.coords import Direction, Position
from aiventure.model.world import Room


class TestRoom:
    def test_create_empty(self):
        pos = Position(0, 0, 0)
        room = Room.create_empty(pos, "Test Room", "A test room.")
        assert room.position == pos
        assert room.name == "Test Room"
        assert room.description == "A test room."
        assert room.visited_count == 0
        assert not room.exits
        assert not room.connected_entities
        assert not room.connected_items
        assert not room.features

    def test_default_description(self):
        room = Room.create_empty(Position(0, 0, 0), "Void")
        assert "Void" in room.description

    def test_uuid_generated(self):
        r1 = Room.create_empty(Position(0, 0, 0), "A")
        r2 = Room.create_empty(Position(1, 0, 0), "B")
        assert r1.id != r2.id

    def test_to_dict_and_back(self):
        pos = Position(2, -1, 0)
        room = Room.create_empty(pos, "Cellar", "Dank and dark.")
        room.exits[Direction.UP] = Position(2, -1, 1)
        room.connected_items.append("item-uuid-1")
        room.visited_count = 3

        data = room.to_dict()
        assert data["position"] == {"x": 2, "y": -1, "z": 0}
        assert data["name"] == "Cellar"
        assert "up" in data["exits"]
        assert data["visited_count"] == 3

        restored = Room.from_dict(data)
        assert restored.position == pos
        assert restored.name == "Cellar"
        assert Direction.UP in restored.exits
        assert restored.exits[Direction.UP] == Position(2, -1, 1)
        assert restored.visited_count == 3
        assert restored.connected_items == ["item-uuid-1"]

    def test_from_dict_empty_exits(self):
        data = {
            "id": "abc",
            "position": {"x": 0, "y": 0, "z": 0},
            "name": "Empty",
            "description": "",
            "exits": {},
            "ambient_details": [],
            "connected_entities": [],
            "connected_items": [],
            "features": [],
            "visited_count": 0,
        }
        room = Room.from_dict(data)
        assert not room.exits
        assert room.id == "abc"