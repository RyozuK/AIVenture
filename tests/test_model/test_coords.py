"""Tests for Position and Direction."""

from aiventure.model.coords import Direction, Position


class TestPosition:
    def test_equality(self):
        assert Position(1, 2, 3) == Position(1, 2, 3)

    def test_inequality(self):
        assert Position(0, 0, 0) != Position(0, 0, 1)

    def test_hashable(self):
        pos = Position(1, 0, -1)
        assert {pos}  # survives set insertion
        assert {pos: "room"}  # survives dict key

    def test_offset_by(self):
        assert Position(0, 0, 0).offset_by(1, -1, 0) == Position(1, -1, 0)

    def test_str(self):
        assert str(Position(2, -3, 1)) == "(2, -3, 1)"


class TestDirection:
    def test_opposite(self):
        assert Direction.NORTH.opposite() == Direction.SOUTH
        assert Direction.EAST.opposite() == Direction.WEST
        assert Direction.UP.opposite() == Direction.DOWN

    def test_opposite_roundtrip(self):
        for d in Direction:
            assert d.opposite().opposite() == d

    def test_offset_north(self):
        assert Direction.NORTH.offset() == (0, -1, 0)

    def test_offset_south(self):
        assert Direction.SOUTH.offset() == (0, 1, 0)

    def test_offset_east(self):
        assert Direction.EAST.offset() == (1, 0, 0)

    def test_offset_west(self):
        assert Direction.WEST.offset() == (-1, 0, 0)

    def test_offset_up(self):
        assert Direction.UP.offset() == (0, 0, 1)

    def test_offset_down(self):
        assert Direction.DOWN.offset() == (0, 0, -1)

    def test_apply_to(self):
        pos = Position(5, 5, 0)
        assert Direction.NORTH.apply_to(pos) == Position(5, 4, 0)
        assert Direction.EAST.apply_to(pos) == Position(6, 5, 0)
        assert Direction.UP.apply_to(pos) == Position(5, 5, 1)

    def test_from_str(self):
        assert Direction.from_str("north") == Direction.NORTH
        assert Direction.from_str("NORTH") == Direction.NORTH
        assert Direction.from_str("  East  ") == Direction.EAST
        assert Direction.from_str("diagonal") is None
        assert Direction.from_str("") is None

    def test_count(self):
        assert len(Direction) == 6