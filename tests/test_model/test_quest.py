"""Tests for quest lifecycle and reward granting."""

import pytest

from aiventure.model.quest import Quest, QuestStatus, Objective, Reward


class TestQuestAdvancement:
    def test_kill_objective_advances(self):
        quest = Quest(
            title="Slay the Goblin King",
            objectives=[Objective(type="kill", target="Goblin King", required_count=1)],
        )
        assert not quest.all_objectives_complete
        completed = quest.advance("kill", "Goblin King")
        assert completed is True
        assert quest.status == QuestStatus.COMPLETE

    def test_collect_objective_advances(self):
        quest = Quest(
            title="Gather Herbs",
            objectives=[Objective(type="collect", target="Firebloom", required_count=3)],
        )
        assert not quest.advance("collect", "Firebloom")  # 1/3
        assert not quest.advance("collect", "Firebloom")  # 2/3
        assert quest.advance("collect", "Firebloom")      # 3/3 -> complete

    def test_partial_target_match(self):
        quest = Quest(
            title="Clear the Cave",
            objectives=[
                Objective(type="kill", target="Cave Spider", required_count=2),
            ],
        )
        quest.advance("kill", "spider")  # partial match
        quest.advance("kill", "spider")
        assert quest.status == QuestStatus.COMPLETE

    def test_wrong_type_no_advance(self):
        quest = Quest(
            title="Kill the Dragon",
            objectives=[Objective(type="kill", target="Dragon", required_count=1)],
        )
        quest.advance("collect", "Dragon")
        assert quest.status != QuestStatus.COMPLETE

    def test_fail_marks_QUEST(self):
        quest = Quest(title="Test", objectives=[Objective()])
        quest.fail()
        assert quest.status == QuestStatus.FAILED


class TestQuestRewards:
    def test_xp_reward(self):
        quest = Quest(
            title="Test",
            objectives=[Objective(type="explore")],
            rewards=[Reward(type="xp", value={"amount": 50})],
        )
        quest.advance("explore")
        assert quest.all_objectives_complete

    def test_gold_reward(self):
        quest = Quest(
            title="Test",
            objectives=[Objective(type="collect", target="gem")],
            rewards=[Reward(type="gold", value={"amount": 100})],
        )
        quest.advance("collect", "gem")
        assert quest.all_objectives_complete


class TestQuestSerialization:
    def test_round_trip(self):
        quest = Quest(
            title="Test Quest",
            description="A test.",
            objectives=[
                Objective(type="kill", target="Orc", required_count=5, current_count=3),
            ],
            rewards=[Reward(type="xp", value={"amount": 100})],
        )
        data = quest.to_dict()
        restored = Quest.from_dict(data)

        assert restored.title == quest.title
        assert restored.objectives[0].current_count == 3
        assert restored.rewards[0].value["amount"] == 100