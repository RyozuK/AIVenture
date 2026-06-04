# AIVenture — Implementation Plan

Derived from `NewDesign.md`. Organized into the 4 design phases, each broken into concrete tasks with file-level targets, dependencies, and acceptance criteria.

---

## Milestone 0 — Project Scaffolding

Before any game code, get the Python project structure, packaging, and config wired up.

### Task 0.1 — Create project layout
- Create all directories from the design (§11):
  `aiventure/` with `model/`, `controller/`, `llm/`, `persistence/`, `client/`, `utils/`, plus `saves/` and `tests/`
- Write `pyproject.toml` (setuptools, Python 3.11+, dependencies: `openai`, `httpx`, `pydantic`, `pydantic-settings`, `pyyaml`, `pytest`, `pytest-asyncio`)
- Write `aiventure/__init__.py` (empty or version string)
- Write `__init__.py` in every package directory
- Write `.gitignore` updates (`.pyc`, `__pycache__`, `.venv`, `*.db`, `saves/`)

### Task 0.2 — Config loader
**File:** `aiventure/utils/config.py`
- Define `GameConfig` pydantic-settings dataclass matching §10 YAML schema
- Support loading from `config.yaml` or env vars
- Provide `load_config(path: str | None = None) -> GameConfig`
- Write `config.yaml` (defaults from §10) and `config.example.yaml`

### Task 0.3 — Logging setup
**File:** `aiventure/utils/logging.py`
- Configure structured logging (JSON or plain) with `aiventure` logger
- Log level from config

**Acceptance:** `python -c "from aiventure.utils.config import load_config; print(load_config())"` works.

---

## Phase 1 — Foundation (MVP)

Goal: A playable game where the player moves through an AI-generated dungeon, sees descriptions, and encounters items.

### Task 1.1 — Model layer: Core enums and Position
**Files:** `aiventure/model/world.py`
- `Position(x, y, z)` — immutable, hashable, comparable dataclass
- `Direction` enum with `opposite()` and `offset() -> Position` methods
- Unit tests for offset arithmetic and opposites

### Task 1.2 — Model layer: Room
**File:** `aiventure/model/world.py`
- `Room` dataclass (id, position, name, description, exits, ambient_details, connected_entities, connected_items, features, visited_count)
- Default empty room factory: `Room.create_empty(position, name, description)`

### Task 1.3 — Model layer: Item and Inventory
**File:** `aiventure/model/item.py`
- `ItemType` enum, `EquipSlot` enum
- `Item` dataclass (all fields from §4.1)
- `Inventory` class with `add()`, `remove()`, `equip()`, `unequip()`, `find()`, `to_dict()`
- Unit tests for inventory operations (equip/unequip, weight tracking)

### Task 1.4 — Model layer: Entity and Player
**File:** `aiventure/model/entity.py`
- `EntityType` enum
- `Entity` dataclass (§4.1)
- `Player` extending `Entity` with gold, xp, level, quests, death_count
- Factory: `Player.create_default(name, position)`

### Task 1.5 — Model layer: Quest
**File:** `aiventure/model/quest.py`
- `QuestStatus` enum, `Objective`, `Reward`, `Quest` dataclasses

### Task 1.6 — Model layer: World
**File:** `aiventure/model/world.py`
- `World` dataclass with rooms dict, entities dict, items dict, quests dict, player, explored/generated positions, turn_count, world_seed, world_description
- Methods: `get_room()`, `get_entity()`, `get_item()`, `move_player()`, `add_room()`, `remove_entity()`, `to_dict()`
- Unit tests for world state mutations

### Task 1.7 — Model layer: Serialization
**File:** `aiventure/model/state.py`
- `world_to_dict(world: World) -> dict` and `world_from_dict(data: dict) -> World`
- Handle UUIDs, enums, sets (explored/generated positions)
- Round-trip test: `world_from_dict(world_to_dict(w)) == w`

### Task 1.8 — LLM adapter: Interface + OpenAI/Custom adapters
**File:** `aiventure/llm/adapter.py`
- `LLMAdapter` ABC, `LLMResponse`, `ToolCall` dataclasses (§5.5)
- `ToolSchema` TypedDict matching OpenAI tool format

