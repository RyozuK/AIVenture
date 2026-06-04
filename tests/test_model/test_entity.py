"""Tests for Entity, Player, and EntityType."""

from aiventure.model.entity import Entity, EntityType, Player
from aiventure.model.coords import Position


class TestEntity:
    def test_defaults(self):
        e = Entity()
        assert e.hp == 10
        assert e.max_hp == 10
        assert e.is_alive
        assert not e.is_hostile

    def test_take_damage(self):
        e = Entity(max_hp=20, hp=20, defense=2)
        dealt = e.take_damage(5)
        assert dealt == 3  # 5 - 2 defense
        assert e.hp == 17

    def test_take_damage_minimum_one(self):
        e = Entity(max_hp=10, hp=10, defense=10)
        dealt = e.take_damage(5)
        assert dealt == 1  # minimum 1
        assert e.hp == 9

    def test_death(self):
        e = Entity(max_hp=5, hp=5, defense=0)
        e.take_damage(10)
        assert not e.is_alive
        assert e.hp == 0

    def test_heal(self):
        e = Entity(max_hp=20, hp=10, defense=0)
        gained = e.heal(15)
        assert gained == 10  # capped at max
        assert e.hp == 20

    def test_heal_no_overflow(self):
        e = Entity(max_hp=10, hp=10)
        gained = e.heal(5)
        assert gained == 0


class TestPlayer:
    def test_create_default(self):
        p = Player.create_default("Gandalf", Position(0, 0, 0))
        assert p.name == "Gandalf"
        assert p.entity_type == EntityType.PLAYER
        assert p.hp == 20
        assert p.max_hp == 20
        assert p.level == 1
        assert p.gold == 0
        assert p.xp == 0
        assert p.position == Position(0, 0, 0)

    def test_gain_xp_no_level_up(self):
        p = Player.create_default("Hero", Position(0, 0, 0))
        leveled = p.gain_xp(30)
        assert not leveled
        assert p.xp == 30
        assert p.level == 1

    def test_gain_xp_level_up(self):
        p = Player.create_default("Hero", Position(0, 0, 0))
        leveled = p.gain_xp(60)  # threshold is 1 * 50 = 50
        assert leveled
        assert p.level == 2
        assert p.xp == 10  # 60 - 50
        assert p.max_hp == 25  # +5
        assert p.hp == 25  # full heal on level up
        assert p.attack == 4
        assert p.defense == 3

    def test_death_count(self):
        p = Player.create_default("Hero", Position(0, 0, 0))
        p.death_count = 3
        assert p.death_count == 3

    def test_active_quests(self):
        p = Player.create_default("Hero", Position(0, 0, 0))
        assert not p.active_quests
        p.active_quests.append("quest-uuid")
        assert len(p.active_quests) == 1