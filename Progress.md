# AIVenture — Progress Tracker

> Last updated: 2026-06-03

## Status Overview

| Metric | Value |
|---|---|
| **Total files** | 51 Python + 3 config/markdown |
| **Lines of code** | ~8,100 |
| **Tests** | 162 passing (0 failing) |
| **Phases complete** | Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 ✅ |

---

## Phase 1 — Foundation (MVP) ✅ Complete

### Milestone 0 — Scaffolding
- [x] **0.1** Project layout, `pyproject.toml`, `__init__.py` files, `.gitignore`
- [x] **0.2** Config loader (`aiventure/utils/config.py`) — Pydantic `GameConfig`, YAML loader, env var override
- [x] **0.3** Logging setup (`aiventure/utils/logging.py`)

### Phase 1 — Foundation
- [x] **1.1** Model: `Position`, `Direction` with offset arithmetic and opposites (`coords.py`)
- [x] **1.2** Model: `Room` with factory `create_empty` and all fields (`world.py`)
- [x] **1.3** Model: `Item`, `Inventory`, `ItemType`, `EquipSlot`, `VALID_SLOT_TYPES` (`item.py`)
- [x] **1.4** Model: `Entity`, `Player`, `EntityType`, `create_default`, `gain_xp` (`entity.py`)
- [x] **1.5** Model: `Quest`, `QuestStatus`, `Objective`, `Reward` (`quest.py`)
- [x] **1.6** Model: `World` with containers, lookups, `move_player`, `add_room` (`world.py`)
- [x] **1.7** Model: Full serialization (`to_dict`/`from_dict`) for all model types
- [x] **1.8** LLM: `LLMAdapter` ABC, `OpenAIAdapter`, `OpenAICompatibleAdapter`
- [x] **1.9** LLM: 5 tool schemas (`generate_room`, `describe_action_outcome`, `describe_combat_outcome`, `describe_item_use`, `generate_npc_dialogue`)
- [x] **1.10** LLM: `LLMService` with retry logic and `_call_with_tool`
- [x] **1.11** LLM: `ContextBuilder` — `build_room_generation_context`, `build_action_context`
- [x] **1.12** Controller: `ParsedCommand`, `parse_input` — synonym map, direction parsing, multi-word verbs
- [x] **1.13** Controller: `CommandRouter` (maps verbs → handlers)
- [x] **1.14** Controller: Action handlers — `move.py`, `inventory.py` (look/take/drop/inventory), `examine.py` (search)
- [x] **1.15** Controller: `GameSession` — main dispatch, history tracking, turn counting
- [x] **1.16** Persistence: `SaveProvider` ABC, `SaveManager`, `JsonFileProvider`, `MemoryProvider`
- [x] **1.17** Client: `CommandRequest`, `CommandResult`, `Client` ABC, `ConsoleClient`
- [x] **1.18** Entry point: `main.py` — new game / load game menu, world generation, game loop
- [x] **1.19** Tests: model + parser + persistence unit tests

---

## Phase 2 — Gameplay ✅ Complete

- [x] **2.1** Combat: `do_attack` — LLM-resolved combat, damage application, XP/loot on kill, death handling
- [x] **2.2** Equipment: `do_equip`/`do_unequip` — slot validation, `VALID_SLOT_TYPES`, stat bonuses into combat
- [x] **2.3** Item use: `do_use` — potions/consumables, deterministic HP heal, charge tracking, LLM narrative
- [x] **2.4** NPC dialogue: `do_talk` — resolve NPC, LLM dialogue, quest offers, item trades
- [x] **2.5** Enhanced parser: pronoun resolution (`it`, `them`), preposition extraction (`with`, `on`), single-letter shortcut guard, quest/use synonyms
- [x] **2.6** Freeform safety gate: LLM-discovered items/entities applied to world
- [x] **2.7** Quest system: `do_quests`, auto-advance kill/collect/explore objectives, `_grant_quest_rewards` (XP/gold/items)
- [x] **2.8** Room generation improvements: adjacent room context, world theme, entities + items in generated rooms

**LLMService extensions:** `CombatOutcomeData`, `ItemUseOutcomeData`, `NPCDialogueData` + async methods

**ContextBuilder extensions:** `build_combat_context`, `build_item_use_context`, `build_npc_dialogue_context`

---

## Phase 3 — Polish ✅ Complete