**File:** `aiventure/llm/adapters/custom.py`
- `OpenAICompatibleAdapter` using `httpx.AsyncClient` to any OpenAI-compatible endpoint
- `chat()` with system prompt, user messages, tools, response_format
- `generate_text()` simple text completion
- Parse tool calls from response

**File:** `aiventure/llm/adapters/openai.py`
- `OpenAIAdapter` using the official `openai` SDK (subclass or wrap `OpenAICompatibleAdapter`)

**File:** `aiventure/llm/adapters/ollama.py`
- `OllamaAdapter` — stub for now (Phase 3). Implement later with `/api/chat` calls.

### Task 1.9 — LLM: Tool schemas
**File:** `aiventure/llm/tools.py`
- Define tool schemas for `generate_room` and `describe_action_outcome` (§5.2)
- Define shared sub-schemas: `item_schema`, `entity_schema`
- Export `ALL_TOOLS: list[ToolSchema]` and a lookup dict by name

### Task 1.10 — LLM: Service layer
**File:** `aiventure/llm/service.py`
- `LLMService` — wraps an `LLMAdapter`, provides:
  - `generate_room(source_room, direction, position, world_context) -> RoomData`
  - `describe_action_outcome(action_context) -> ActionOutcomeData`
- Each method builds system+user prompt, calls adapter with relevant tool, validates result
- Retry logic: up to N retries on malformed tool call, then fallback to raw text parse

### Task 1.11 — LLM: Context builder
**File:** `aiventure/controller/context.py`
- `ContextBuilder` class
- `build_room_generation_context(world, source_room, direction) -> (system_prompt, user_messages)`
- `build_action_context(world, action_description) -> (system_prompt, user_messages)`
- Includes: world theme, current room, player summary, recent history (last N turns), active quests

### Task 1.12 — Controller: Input parser
**File:** `aiventure/controller/parser.py`
- `parse_input(text: str) -> ParsedCommand`
- Recognize: direction movement (`north`, `go north`), `look`, `look at <target>`, `take <item>`, `attack <target>`, `search`, `inventory`, `use <item>`
- Unrecognized input → `ParsedCommand(verb="unknown", raw=text)` for LLM fallback
- Synonym map: take/get/pick up, go/move, i/inventory/inv, etc.
- Unit tests for all command patterns

### Task 1.13 — Controller: Command router
**File:** `aiventure/controller/router.py`
- `CommandRouter` — maps verb strings to action handler callables
- Built-in handlers (wired by `GameSession.__init__`): `move`, `look`, `take`, `drop`, `attack`, `search`, `inventory`, `unknown`
- Extension point: `register(verb, handler)`

### Task 1.14 — Controller: Action handlers (Phase 1 subset)
**File:** `aiventure/controller/actions/move.py`
- `handle_move(session, direction: Direction) -> CommandResult`
- Look up target position from current room exits
- If room exists: move player, update explored set
- If room doesn't exist: call `LLMService.generate_room()`, add to world, then move

**File:** `aiventure/controller/actions/examine.py`
- `handle_look(session, target: str | None) -> CommandResult`
- No target: return current room description + visible entities/items
- With target: resolve to entity or item, return detailed description

**File:** `aiventure/controller/actions/inventory.py`
- `handle_inventory(session) -> CommandResult`
- `handle_take(session, item_name: str) -> CommandResult`
- `handle_drop(session, item_name: str) -> CommandResult`
- Resolve item name → UUID, validate (is item in room / in inventory), mutate world

### Task 1.15 — Controller: GameSession
**File:** `aiventure/controller/session.py`
- `GameSession(world, llm_service, save_manager, config)`
- `process_command(input_text: str) -> CommandResult` — the main entry point
- Wires parser → router → action handlers
- Tracks turn count, recent history for context builder
- Returns `CommandResult` (§8.1) with narrative text and state snapshot

### Task 1.16 — Persistence: JsonFileProvider + SaveManager
**File:** `aiventure/persistence/provider.py`
- `SaveProvider` ABC (§7.1)

**File:** `aiventure/persistence/providers/json_file.py`
- `JsonFileProvider(directory: str)` — one JSON file per slot
- `save()`, `load()`, `delete()`, `list_slots()`

**File:** `aiventure/persistence/providers/memory.py`
- `MemoryProvider` — in-memory dict (for testing)

