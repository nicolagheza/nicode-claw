# Layered Project Restructure

## Overview

Reorganize nicode-claw from a flat file layout into a layered architecture with proper separation of concerns. Custom tools are scattered across 4 locations, files mix multiple responsibilities (toolkit + storage + background logic), and there's no clear dependency direction between modules.

## Goals

- All custom Agno toolkits consolidated in one `tools/` package
- Storage logic isolated into a `storage/` layer (tools and services both consume it)
- Background processes grouped in `services/`
- Shared infrastructure (config, context, formatting) in `core/`
- Strict dependency direction: core ← storage ← tools ← services/agent ← bot ← main
- No logic changes — pure restructure. Every function keeps its exact behavior.

## Target Structure

```
src/nicode_claw/
├── core/
│   ├── __init__.py
│   ├── config.py            # Settings dataclass
│   ├── context.py           # AppContext dataclass
│   └── formatting.py        # md_to_telegram_html() — pure conversion only
├── storage/
│   ├── __init__.py
│   ├── intents.py           # Follow-up intent CRUD
│   └── jobs.py              # Scheduled job CRUD
├── tools/
│   ├── __init__.py
│   ├── follow_up.py         # FollowUpTools (delegates to storage.intents)
│   ├── install.py           # InstallTools
│   ├── scheduler.py         # SchedulerTools (delegates to storage.jobs)
│   └── telegram.py          # TelegramTools
├── services/
│   ├── __init__.py
│   ├── reflection.py        # ReflectionRunner + run_reflection_loop
│   └── scheduler.py         # cron_matches() + run_scheduler()
├── agent/
│   ├── __init__.py
│   ├── factory.py           # create_agent(), create_mcp(), _get_model()
│   └── processing.py        # process_message(), transcribe_audio()
├── bot/
│   ├── __init__.py
│   ├── handlers.py          # Telegram message handlers
│   ├── media.py             # download_file()
│   └── reply.py             # reply_formatted()
├── __init__.py
├── __main__.py
└── main.py
```

## Layer Boundaries

Strict dependency direction — each layer can only import from layers below it:

```
main.py (wiring)
   ↓
bot/        → core, agent
services/   → core, storage, agent, bot.reply
agent/      → core, tools
tools/      → core, storage
   ↓
storage/    → (stdlib only)
core/       → (stdlib + third-party only)
```

Rules:
- `storage/` never imports from `tools/`, `services/`, or `bot/`
- `tools/` never import from `services/` or `bot/`
- `core/` never imports from any other internal package
- `services/reflection.py` imports `bot.reply.reply_formatted` — pragmatic exception since it's a pure send helper
- `core/context.py` uses `TYPE_CHECKING` imports for types from `tools/` and `agent/` — no runtime dependency, only for type annotations

## File Migration Map

### Splits (one file becomes multiple)

| Original | Becomes | What it gets |
|----------|---------|-------------|
| `scheduler.py` | `tools/scheduler.py` | SchedulerTools class |
| | `storage/jobs.py` | `load_jobs`, `save_jobs`, `JOBS_FILE` |
| | `services/scheduler.py` | `cron_matches()`, `run_scheduler()` |
| `follow_up.py` | `tools/follow_up.py` | FollowUpTools class |
| | `storage/intents.py` | `load_intents`, `save_intents`, `parse_check_in`, `get_due_intents`, `update_intent`, `prune_expired_intents` |
| `formatting.py` | `core/formatting.py` | `md_to_telegram_html()` + regex constants |
| | `bot/reply.py` | `reply_formatted()` |
| `agent/agent.py` | `agent/factory.py` | `create_agent()`, `create_mcp()`, `_get_model()` |
| | `agent/processing.py` | `process_message()`, `transcribe_audio()` |

### Moves (relocate without splitting)

| Original | Becomes |
|----------|---------|
| `config.py` | `core/config.py` |
| `context.py` | `core/context.py` |
| `install_tools.py` | `tools/install.py` |
| `bot/telegram_tools.py` | `tools/telegram.py` |
| `reflection.py` | `services/reflection.py` |
| `bot/handlers.py` | `bot/handlers.py` (stays) |
| `bot/media.py` | `bot/media.py` (stays) |

### Stays in place

- `main.py` — updates all imports
- `__main__.py` — unchanged

### Deleted after migration

Old locations removed once new files are in place:
- `scheduler.py`, `follow_up.py`, `formatting.py`, `install_tools.py`, `config.py`, `context.py`, `reflection.py`, `agent/agent.py`, `bot/telegram_tools.py`

## Storage Layer

Functions extracted from toolkit files become the public interface of the storage modules. The `_` prefix is dropped since these are now public APIs.

### `storage/jobs.py`

```python
JOBS_FILE = Path("data/scheduled_jobs.json")

def load_jobs() -> list[dict]: ...
def save_jobs(jobs: list[dict]) -> None: ...
```

Consumed by: `tools/scheduler.py`, `services/scheduler.py`

### `storage/intents.py`

```python
INTENTS_FILE = Path("data/follow_up_intents.json")

def load_intents() -> list[dict]: ...
def save_intents(intents: list[dict]) -> None: ...
def parse_check_in(check_in: str) -> datetime: ...
def get_due_intents() -> list[dict]: ...
def update_intent(intent_id: str, updates: dict) -> None: ...
def prune_expired_intents() -> int: ...
```

Consumed by: `tools/follow_up.py`, `services/reflection.py`

### Future migration path

When migrating to SQLite (for the event-driven agent evolution), only the `storage/` package changes. All consumers (tools, services) stay the same because they depend on the storage function interfaces, not on JSON file details.

## Import Updates

Every file that imports from a moved module needs its imports updated. The key changes:

- `from nicode_claw.config import Settings` → `from nicode_claw.core.config import Settings`
- `from nicode_claw.context import AppContext` → `from nicode_claw.core.context import AppContext`
- `from nicode_claw.formatting import reply_formatted` → `from nicode_claw.bot.reply import reply_formatted`
- `from nicode_claw.formatting import md_to_telegram_html` → `from nicode_claw.core.formatting import md_to_telegram_html`
- `from nicode_claw.scheduler import SchedulerTools, run_scheduler` → `from nicode_claw.tools.scheduler import SchedulerTools` + `from nicode_claw.services.scheduler import run_scheduler`
- `from nicode_claw.follow_up import FollowUpTools` → `from nicode_claw.tools.follow_up import FollowUpTools`
- `from nicode_claw.install_tools import InstallTools` → `from nicode_claw.tools.install import InstallTools`
- `from nicode_claw.bot.telegram_tools import TelegramTools` → `from nicode_claw.tools.telegram import TelegramTools`
- `from nicode_claw.agent.agent import process_message, transcribe_audio, create_agent, create_mcp` → split between `from nicode_claw.agent.factory import ...` and `from nicode_claw.agent.processing import ...`
- `from nicode_claw.reflection import run_reflection_loop` → `from nicode_claw.services.reflection import run_reflection_loop`

## Constraints

- No logic changes. Every function preserves its exact behavior.
- No new dependencies. Only stdlib, existing third-party, and internal imports.
- No test changes (project has no tests).
- The refactor should be done in a sequence that keeps the app importable at each step (create new → update imports → delete old).