- [x] **3.1** Ollama adapter (`llm/adapters/ollama.py`) — `/api/chat` with tool calling, `/api/generate` for text
- [x] **3.2** SQLite persistence (`persistence/providers/sqlite.py`) — single DB, row per slot, metadata columns
- [x] **3.3** Context memory management (`llm/memory.py`) — sliding window, token budget, summarization
- [x] **3.4** Auto-save system — on interval, on room-gen, on quest-complete, on death, non-blocking (2s timeout)
- [x] **3.5** Death & respawn (`actions/death.py`) — configurable gold/item loss penalties, full heal, respawn at start
- [x] **3.6** WebSocket client (`client/websocket.py`) — async server, JSON protocol, result queuing
- [x] **3.7** Discord bot stub (`client/discord.py`) — console fallback when `discord` not installed
- [x] **3.8** Integration tests (`tests/test_integration.py`) — 19 tests covering full game loop with mock LLM
- [x] **3.9** Documentation — `README.md` with features, install, config, commands, architecture, extension guides

---

## Phase 4 — Community ✅ Complete

- [x] **4.1** Discord bot polish — full `DiscordClient` with embeds, reaction quick-actions, per-player sessions, `DiscordGameManager`
- [x] **4.2** Plugin system (`plugins.py`) — setuptools entry-point discovery under `aiventure.plugins` group
- [x] **4.3** World seed sharing — `export_world()`, `export_world_file()`, `import_world()`, `do_export()`, `do_import()` commands
- [x] **4.4** Statistics — `stats` command showing levels, rooms, items, quests, deaths, inventory

### Deferred / Out of Scope
- ~~4.5 Leaderboard~~ — requires cloud provider, marked optional in Plan.md

---

## Key Design Decisions

1. **MVC separation** — strict model/controller/client split for multiple frontends
2. **Config** — Pydantic models merged from YAML with `${ENV_VAR}` placeholder overrides
3. **Single-letter guard** — `i`, `l`, `q` only trigger on exact input to avoid matching sentences
4. **Combat resolution** — LLM generates narrative + damage via `describe_combat_outcome`; engine applies deterministic HP changes
5. **Target resolution** — dead entities filtered out to prevent attacking corpses
6. **ContextBuilder centralization** — all LLM prompts assembled in `ContextBuilder`
7. **Auto-save** — non-blocking with 2s timeout; fires on interval, room-gen, quest-complete, death
8. **Quest advancement** — `_advance_quests()` returns list of completed quest titles for save triggers
9. **UUIDs** — generated via `uuid.uuid4()` at object creation
10. **Model layer** — pure, synchronous `dataclass`es; all I/O is async

---

## Command Reference

| Command | Aliases | Description |
|---|---|---|
| Movement | `north`, `south`, `east`, `west`, `up`, `down` | Move one step |
| Movement | `go <dir>`, `walk <dir>` | Move with verb prefix |
| `look` | `l`, `examine` | Describe room or target |
| `take` | `get`, `grab`, `pick up` | Pick up item from room |
| `drop` | `discard`, `dump` | Drop item to ground |
| `inventory` | `i`, `inv`, `items` | Show inventory |
| `equip` | `wear`, `don`, `put on` | Equip item to slot |
| `unequip` | `remove`, `take off`, `doff` | Remove item from slot |
| `use` | `drink`, `activate` | Use potion/consumable |
| `attack` | `hit`, `kill`, `smash`, `strike` | Attack entity |
| `search` | `explore`, `rummage`, `probe` | Search room |
| `talk` | `speak`, `chat`, `hail`, `greet` | Talk to NPC |
| `quests` | `quest` | Show active quests |
| `stats` | `statistics` | Show game statistics |
| `save` | — | Save game to slot |
| `export` | `export world` | Export world to JSON file |
| `quit` | `q`, `exit` | Quit game |

---

## Test Coverage

| Test File | Tests | Covers |
|---|---|---|
| `test_coords.py` | 8 | Position, Direction offset/opposite/distance |
| `test_world.py` | 10 | Room, World creation, movement, lookups |
| `test_item.py` | 10 | Item, Inventory add/remove/equip/unequip/find/weight |
| `test_entity.py` | 10 | Entity, Player damage/heal/leveling/death |
| `test_quest.py` | 5 | Quest advance/complete/fail |
| `test_state.py` | 11 | Full world serialization round-trip |
| `test_parser.py` | 24 | All command patterns, pronouns, prepositions, guard |
| `test_combat.py` | 6 | Attack hit/miss/dead/friendly, effective stats with equipment |
| `test_providers.py` | 9 | JSON + Memory save/load/delete/list |
| `test_integration.py` | 19 | Full game loop, save/load (Memory + SQLite), auto-save, quests, death, export, pronouns |
| `test_discord.py` | 46 | DiscordClient embeds, classification, reactions, sessions, config |

**Total: 162 tests passing**