**File:** `aiventure/persistence/manager.py`
- `SaveManager` with `auto_save()`, `load_slot()`, `create_slot()`, `list_slots()` (§7.1)

### Task 1.17 — Client: Protocol types + Console client
**File:** `aiventure/client/protocol.py`
- `CommandRequest` and `CommandResult` dataclasses (§8.1)

**File:** `aiventure/client/base.py`
- `Client` ABC with `send_result(result)`, `get_input()`

**File:** `aiventure/client/console.py`
- `ConsoleClient` — stdin/stdout game loop
- Renders narrative text, shows room description on entry
- Prompt loop: `:> ` → input → CommandRequest → await result → display
- Graceful exit on `quit`/`exit`

### Task 1.18 — Bootstrapping: main entry point
**File:** `aiventure/__main__.py` (or `aiventure/main.py`)
- Load config
- Create LLM adapter from config (resolve provider type)
- Create LLMService with adapter + tool schemas
- Create SaveManager with JsonFileProvider
- Console menu: New Game / Load Game / Quit
- **New Game**: call LLM to generate world theme + starting room, create World, create Player
- **Load Game**: list slots, pick one, load World via SaveManager
- Start `GameSession` with `ConsoleClient`

### Task 1.19 — Tests: Phase 1 unit tests
**Directory:** `tests/`
- `test_model/test_world.py` — Position, Direction, Room, World
- `test_model/test_item.py` — Item, Inventory
- `test_model/test_entity.py` — Entity, Player
- `test_model/test_state.py` — round-trip serialization
- `test_controller/test_parser.py` — all command patterns
- `test_llm/test_tools.py` — tool schema structure validation
- `test_persistence/test_json_file.py` — save/load/delete/list (with MemoryProvider for speed)
- `tests/conftest.py` — shared fixtures (sample World, Player, etc.)

**Acceptance criteria for Phase 1:**
- Player can start a new game → sees starting room description
- Player can move in cardinal directions → new rooms generated by LLM
- Player can look at room, items, and entities
- Player can take/drop items
- Player can save and load game
- Console loop runs end-to-end with any OpenAI-compatible endpoint
- All unit tests pass

---

## Phase 2 — Gameplay

Goal: Full gameplay with combat, items, NPCs, and quests.

### Task 2.1 — Combat system
**File:** `aiventure/controller/actions/combat.py`
- `handle_attack(session, target_name: str) -> CommandResult`
- Resolve target entity, check hostility and range
- Build combat context: attacker stats (player + equipped weapon), defender stats, environment
- Call `LLMService.describe_combat_outcome()`
- Apply damage to both sides, check death, process loot drops
- Add combat narrative to history

**File:** `aiventure/llm/tools.py` (extend)
- Add `describe_combat_outcome` tool schema (§5.2)

**File:** `aiventure/llm/service.py` (extend)
- `describe_combat_outcome()` method

**Tests:** combat action with mock LLM service

### Task 2.2 — Equipment system
**File:** `aiventure/controller/actions/inventory.py` (extend)
- `handle_equip(session, item_name)`, `handle_unequip(session, slot)`
- Validate item type matches slot (weapon → HAND, armor → CHEST, etc.)
- Stat bonuses from equipped items factor into combat context

### Task 2.3 — Item use (potions, consumables)
**File:** `aiventure/controller/actions/inventory.py` (extend)
- `handle_use(session, item_name)` — for potions and consumables
- Call `LLMService.describe_item_use()` for non-deterministic effects
- Apply deterministic effects (heal potion: restore HP) + LLM narrative

**File:** `aiventure/llm/tools.py` (extend)
- Add `describe_item_use` tool schema

**File:** `aiventure/llm/service.py` (extend)
- `describe_item_use()` method

### Task 2.4 — NPCs and dialogue
**File:** `aiventure/controller/actions/social.py`
- `handle_talk(session, npc_name: str) -> CommandResult`
- Resolve NPC entity, verify in same room
- Call `LLMService.generate_npc_dialogue()`
- Display dialogue, handle quest offers or item trades in response

**File:** `aiventure/llm/tools.py` (extend)
- Add `generate_npc_dialogue` tool schema

**File:** `aiventure/llm/service.py` (extend)
- `generate_npc_dialogue()` method

