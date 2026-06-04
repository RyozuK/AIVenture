"""Tests for persistence providers."""

import pytest

from aiventure.persistence.providers.memory import MemoryProvider
from aiventure.persistence.providers.json_file import JsonFileProvider


@pytest.fixture
def mem_provider():
    return MemoryProvider()


@pytest.fixture
def json_provider(tmp_path):
    return JsonFileProvider(str(tmp_path / "saves"))


@pytest.mark.asyncio
async def test_memory_save_load(mem_provider):
    data = {"foo": "bar", "number": 42}
    await mem_provider.save("slot1", data)
    loaded = await mem_provider.load("slot1")
    assert loaded == data


@pytest.mark.asyncio
async def test_memory_load_nonexistent(mem_provider):
    assert await mem_provider.load("nope") is None


@pytest.mark.asyncio
async def test_memory_delete(mem_provider):
    await mem_provider.save("slot1", {"a": 1})
    await mem_provider.delete("slot1")
    assert await mem_provider.load("slot1") is None


@pytest.mark.asyncio
async def test_memory_list_slots(mem_provider):
    await mem_provider.save("alpha", {})
    await mem_provider.save("beta", {})
    slots = await mem_provider.list_slots()
    assert set(slots) == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_json_save_load(json_provider):
    data = {"rooms": {}, "player": {"name": "Hero"}}
    await json_provider.save("test_save", data)
    loaded = await json_provider.load("test_save")
    assert loaded == data


@pytest.mark.asyncio
async def test_json_load_nonexistent(json_provider):
    assert await json_provider.load("nope") is None


@pytest.mark.asyncio
async def test_json_delete(json_provider):
    await json_provider.save("del_me", {"x": 1})
    await json_provider.delete("del_me")
    assert await json_provider.load("del_me") is None


@pytest.mark.asyncio
async def test_json_list_slots(json_provider):
    await json_provider.save("save1", {})
    await json_provider.save("save2", {})
    slots = await json_provider.list_slots()
    assert "save1" in slots
    assert "save2" in slots