"""Tests for the natural language command parser."""

import pytest

from aiventure.controller.parser import parse_input, ParsedCommand
from aiventure.model.coords import Direction


class TestMovement:
    def test_direction_only(self):
        cmd = parse_input("north")
        assert cmd.verb == "move"
        assert cmd.direction == Direction.NORTH

    def test_direction_with_go(self):
        cmd = parse_input("go north")
        assert cmd.verb == "move"
        assert cmd.direction == Direction.NORTH

    def test_direction_walk(self):
        cmd = parse_input("walk south")
        assert cmd.direction == Direction.SOUTH

    def test_all_cardinals(self):
        for name, d in [("north", Direction.NORTH), ("south", Direction.SOUTH),
                         ("east", Direction.EAST), ("west", Direction.WEST)]:
            cmd = parse_input(name)
            assert cmd.direction == d, f"Failed for {name}"

    def test_vertical(self):
        assert parse_input("up").direction == Direction.UP
        assert parse_input("down").direction == Direction.DOWN


class TestLook:
    def test_look(self):
        assert parse_input("look").verb == "look"

    def test_look_at_target(self):
        cmd = parse_input("look at the goblin")
        assert cmd.verb == "look"
        assert "goblin" in cmd.target.lower()

    def test_examine(self):
        cmd = parse_input("examine the chest")
        assert cmd.verb == "look"
        assert "chest" in cmd.target.lower()


class TestTake:
    def test_take(self):
        cmd = parse_input("take the sword")
        assert cmd.verb == "take"

    def test_get(self):
        cmd = parse_input("get the potion")
        assert cmd.verb == "take"

    def test_pick_up(self):
        cmd = parse_input("pick up the key")
        assert cmd.verb == "take"


class TestDrop:
    def test_drop(self):
        cmd = parse_input("drop the sword")
        assert cmd.verb == "drop"

    def test_discard(self):
        cmd = parse_input("discard the potion")
        assert cmd.verb == "drop"


class TestInventory:
    def test_inventory(self):
        cmd = parse_input("inventory")
        assert cmd.verb == "inventory"

    def test_i(self):
        cmd = parse_input("i")
        assert cmd.verb == "inventory"

    def test_inv(self):
        cmd = parse_input("inv")
        assert cmd.verb == "inventory"


class TestAttack:
    def test_attack(self):
        cmd = parse_input("attack the goblin")
        assert cmd.verb == "attack"

    def test_hit(self):
        cmd = parse_input("hit the orc")
        assert cmd.verb == "attack"


class TestSearch:
    def test_search(self):
        cmd = parse_input("search")
        assert cmd.verb == "search"

    def test_search_room(self):
        cmd = parse_input("search the room")
        assert cmd.verb == "search"


class TestUnknown:
    def test_freeform(self):
        cmd = parse_input("i found a secret passage")
        assert cmd.verb == "unknown"

    def test_nonsense(self):
        cmd = parse_input("xyzzy")
        assert cmd.verb == "unknown"

    def test_empty(self):
        cmd = parse_input("")
        assert cmd.verb == "look"


class TestQuit:
    def test_quit(self):
        cmd = parse_input("quit")
        assert cmd.verb == "quit"

    def test_exit(self):
        cmd = parse_input("exit")
        assert cmd.verb == "quit"

    def test_q(self):
        cmd = parse_input("q")
        assert cmd.verb == "quit"