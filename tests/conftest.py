"""Shared pytest fixtures for model tests."""

from __future__ import annotations

import pytest

from aiventure.model.coords import Position
from aiventure.model.world import Room
from aiventure.model.entity import Player
from aiventure.model.world import World


@pytest.fixture
def origin() -> Position:
    return Position(0, 0, 0)


@pytest.fixture
def starting_room(origin: Position) -> Room:
    return Room.create_empty(origin, "The Entrance", "A dimly lit cavern entrance.")


@pytest.fixture
def player(origin: Position) -> Player:
    return Player.create_default("Hero", origin)


@pytest.fixture
def sample_world(origin: Position, starting_room: Room, player: Player) -> World:
    world = World(
        world_seed="dark dungeon",
        world_description="A treacherous underground labyrinth.",
    )
    world.add_room(starting_room)
    world.player = player
    world.explored_positions.add(origin)
    world.generated_positions.add(origin)
    return world