### Task 2.5 — Enhanced natural language parser
**File:** `aiventure/controller/parser.py` (extend)
- Broader synonym maps
- Handle "i", "it" as pronouns referencing last mentioned target
- Better preposition handling ("attack the goblin with my sword")

### Task 2.6 — Freeform command via LLM
**File:** `aiventure/controller/actions/__init__.py` (or new `freeform.py`)
- `handle_unknown(session, raw_text: str) -> CommandResult`
- Pass full raw text to `LLMService.describe_action_outcome()`
- LLM determines if action is valid, generates narrative and state changes
- Controller validates proposed state changes before applying (safety gate)

### Task 2.7 — Quest system
**File:** `aiventure/controller/actions/quest.py`
- Quest display: `quests`, `quest <name>`
- Auto-advance quest objectives when relevant actions complete (kill, collect, explore)
- Quest completion: trigger reward granting
- Quest generation: via NPC dialogue or room features (LLM-generated)

**File:** `aiventure/model/quest.py` (extend)
- `Quest.complete()` — check all objectives, grant rewards
- `Quest.advance(objective_type, target)` — increment matching objectives

**Tests:** quest lifecycle (create → advance → complete → reward)

### Task 2.8 — Room generation improvements
**File:** `aiventure/llm/service.py` (extend)
- Context for room generation now includes: adjacent rooms' descriptions, world theme, dungeon depth (z level)
- LLM can generate items AND entities in rooms via `generate_room` tool
- Validation: exits must reference valid directions, no self-referential loops

**Acceptance criteria for Phase 2:**
- Player can fight enemies, see combat narratives, collect loot
- Player can equip weapons/armor, use potions
- Player can talk to NPCs, receive quests, complete them
- Freeform commands ("I try to sneaking past the guard") are interpreted by LLM
- Quests track progress and grant rewards on completion

---

## Phase 3 — Polish and Extensibility

Goal: Production-ready game with local model support, save management, and web client.

