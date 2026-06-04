"""Position and Direction — coordinate system for the dungeon."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Position:
    """Immutable 3D grid coordinate."""

    x: int
    y: int
    z: int

    def __str__(self) -> str:
        return f"({self.x}, {self.y}, {self.z})"

    def offset_by(self, dx: int, dy: int, dz: int) -> Position:
        """Return a new Position shifted by *(dx, dy, dz)*."""
        return Position(self.x + dx, self.y + dy, self.z + dz)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: dict) -> Position:
        return cls(data["x"], data["y"], data["z"])

    def distance_to(self, other: Position) -> int:
        """Manhattan distance to *other*."""
        return abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)


# Lookup tables kept outside the Enum to avoid being captured as members
_DIRECTION_OPPOSITES = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
}

_DIRECTION_OFFSETS: dict[str, tuple[int, int, int]] = {
    "north": (0, -1, 0),
    "south": (0, 1, 0),
    "east": (1, 0, 0),
    "west": (-1, 0, 0),
    "up": (0, 0, 1),
    "down": (0, 0, -1),
}


class Direction(Enum):
    """Cardinal directions plus vertical movement."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    UP = "up"
    DOWN = "down"

    def opposite(self) -> Direction:
        """Return the opposite direction."""
        return Direction(_DIRECTION_OPPOSITES[self.value])

    def offset(self) -> tuple[int, int, int]:
        """Return the *(dx, dy, dz)* for this direction."""
        return _DIRECTION_OFFSETS[self.value]

    def apply_to(self, pos: Position) -> Position:
        """Return *pos* moved one step in this direction."""
        dx, dy, dz = self.offset()
        return pos.offset_by(dx, dy, dz)

    @classmethod
    def from_str(cls, text: str) -> Direction | None:
        """Case-insensitive lookup from a string token."""
        key = text.strip().lower()
        return cls(key) if key in _DIRECTION_OFFSETS else None