### Task 3.1 — Ollama adapter
**File:** `aiventure/llm/adapters/ollama.py`
- Full implementation using `httpx` to Ollama `/api/chat` endpoint
- Tool calling support (Ollama's tools format may differ — adapt)
- Fallback to JSON-mode prompt if tool calling not supported

### Task 3.2 — SQLite persistence provider
**File:** `aiventure/persistence/providers/sqlite.py`
- Single `.db` file, one row per save slot
- Columns: slot_name, world_json, created_at, modified_at, player_name, player_level, turn_count, room_name, thumbnail, metadata
- `SaveSlotInfo` metadata population

### Task 3.3 — Context memory management
**File:** `aiventure/llm/memory.py`
- `MemoryManager` class
- Token budget tracking per context component (lore, room, history, quests)
- Sliding window: keep last N turns of full history, summarize older turns
- Summarization: call a "light model" or same model with summarize prompt
- Eviction policy: drop oldest ambient details, compress entity descriptions

### Task 3.4 — Auto-save system
**File:** `aiventure/controller/session.py` (extend)
- Auto-save every N turns (from config)
- Auto-save on every new room generation
- Auto-save on quest completion
- Background save (non-blocking, don't wait for save to respond to player)

### Task 3.5 — Death and respawn
**File:** `aiventure/controller/actions/combat.py` (extend) or new `aiventure/controller/actions/death.py`
- Death narrative via `describe_action_outcome`
- Respawn logic: reset player to last checkpoint (starting room or last save room)
- Apply death penalties per config (xp retained, gold/item loss)
- Increment death_count

### Task 3.6 — WebSocket client
**File:** `aiventure/client/websocket.py`
- Async WebSocket server using `websockets` library
- Protocol: JSON CommandRequest/CommandResult over WS
- Session management: one `GameSession` per WS connection
- Support concurrent players
- Health endpoint for readiness checks

### Task 3.7 — Discord bot client (stub)
**File:** `aiventure/client/discord.py`
- `DiscordClient` using `discord.py` or `discord-py`
- Basic: DM-based single-session bot, text commands
- Advanced features (embeds, reactions) deferred to Phase 4

### Task 3.8 — Expanded test suite
- Integration test: full game loop with `MemoryProvider` + mock LLM adapter
  - Verifies: new game → move → generate room → take item → save → load → resume
- Mock LLM adapter that returns predetermined tool call responses
- Test all action handlers with mock LLM
- Async test fixtures with `pytest-asyncio`

### Task 3.9 — Documentation
- `README.md` — project overview, installation, config guide, usage
- `docs/config.md` — full config reference
- `docs/extend.md` — how to add new clients, persistence providers, LLM adapters
- `config.example.yaml` with all options documented

**Acceptance criteria for Phase 3:**
- Works with Ollama/local models
- SQLite saves with slot metadata and thumbnails
- Auto-save works reliably
- WebSocket client supports concurrent sessions
- Death/respawn cycle works with configurable penalties
- Full integration test passes

---

## Phase 4 — Community

Goal: Broader accessibility and extensibility.

### Task 4.1 — Discord bot polish
- Embed formatting for room descriptions and combat
- Reaction-based quick actions (⚔️ attack, 🔍 search, 🎒 inventory)
- Persistent per-player sessions in bot memory

### Task 4.2 — Plugin system
- Hook points: custom action handlers, custom tool schemas, custom persistence providers
- Entry-point based discovery (`setuptools entry_points`)
- `aiventure.plugins` registry

### Task 4.3 — World seed sharing
- Export: `world_to_dict()` → compressed JSON file with world_seed
- Import: load exported world, merge or replace current world
- Seed-based reproducibility (if LLM supports temperature=0 + seed)

### Task 4.4 — Statistics and analytics
- Track: turns played, rooms explored, entities killed, items collected, quests completed, time played
- `stats` command in-game
- Persist in save file

### Task 4.5 — Leaderboard (optional)
- Requires cloud provider
- Submit stats on quest completion or game end
- Anonymous by default

---

## Dependency Graph (Phase 1 tasks)

```
0.1 (scaffolding)
  └── 0.2 (config) ──┐
  └── 0.3 (logging)  │
                     ├── 1.1 (Position, Direction)
                     ├── 1.2 (Room)
                     ├── 1.3 (Item, Inventory)
                     ├── 1.4 (Entity, Player)
                     ├── 1.5 (Quest) ───────────────────────────┐
                     ├── 1.6 (World) ──────────────────────────┐│
                     │  └── 1.7 (serialization) ───────────────┤│
                     │                                         ││
                     ├── 1.8 (LLM adapters)                    ││
                     ├── 1.9 (tool schemas) ───────────────────┤│
                     │  └── 1.10 (LLM service) ────────────────┤│
                     │       └── 1.11 (context builder) ───────┤│
                     │                                         ││
                     ├── 1.12 (parser)                         ││
                     ├── 1.13 (router)                         ││
                     │  └── 1.14 (action handlers) ────────────┤│
                     │       └── 1.15 (GameSession) ───────────┘│
                     │              │                           │
                     ├── 1.16 (persistence)                     │
                     │  └───────────────────────────────────────┘
                     │
                     ├── 1.17 (console client)
                     │
                     └── 1.18 (main entry point)
                          └── 1.19 (tests)
```

### Execution order (recommended)
1. **Tasks 0.1–0.3** — Scaffold, config, logging (1 day)
2. **Tasks 1.1–1.7** — Full model layer + serialization (2 days)
3. **Tasks 1.8–1.11** — LLM layer (adapters, tools, service, context) (2 days)
4. **Tasks 1.12–1.15** — Controller layer (parser, router, actions, session) (2 days)
5. **Task 1.16** — Persistence (1 day)
6. **Tasks 1.17–1.18** — Console client + main entry (1 day)
7. **Task 1.19** — Tests (1–2 days, can overlap)

**Estimated Phase 1 total: ~10–12 days** (solo, part-time)

---

## Notes

- All model objects should be `dataclass` with type hints for IDE support and serialization.
- UUIDs should be generated with `uuid.uuid4()` at object creation time.
- All I/O (LLM calls, file saves, network) is `async`. The model layer is synchronous and pure.
- The console client can use `asyncio.run()` with `asyncio.run_coroutine_threadsafe()` or an async stdin reader for the input loop.
- For local development, the `MemoryProvider` and a mock LLM adapter that returns hardcoded tool calls are the primary testing tools — no real LLM needed for unit tests.