# Layered Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize nicode-claw from flat files into a layered architecture: core/, storage/, tools/, services/, agent/, bot/.

**Architecture:** Create all new package directories and files first (copying code with updated imports), then update consumers (main.py, handlers.py) to import from new locations, then delete old files. This ensures the app stays importable at every step.

**Tech Stack:** Python 3.12, Agno, python-telegram-bot

---

## File Structure

| New File | Responsibility | Source |
|----------|---------------|--------|
| `src/nicode_claw/core/__init__.py` | Package init | New |
| `src/nicode_claw/core/config.py` | Settings dataclass | From `config.py` |
| `src/nicode_claw/core/context.py` | AppContext dataclass | From `context.py` |
| `src/nicode_claw/core/formatting.py` | md_to_telegram_html() | From `formatting.py` (partial) |
| `src/nicode_claw/storage/__init__.py` | Package init | New |
| `src/nicode_claw/storage/jobs.py` | Job CRUD | From `scheduler.py` (partial) |
| `src/nicode_claw/storage/intents.py` | Intent CRUD | From `follow_up.py` (partial) |
| `src/nicode_claw/tools/__init__.py` | Package init | New |
| `src/nicode_claw/tools/scheduler.py` | SchedulerTools | From `scheduler.py` (partial) |
| `src/nicode_claw/tools/follow_up.py` | FollowUpTools | From `follow_up.py` (partial) |
| `src/nicode_claw/tools/install.py` | InstallTools | From `install_tools.py` |
| `src/nicode_claw/tools/telegram.py` | TelegramTools | From `bot/telegram_tools.py` |
| `src/nicode_claw/services/__init__.py` | Package init | New |
| `src/nicode_claw/services/scheduler.py` | cron_matches + run_scheduler | From `scheduler.py` (partial) |
| `src/nicode_claw/services/reflection.py` | ReflectionRunner + loop | From `reflection.py` |
| `src/nicode_claw/agent/factory.py` | create_agent, create_mcp | From `agent/agent.py` (partial) |
| `src/nicode_claw/agent/processing.py` | process_message, transcribe_audio | From `agent/agent.py` (partial) |
| `src/nicode_claw/bot/reply.py` | reply_formatted() | From `formatting.py` (partial) |

---

### Task 1: Create core/ package

**Files:**
- Create: `src/nicode_claw/core/__init__.py`
- Create: `src/nicode_claw/core/config.py`
- Create: `src/nicode_claw/core/context.py`
- Create: `src/nicode_claw/core/formatting.py`

- [ ] **Step 1: Create core/__init__.py**

```python
```

(Empty file)

- [ ] **Step 2: Create core/config.py**

Exact copy of current `config.py` — no import changes needed (it only imports stdlib + dotenv):

```python
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    mode: str  # "polling" or "webhook"
    webhook_url: str | None = None
    allowed_user_ids: list[int] | None = None
    db_path: str = "data/nicode_claw.db"
    model_provider: str = "openai"
    model_id: str = "gpt-5.4"
    google_stitch_api_key: str = ""
    quiet_hours_start: int = 23
    quiet_hours_end: int = 7
    max_proactive_messages_per_hour: int = 5
    reflection_interval_minutes: int = 15

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        api_key = os.environ.get("OPENAI_API_KEY")

        if not token or not api_key:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set"
            )

        raw_ids = os.environ.get("ALLOWED_USER_IDS", "")
        allowed_ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip()] or None

        return cls(
            telegram_bot_token=token,
            openai_api_key=api_key,
            mode=os.environ.get("MODE", "polling"),
            webhook_url=os.environ.get("WEBHOOK_URL") or None,
            allowed_user_ids=allowed_ids,
            db_path=os.environ.get("DB_PATH", "data/nicode_claw.db"),
            model_provider=os.environ.get("MODEL_PROVIDER", "openai"),
            model_id=os.environ.get("MODEL_ID", "gpt-5.4"),
            google_stitch_api_key=os.environ.get("GOOGLE_STITCH_API_KEY", ""),
            quiet_hours_start=int(os.environ.get("QUIET_HOURS_START", "23")),
            quiet_hours_end=int(os.environ.get("QUIET_HOURS_END", "7")),
            max_proactive_messages_per_hour=int(os.environ.get("MAX_PROACTIVE_MESSAGES_PER_HOUR", "5")),
            reflection_interval_minutes=int(os.environ.get("REFLECTION_INTERVAL_MINUTES", "15")),
        )
```

- [ ] **Step 3: Create core/context.py**

Updated imports to use new locations. Uses `TYPE_CHECKING` for tools/agent types to avoid circular deps:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import openai

if TYPE_CHECKING:
    from agno.agent import Agent
    from agno.tools.mcp import MCPTools

    from nicode_claw.tools.follow_up import FollowUpTools
    from nicode_claw.tools.scheduler import SchedulerTools
    from nicode_claw.tools.telegram import TelegramTools

from nicode_claw.core.config import Settings


@dataclass
class AppContext:
    settings: Settings
    agent: Agent
    telegram_tools: TelegramTools
    scheduler_tools: SchedulerTools
    openai_client: openai.AsyncOpenAI
    follow_up_tools: FollowUpTools | None = None
    mcp_tools: MCPTools | None = None
```

- [ ] **Step 4: Create core/formatting.py**

Only the pure conversion function — no `reply_formatted`:

```python
from __future__ import annotations

import html
import re

_RE_CODE_BLOCK = re.compile(r"```\w*\n(.*?)```", re.DOTALL)
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_HEADER = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_RE_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*")
_RE_BOLD_UNDER = re.compile(r"__(.+?)__")
_RE_ITALIC_STAR = re.compile(r"(?<!\w)\*([^*]+?)\*(?!\w)")
_RE_ITALIC_UNDER = re.compile(r"(?<!\w)_([^_]+?)_(?!\w)")
_RE_STRIKE = re.compile(r"~~(.+?)~~")
_RE_BLOCKQUOTE = re.compile(r"^>\s?(.+)$", re.MULTILINE)
_RE_LIST_ITEM = re.compile(r"^[-*]\s+", re.MULTILINE)


def md_to_telegram_html(text: str) -> str:
    """Convert common Markdown to Telegram-supported HTML."""
    code_blocks: list[str] = []

    def _save_code_block(m):
        code_blocks.append(html.escape(m.group(1)))
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = _RE_CODE_BLOCK.sub(_save_code_block, text)

    inline_codes: list[str] = []

    def _save_inline(m):
        inline_codes.append(html.escape(m.group(1)))
        return f"\x00INLINE{len(inline_codes) - 1}\x00"

    text = _RE_INLINE_CODE.sub(_save_inline, text)

    text = html.escape(text)

    text = _RE_HEADER.sub(r"<b>\1</b>", text)
    text = _RE_BOLD_STAR.sub(r"<b>\1</b>", text)
    text = _RE_BOLD_UNDER.sub(r"<b>\1</b>", text)
    text = _RE_ITALIC_STAR.sub(r"<i>\1</i>", text)
    text = _RE_ITALIC_UNDER.sub(r"<i>\1</i>", text)
    text = _RE_STRIKE.sub(r"<s>\1</s>", text)
    text = _RE_BLOCKQUOTE.sub(r"\1", text)
    text = _RE_LIST_ITEM.sub("• ", text)

    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{i}\x00", f"<pre>{block}</pre>")
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00INLINE{i}\x00", f"<code>{code}</code>")

    return text
```

- [ ] **Step 5: Commit**

```bash
git add src/nicode_claw/core/
git commit -m "$(cat <<'EOF'
refactor: create core/ package with config, context, formatting
EOF
)"
```

---

### Task 2: Create storage/ package

**Files:**
- Create: `src/nicode_claw/storage/__init__.py`
- Create: `src/nicode_claw/storage/jobs.py`
- Create: `src/nicode_claw/storage/intents.py`

- [ ] **Step 1: Create storage/__init__.py**

```python
```

(Empty file)

- [ ] **Step 2: Create storage/jobs.py**

Extracted from `scheduler.py`. Functions are now public (no `_` prefix):

```python
from __future__ import annotations

import json
from pathlib import Path

JOBS_FILE = Path("data/scheduled_jobs.json")


def load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    return json.loads(JOBS_FILE.read_text())


def save_jobs(jobs: list[dict]) -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))
```

- [ ] **Step 3: Create storage/intents.py**

Extracted from `follow_up.py`. Functions are now public (no `_` prefix):

```python
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

INTENTS_FILE = Path("data/follow_up_intents.json")


def load_intents() -> list[dict]:
    if not INTENTS_FILE.exists():
        return []
    return json.loads(INTENTS_FILE.read_text())


def save_intents(intents: list[dict]) -> None:
    INTENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    INTENTS_FILE.write_text(json.dumps(intents, indent=2))


def parse_check_in(check_in: str) -> datetime:
    """Parse a relative time string like '1h', '30m', '3 days', 'tomorrow morning' into an absolute datetime."""
    now = datetime.now()
    check_in = check_in.strip().lower()

    if check_in == "tomorrow morning":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    if check_in == "tomorrow":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    if check_in == "tonight":
        return now.replace(hour=20, minute=0, second=0, microsecond=0)

    if check_in == "next week":
        return now + timedelta(weeks=1)

    # Parse patterns like "1h", "30m", "2d", "3 days", "1 hour"
    match = re.match(r"(\d+)\s*(m|min|mins|minutes?|h|hrs?|hours?|d|days?|w|weeks?)", check_in)
    if match:
        value = int(match.group(1))
        unit = match.group(2)[0]  # first char: m, h, d, w
        if unit == "m":
            return now + timedelta(minutes=value)
        elif unit == "h":
            return now + timedelta(hours=value)
        elif unit == "d":
            return now + timedelta(days=value)
        elif unit == "w":
            return now + timedelta(weeks=value)

    # Default: check in 1 hour
    logger.warning("Could not parse check_in '%s', defaulting to 1 hour", check_in)
    return now + timedelta(hours=1)


def get_due_intents() -> list[dict]:
    """Return all pending intents whose check_at time has passed."""
    now = datetime.now().isoformat()
    intents = load_intents()
    return [
        i for i in intents
        if i["status"] == "pending" and i["check_at"] <= now
    ]


def update_intent(intent_id: str, updates: dict) -> None:
    """Update fields on an intent by ID."""
    intents = load_intents()
    for i in intents:
        if i["id"] == intent_id:
            i.update(updates)
            break
    save_intents(intents)


def prune_expired_intents() -> int:
    """Remove intents that have exceeded max_checks. Returns count pruned."""
    intents = load_intents()
    before = len(intents)
    intents = [
        i for i in intents
        if not (i["checks_done"] >= i["max_checks"] and i["status"] != "reported")
    ]
    pruned = before - len(intents)
    if pruned > 0:
        save_intents(intents)
    return pruned
```

- [ ] **Step 4: Commit**

```bash
git add src/nicode_claw/storage/
git commit -m "$(cat <<'EOF'
refactor: create storage/ package with jobs and intents CRUD
EOF
)"
```

---

### Task 3: Create tools/ package

**Files:**
- Create: `src/nicode_claw/tools/__init__.py`
- Create: `src/nicode_claw/tools/scheduler.py`
- Create: `src/nicode_claw/tools/follow_up.py`
- Create: `src/nicode_claw/tools/install.py`
- Create: `src/nicode_claw/tools/telegram.py`

- [ ] **Step 1: Create tools/__init__.py**

```python
```

(Empty file)

- [ ] **Step 2: Create tools/scheduler.py**

SchedulerTools class only, delegates to storage:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from agno.tools.toolkit import Toolkit

from nicode_claw.storage.jobs import load_jobs, save_jobs


class SchedulerTools(Toolkit):

    def __init__(self):
        super().__init__(name="scheduler_tools")
        self.register(self.create_scheduled_job)
        self.register(self.list_scheduled_jobs)
        self.register(self.delete_scheduled_job)

    def create_scheduled_job(self, cron: str, prompt: str, name: str = "") -> str:
        """Create a scheduled job that runs on a cron schedule.
        The prompt will be sent to the AI agent at the scheduled time and the response
        will be sent to the user via Telegram.

        Args:
            cron: Cron expression (e.g. "0 10 * * *" for every day at 10:00,
                  "0 8 * * 1-5" for weekdays at 8:00, "*/30 * * * *" for every 30 min).
                  Format: minute hour day_of_month month day_of_week
            prompt: The prompt/task to execute at the scheduled time.
            name: Optional human-readable name for the job.

        Returns:
            Confirmation with the job ID.
        """
        jobs = load_jobs()
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "name": name or prompt[:50],
            "cron": cron,
            "prompt": prompt,
            "created_at": datetime.now().isoformat(),
        }
        jobs.append(job)
        save_jobs(jobs)
        return f"Job '{job['name']}' created with ID {job_id}. Schedule: {cron}"

    def list_scheduled_jobs(self) -> str:
        """List all scheduled jobs.

        Returns:
            A formatted list of all scheduled jobs.
        """
        jobs = load_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = []
        for j in jobs:
            lines.append(f"- **{j['name']}** (ID: {j['id']})\n  Schedule: {j['cron']}\n  Prompt: {j['prompt']}")
        return "\n".join(lines)

    def delete_scheduled_job(self, job_id: str) -> str:
        """Delete a scheduled job by its ID.

        Args:
            job_id: The ID of the job to delete.

        Returns:
            Confirmation or error message.
        """
        jobs = load_jobs()
        new_jobs = [j for j in jobs if j["id"] != job_id]
        if len(new_jobs) == len(jobs):
            return f"Job with ID {job_id} not found."
        save_jobs(new_jobs)
        return f"Job {job_id} deleted."
```

- [ ] **Step 3: Create tools/follow_up.py**

FollowUpTools class only, delegates to storage:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from agno.tools.toolkit import Toolkit

from nicode_claw.storage.intents import (
    load_intents,
    parse_check_in,
    save_intents,
)


class FollowUpTools(Toolkit):

    def __init__(self):
        super().__init__(name="follow_up_tools")
        self.register(self.create_follow_up)
        self.register(self.list_follow_ups)
        self.register(self.delete_follow_up)

    def create_follow_up(
        self,
        what: str,
        why: str,
        check_in: str,
        how: str = "silent_check",
        priority: str = "medium",
        max_checks: int = 3,
    ) -> str:
        """Create a follow-up intent to check on something later.

        Use this when a conversation involves something worth following up on:
        a task in progress, a decision pending, something the user is tracking,
        or an interesting topic worth monitoring.

        Args:
            what: What to check or do (e.g. "check if AAPL dropped below $150").
            why: The conversational context that triggered this (e.g. "user was watching AAPL position").
            check_in: When to check — relative time like "1h", "30m", "tomorrow morning", "3 days".
            how: Strategy — "silent_check" (run tools, only report if noteworthy) or "direct_ask" (message the user).
            priority: "low", "medium", or "high" — affects whether results get reported.
            max_checks: Maximum number of times to check before expiring (default 3).

        Returns:
            Confirmation with the intent ID.
        """
        intents = load_intents()
        intent_id = str(uuid.uuid4())[:8]
        check_at = parse_check_in(check_in)

        intent = {
            "id": intent_id,
            "what": what,
            "why": why,
            "check_at": check_at.isoformat(),
            "how": how,
            "priority": priority,
            "max_checks": max_checks,
            "checks_done": 0,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        intents.append(intent)
        save_intents(intents)
        return f"Follow-up created (ID: {intent_id}): will check '{what}' at {check_at.strftime('%Y-%m-%d %H:%M')}"

    def list_follow_ups(self) -> str:
        """List all active follow-up intents.

        Returns:
            A formatted list of all active (non-expired) follow-up intents.
        """
        intents = load_intents()
        active = [i for i in intents if i["status"] in ("pending", "checked")]
        if not active:
            return "No active follow-ups."
        lines = []
        for i in active:
            lines.append(
                f"- **{i['what']}** (ID: {i['id']})\n"
                f"  Why: {i['why']}\n"
                f"  Next check: {i['check_at']}\n"
                f"  Priority: {i['priority']} | Checks: {i['checks_done']}/{i['max_checks']}"
            )
        return "\n".join(lines)

    def delete_follow_up(self, intent_id: str) -> str:
        """Delete a follow-up intent by its ID.

        Args:
            intent_id: The ID of the follow-up to delete.

        Returns:
            Confirmation or error message.
        """
        intents = load_intents()
        new_intents = [i for i in intents if i["id"] != intent_id]
        if len(new_intents) == len(intents):
            return f"Follow-up with ID {intent_id} not found."
        save_intents(new_intents)
        return f"Follow-up {intent_id} deleted."
```

- [ ] **Step 4: Create tools/install.py**

Moved from `install_tools.py`, unchanged:

```python
from __future__ import annotations

import logging
import shutil
import subprocess

from agno.tools.toolkit import Toolkit

logger = logging.getLogger(__name__)


class InstallTools(Toolkit):

    def __init__(self):
        super().__init__(name="install_tools")
        self.register(self.install_package)

    def install_package(self, package_name: str) -> str:
        """Install a Python package using uv. Use this when a package is missing.

        Args:
            package_name: The name of the package to install (e.g. "openpyxl", "requests").

        Returns:
            A success or error message.
        """
        uv_path = shutil.which("uv")
        if not uv_path:
            return "Error: uv not found in PATH."

        try:
            result = subprocess.run(
                [uv_path, "add", package_name],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return f"Package '{package_name}' installed successfully."
            return f"Error installing {package_name}: {result.stderr}"
        except Exception as e:
            logger.exception("Error installing package %s", package_name)
            return f"Error installing {package_name}: {e}"
```

- [ ] **Step 5: Create tools/telegram.py**

Moved from `bot/telegram_tools.py`, unchanged:

```python
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agno.tools.toolkit import Toolkit

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


class TelegramTools(Toolkit):

    def __init__(self):
        super().__init__(name="telegram_tools")
        self._chat_id: int | None = None
        self._bot = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.register(self.send_file)

    def set_context(self, bot, chat_id: int, loop: asyncio.AbstractEventLoop) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._loop = loop

    def send_file(self, file_path: str, caption: str = "") -> str:
        """Send a file to the user via Telegram with an optional caption.

        Args:
            file_path: The path to the file to send.
            caption: Optional caption to display under the file.

        Returns:
            A confirmation message or an error message.
        """
        if self._bot is None or self._chat_id is None or self._loop is None:
            return "Error: Telegram context not set."

        path = Path(file_path)
        if not path.exists():
            # Search in common tool directories
            for search_dir in [Path("tmp/files"), Path("tmp/python")]:
                candidate = search_dir / path.name
                if candidate.exists():
                    path = candidate
                    break
            else:
                return f"Error: File not found: {file_path}"

        try:
            with open(path, "rb") as f:
                data = f.read()

            if path.suffix.lower() in IMAGE_EXTENSIONS:
                future = asyncio.run_coroutine_threadsafe(
                    self._bot.send_photo(
                        chat_id=self._chat_id, photo=data, caption=caption or None
                    ),
                    self._loop,
                )
            else:
                future = asyncio.run_coroutine_threadsafe(
                    self._bot.send_document(
                        chat_id=self._chat_id,
                        document=data,
                        filename=path.name,
                        caption=caption or None,
                    ),
                    self._loop,
                )
            future.result(timeout=30)
            return f"File '{path.name}' sent to user."
        except Exception as e:
            logger.exception("Error sending file %s", file_path)
            return f"Error sending file: {e}"
```

- [ ] **Step 6: Commit**

```bash
git add src/nicode_claw/tools/
git commit -m "$(cat <<'EOF'
refactor: create tools/ package with all custom Agno toolkits
EOF
)"
```

---

### Task 4: Create services/ package

**Files:**
- Create: `src/nicode_claw/services/__init__.py`
- Create: `src/nicode_claw/services/scheduler.py`
- Create: `src/nicode_claw/services/reflection.py`

- [ ] **Step 1: Create services/__init__.py**

```python
```

(Empty file)

- [ ] **Step 2: Create services/scheduler.py**

Cron matching + background loop, delegates to storage for job data:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from nicode_claw.agent.processing import process_message
from nicode_claw.bot.reply import reply_formatted
from nicode_claw.storage.jobs import load_jobs

if TYPE_CHECKING:
    from telegram import Bot

    from nicode_claw.core.context import AppContext

logger = logging.getLogger(__name__)


def cron_matches(cron: str, now: datetime) -> bool:
    parts = cron.strip().split()
    if len(parts) != 5:
        return False

    def match_field(field: str, value: int) -> bool:
        if field == "*":
            return True
        for part in field.split(","):
            if "/" in part:
                base, step = part.split("/")
                step = int(step)
                start = 0 if base == "*" else int(base)
                if value >= start and (value - start) % step == 0:
                    return True
            elif "-" in part:
                lo, hi = part.split("-")
                if int(lo) <= value <= int(hi):
                    return True
            elif int(part) == value:
                return True
        return False

    minute, hour, dom, month, dow = parts
    return (
        match_field(minute, now.minute)
        and match_field(hour, now.hour)
        and match_field(dom, now.day)
        and match_field(month, now.month)
        and match_field(dow, now.isoweekday() % 7)
    )


async def run_scheduler(ctx: AppContext, bot: Bot, chat_id: int, user_id: str) -> None:
    logger.info("Scheduler started")
    while True:
        try:
            await asyncio.sleep(60)
            now = datetime.now()
            jobs = load_jobs()
            for job in jobs:
                if cron_matches(job["cron"], now):
                    logger.info("Running scheduled job: %s", job["name"])
                    try:
                        ctx.telegram_tools.set_context(bot, chat_id, asyncio.get_running_loop())
                        response = await process_message(
                            ctx.agent,
                            f"[Scheduled task: {job['name']}]\n{job['prompt']}",
                            user_id=user_id,
                            session_id=str(chat_id),
                        )
                        await reply_formatted(bot, chat_id, response)
                    except Exception:
                        logger.exception("Error running scheduled job %s", job["id"])
        except Exception:
            logger.exception("Scheduler error")
```

- [ ] **Step 3: Create services/reflection.py**

Updated imports to use new locations:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from agno.agent import Agent

from nicode_claw.bot.reply import reply_formatted
from nicode_claw.storage.intents import (
    get_due_intents,
    parse_check_in,
    prune_expired_intents,
    update_intent,
)

if TYPE_CHECKING:
    from telegram import Bot

    from nicode_claw.core.config import Settings

logger = logging.getLogger(__name__)

REFLECTION_INSTRUCTIONS = """You are in reflection mode. You are reviewing follow-up intents to decide what's worth acting on.

For each intent you receive, you must:
1. Execute the check described in the intent using your available tools (search, finance data, code execution, etc.)
2. Evaluate: is the result noteworthy enough to message the user?
3. Respond with your finding and a clear YES or NO verdict on whether to message the user.

Guidelines:
- Be proactive but respect the user's attention — only recommend messaging if you have something genuinely useful to say.
- A silent check that finds nothing interesting is a success, not a failure.
- For "direct_ask" intents, always recommend messaging (these are explicit follow-up questions).
- For "silent_check" intents, only recommend messaging if the result is significant.
- When recommending a message, compose it ready to send. Use these prefixes:
  - "💭 Thinking of you" — for pattern-based insights
  - "🔔 Quick follow-up" — for task follow-ups
  - "⚡ Heads up" — for monitoring alerts

Respond in this format:
VERDICT: YES or NO
MESSAGE: (only if YES) The exact message to send to the user.
RESCHEDULE: (only if NO) A relative time for when to check again, e.g. "1h", "6h", "1d". Or "expire" if no further checks are useful."""


def _is_quiet_hours(settings: Settings) -> bool:
    hour = datetime.now().hour
    start = settings.quiet_hours_start
    end = settings.quiet_hours_end
    if start > end:
        # Wraps midnight, e.g. 23-7
        return hour >= start or hour < end
    else:
        return start <= hour < end


class ReflectionRunner:

    def __init__(self, settings: Settings, agent: Agent, bot: Bot, chat_id: int):
        self._settings = settings
        self._agent = agent
        self._bot = bot
        self._chat_id = chat_id
        self._messages_this_hour: list[datetime] = []

    def _check_rate_limit(self) -> bool:
        """Return True if we can still send messages this hour."""
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        self._messages_this_hour = [t for t in self._messages_this_hour if t > cutoff]
        return len(self._messages_this_hour) < self._settings.max_proactive_messages_per_hour

    def _record_message(self) -> None:
        self._messages_this_hour.append(datetime.now())

    async def run_once(self) -> None:
        """Run one reflection cycle: process due intents, prune expired."""
        if _is_quiet_hours(self._settings):
            logger.debug("Reflection skipped: quiet hours")
            return

        due_intents = get_due_intents()
        if not due_intents:
            logger.debug("Reflection: no due intents")
            prune_expired_intents()
            return

        # Sort by priority: high first
        priority_order = {"high": 0, "medium": 1, "low": 2}
        due_intents.sort(key=lambda i: priority_order.get(i["priority"], 1))

        for intent in due_intents:
            if not self._check_rate_limit():
                logger.info("Reflection: rate limit reached, deferring remaining intents")
                break

            await self._process_intent(intent)

        prune_expired_intents()

    async def _process_intent(self, intent: dict) -> None:
        """Process a single follow-up intent."""
        logger.info("Reflection: processing intent %s — %s", intent["id"], intent["what"])

        prompt = (
            f"Follow-up intent to process:\n"
            f"- What: {intent['what']}\n"
            f"- Why: {intent['why']}\n"
            f"- Type: {intent['how']}\n"
            f"- Priority: {intent['priority']}\n"
            f"- Checks so far: {intent['checks_done']}/{intent['max_checks']}\n\n"
            f"Execute the check and provide your verdict."
        )

        try:
            run_output = await self._agent.arun(
                prompt,
                user_id="reflection",
                session_id="reflection",
            )
            response = run_output.content

            # Parse the response for verdict
            if "VERDICT: YES" in response.upper():
                # Extract message
                message = self._extract_message(response)
                if message:
                    await reply_formatted(self._bot, self._chat_id, message)
                    self._record_message()
                    update_intent(intent["id"], {
                        "status": "reported",
                        "checks_done": intent["checks_done"] + 1,
                    })
                    logger.info("Reflection: reported intent %s to user", intent["id"])
                else:
                    logger.warning("Reflection: YES verdict but no message extracted for %s", intent["id"])
                    self._reschedule_intent(intent, "1h")
            else:
                # Extract reschedule time
                reschedule = self._extract_reschedule(response)
                if reschedule == "expire":
                    update_intent(intent["id"], {
                        "status": "expired",
                        "checks_done": intent["checks_done"] + 1,
                    })
                    logger.info("Reflection: expired intent %s", intent["id"])
                else:
                    self._reschedule_intent(intent, reschedule)

        except Exception:
            logger.exception("Reflection: error processing intent %s", intent["id"])
            self._reschedule_intent(intent, "1h")

    def _reschedule_intent(self, intent: dict, check_in: str) -> None:
        """Reschedule an intent for a later check."""
        new_check_at = parse_check_in(check_in)
        update_intent(intent["id"], {
            "status": "pending",
            "checks_done": intent["checks_done"] + 1,
            "check_at": new_check_at.isoformat(),
        })
        logger.info("Reflection: rescheduled intent %s to %s", intent["id"], new_check_at)

    def _extract_message(self, response: str) -> str | None:
        """Extract the MESSAGE: line from a reflection response."""
        for line in response.split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("MESSAGE:"):
                return stripped[len("MESSAGE:"):].strip()
        # If no MESSAGE: line found, look for content after VERDICT: YES
        parts = response.split("VERDICT: YES", 1)
        if len(parts) > 1:
            remaining = parts[1].strip()
            # Skip the RESCHEDULE line if present
            lines = [l for l in remaining.split("\n") if not l.strip().upper().startswith("RESCHEDULE:")]
            content = "\n".join(lines).strip()
            if content:
                return content
        return None

    def _extract_reschedule(self, response: str) -> str:
        """Extract the RESCHEDULE: value from a reflection response."""
        for line in response.split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("RESCHEDULE:"):
                return stripped[len("RESCHEDULE:"):].strip().lower()
        return "1h"


async def run_reflection_loop(
    settings: Settings,
    agent: Agent,
    bot: Bot,
    chat_id: int,
) -> None:
    """Background loop that runs reflection on a configurable interval."""
    runner = ReflectionRunner(settings, agent, bot, chat_id)
    interval = settings.reflection_interval_minutes * 60
    logger.info("Reflection loop started (interval: %d minutes)", settings.reflection_interval_minutes)

    while True:
        try:
            await asyncio.sleep(interval)
            await runner.run_once()
        except Exception:
            logger.exception("Reflection loop error")
```

- [ ] **Step 4: Commit**

```bash
git add src/nicode_claw/services/
git commit -m "$(cat <<'EOF'
refactor: create services/ package with scheduler loop and reflection runner
EOF
)"
```

---

### Task 5: Create new agent/ files and bot/reply.py

**Files:**
- Create: `src/nicode_claw/agent/factory.py`
- Create: `src/nicode_claw/agent/processing.py`
- Create: `src/nicode_claw/bot/reply.py`

- [ ] **Step 1: Create agent/factory.py**

Agent creation logic with updated imports:

```python
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.models.openrouter import OpenRouter
from agno.skills import Skills, LocalSkills
from agno.tools.csv_toolkit import CsvTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.file import FileTools
from agno.tools.hackernews import HackerNewsTools
from agno.tools.mcp import MCPTools
from agno.tools.mcp.params import StreamableHTTPClientParams
from agno.tools.python import PythonTools
from agno.tools.shell import ShellTools
from agno.tools.yfinance import YFinanceTools

from nicode_claw.core.config import Settings
from nicode_claw.tools.follow_up import FollowUpTools
from nicode_claw.tools.install import InstallTools
from nicode_claw.tools.telegram import TelegramTools

if TYPE_CHECKING:
    from nicode_claw.tools.scheduler import SchedulerTools


def create_mcp(settings: Settings) -> MCPTools:
    return MCPTools(
        transport="streamable-http",
        server_params=StreamableHTTPClientParams(
            url="https://stitch.googleapis.com/mcp",
            headers={"X-Goog-Api-Key": settings.google_stitch_api_key},
            timeout=timedelta(seconds=120),
        ),
        timeout_seconds=120,
        refresh_connection=True,
    )


def _get_model(settings: Settings):
    if settings.model_provider == "openrouter":
        return OpenRouter(id=settings.model_id)
    return OpenAIChat(id=settings.model_id)


def create_agent(
    settings: Settings,
    telegram_tools: TelegramTools,
    scheduler_tools: SchedulerTools,
    follow_up_tools: FollowUpTools | None = None,
    mcp_tools: MCPTools | None = None,
) -> Agent:
    db = SqliteDb(db_file=settings.db_path)

    tools = [
        DuckDuckGoTools(),
        HackerNewsTools(),
        CsvTools(),
        FileTools(base_dir=Path("tmp/files")),
        PythonTools(
            base_dir=Path("tmp/python"),
            exclude_tools=["pip_install_package", "uv_pip_install_package"],
        ),
        ShellTools(),
        YFinanceTools(),
        InstallTools(),
        telegram_tools,
        scheduler_tools,
    ]
    if follow_up_tools:
        tools.append(follow_up_tools)
    if mcp_tools:
        tools.append(mcp_tools)

    return Agent(
        model=_get_model(settings),
        description="A helpful AI assistant called nicodeclaw and you live in your creator's computer. You communicate via Telegram.",
        instructions=[
            "You are a helpful assistant.",
            "Respond concisely and clearly.",
            "You can analyze images, documents, and audio.",
            "When you generate a file (chart, image, CSV, etc.), use the send_file tool to send it to the user.",
            "When you need to install a Python package, use the install_package tool.",
            "Files saved by FileTools are in tmp/files/. Files saved by PythonTools are in tmp/python/. Use the full path when calling send_file.",
            "For complex coding tasks, you can delegate to Claude Code via shell: claude -p 'your prompt here' --dangerously-skip-permissions --output-format text",
            "When a conversation involves something that might benefit from a follow-up (a task in progress, a decision pending, something the user is tracking, an interesting topic), use create_follow_up to schedule one. Be eager — it's better to create a follow-up and have it turn out to be nothing than to miss something the user would have appreciated.",
        ],
        tools=tools,
        markdown=True,
        db=db,
        add_history_to_context=True,
        num_history_runs=10,
        enable_agentic_memory=True,
        skills=Skills(loaders=[LocalSkills(".agents/skills")]),
        debug_mode=True,
    )
```

- [ ] **Step 2: Create agent/processing.py**

Message processing + audio transcription:

```python
from __future__ import annotations

import io

import openai
from agno.agent import Agent
from agno.media import Image


async def process_message(
    agent: Agent,
    text: str,
    *,
    user_id: str,
    session_id: str,
    images: list[bytes] | None = None,
) -> str:
    image_objects = [Image(content=b) for b in images] if images else []
    run_output = await agent.arun(
        text,
        images=image_objects or None,
        user_id=user_id,
        session_id=session_id,
    )
    return run_output.content


async def transcribe_audio(client: openai.AsyncOpenAI, audio_bytes: bytes) -> str:
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.ogg"
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text
```

- [ ] **Step 3: Create bot/reply.py**

The Telegram send helper, imports formatting from core:

```python
from __future__ import annotations

from telegram.constants import ParseMode

from nicode_claw.core.formatting import md_to_telegram_html


async def reply_formatted(bot, chat_id: int, text: str) -> None:
    """Send with Telegram HTML formatting, falling back to plain text."""
    try:
        formatted = md_to_telegram_html(text)
        await bot.send_message(chat_id=chat_id, text=formatted, parse_mode=ParseMode.HTML)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text)
```

- [ ] **Step 4: Commit**

```bash
git add src/nicode_claw/agent/factory.py src/nicode_claw/agent/processing.py src/nicode_claw/bot/reply.py
git commit -m "$(cat <<'EOF'
refactor: split agent/agent.py into factory + processing, add bot/reply.py
EOF
)"
```

---

### Task 6: Update consumers (main.py, bot/handlers.py)

**Files:**
- Modify: `src/nicode_claw/main.py`
- Modify: `src/nicode_claw/bot/handlers.py`

- [ ] **Step 1: Rewrite main.py with new imports**

Replace the entire content of `src/nicode_claw/main.py`:

```python
from __future__ import annotations

import asyncio
import logging

import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from nicode_claw.agent.factory import create_agent, create_mcp
from nicode_claw.bot.handlers import (
    handle_audio,
    handle_document,
    handle_photo,
    handle_text,
    start_command,
)
from nicode_claw.core.config import Settings
from nicode_claw.core.context import AppContext
from nicode_claw.services.reflection import run_reflection_loop
from nicode_claw.services.scheduler import run_scheduler
from nicode_claw.tools.follow_up import FollowUpTools
from nicode_claw.tools.scheduler import SchedulerTools
from nicode_claw.tools.telegram import TelegramTools

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings.from_env()

    telegram_tools = TelegramTools()
    scheduler_tools = SchedulerTools()
    follow_up_tools = FollowUpTools()

    async def post_init(application: Application) -> None:
        mcp = create_mcp(settings) if settings.google_stitch_api_key else None
        agent = create_agent(settings, telegram_tools, scheduler_tools, follow_up_tools, mcp)
        ctx = AppContext(
            settings=settings,
            agent=agent,
            telegram_tools=telegram_tools,
            scheduler_tools=scheduler_tools,
            openai_client=openai.AsyncOpenAI(),
            follow_up_tools=follow_up_tools,
            mcp_tools=mcp,
        )
        application.bot_data["ctx"] = ctx
        if settings.allowed_user_ids:
            chat_id = settings.allowed_user_ids[0]
            user_id = str(chat_id)
            asyncio.create_task(
                run_scheduler(ctx, application.bot, chat_id, user_id)
            )
            asyncio.create_task(
                run_reflection_loop(settings, agent, application.bot, chat_id)
            )

    async def post_shutdown(application: Application) -> None:
        ctx: AppContext | None = application.bot_data.get("ctx")
        if ctx and ctx.mcp_tools:
            await ctx.mcp_tools.close()

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(
        MessageHandler(filters.AUDIO | filters.VOICE, handle_audio)
    )

    if settings.mode == "webhook":
        logger.info("Starting in webhook mode: %s", settings.webhook_url)
        app.run_webhook(
            listen="0.0.0.0",
            port=8443,
            webhook_url=settings.webhook_url,
        )
    else:
        logger.info("Starting in polling mode")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rewrite bot/handlers.py with new imports**

Replace the entire content of `src/nicode_claw/bot/handlers.py`:

```python
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from nicode_claw.agent.processing import process_message, transcribe_audio
from nicode_claw.bot.media import download_file
from nicode_claw.bot.reply import reply_formatted
from nicode_claw.core.context import AppContext

logger = logging.getLogger(__name__)

_ERROR_MSG = "Mi dispiace, qualcosa è andato storto. Riprova."


def _get_ctx(context: ContextTypes.DEFAULT_TYPE) -> AppContext:
    return context.bot_data["ctx"]


def _is_allowed(ctx: AppContext, update: Update) -> bool:
    allowed = ctx.settings.allowed_user_ids
    if allowed is None:
        return True
    user = update.effective_user
    return user is not None and user.id in allowed


async def _handle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str,
    *,
    images: list[bytes] | None = None,
) -> None:
    """Common handler logic: auth check, set context, call agent, reply."""
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    try:
        ctx.telegram_tools.set_context(context.bot, chat_id, asyncio.get_running_loop())
        response = await process_message(
            ctx.agent, prompt, user_id=user_id, session_id=str(chat_id), images=images
        )
        await reply_formatted(context.bot, chat_id, response)
    except Exception:
        logger.exception("Error processing message")
        await update.message.reply_text(_ERROR_MSG)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    await update.message.reply_text(
        "Ciao! Sono il tuo assistente AI. Inviami un messaggio, "
        "un'immagine o un audio e ti rispondo."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle(update, context, update.message.text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    photo = update.message.photo[-1]
    caption = update.message.caption or "Describe this image."
    image_bytes = await download_file(context.bot, photo.file_id)
    await _handle(update, context, caption, images=[image_bytes])


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    doc = update.message.document
    caption = update.message.caption or ""
    file_bytes = await download_file(context.bot, doc.file_id)
    text_content = file_bytes.decode("utf-8", errors="replace")
    prompt = f"{caption}\n\nDocument content:\n{text_content}" if caption else f"Analyze this document:\n{text_content}"
    await _handle(update, context, prompt)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    audio = update.message.audio or update.message.voice
    caption = update.message.caption or ""
    audio_bytes = await download_file(context.bot, audio.file_id)
    transcription = await transcribe_audio(ctx.openai_client, audio_bytes)
    await update.message.reply_text(f"\U0001f399 Trascrizione:\n{transcription}")
    prompt = f"{caption}\n\nAudio transcription:\n{transcription}" if caption else transcription
    await _handle(update, context, prompt)
```

- [ ] **Step 3: Commit**

```bash
git add src/nicode_claw/main.py src/nicode_claw/bot/handlers.py
git commit -m "$(cat <<'EOF'
refactor: update main.py and handlers.py to use new package structure
EOF
)"
```

---

### Task 7: Delete old files

**Files:**
- Delete: `src/nicode_claw/config.py`
- Delete: `src/nicode_claw/context.py`
- Delete: `src/nicode_claw/formatting.py`
- Delete: `src/nicode_claw/install_tools.py`
- Delete: `src/nicode_claw/follow_up.py`
- Delete: `src/nicode_claw/scheduler.py`
- Delete: `src/nicode_claw/reflection.py`
- Delete: `src/nicode_claw/agent/agent.py`
- Delete: `src/nicode_claw/bot/telegram_tools.py`

- [ ] **Step 1: Delete all old files**

```bash
rm src/nicode_claw/config.py
rm src/nicode_claw/context.py
rm src/nicode_claw/formatting.py
rm src/nicode_claw/install_tools.py
rm src/nicode_claw/follow_up.py
rm src/nicode_claw/scheduler.py
rm src/nicode_claw/reflection.py
rm src/nicode_claw/agent/agent.py
rm src/nicode_claw/bot/telegram_tools.py
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: remove old files superseded by new package structure
EOF
)"
```

---

### Task 8: Verify end-to-end

**Files:** None (verification only)

- [ ] **Step 1: Verify all imports resolve**

```bash
cd /Users/nicolagheza/Developer/nicode-claw && uv run python -c "
from nicode_claw.core.config import Settings
from nicode_claw.core.context import AppContext
from nicode_claw.core.formatting import md_to_telegram_html
from nicode_claw.storage.jobs import load_jobs, save_jobs
from nicode_claw.storage.intents import load_intents, save_intents, parse_check_in, get_due_intents, update_intent, prune_expired_intents
from nicode_claw.tools.scheduler import SchedulerTools
from nicode_claw.tools.follow_up import FollowUpTools
from nicode_claw.tools.install import InstallTools
from nicode_claw.tools.telegram import TelegramTools
from nicode_claw.agent.factory import create_agent, create_mcp
from nicode_claw.agent.processing import process_message, transcribe_audio
from nicode_claw.bot.reply import reply_formatted
from nicode_claw.services.reflection import run_reflection_loop, ReflectionRunner
from nicode_claw.services.scheduler import run_scheduler, cron_matches
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 2: Verify full import chain through main**

```bash
cd /Users/nicolagheza/Developer/nicode-claw && uv run python -c "from nicode_claw.main import main; print('Full import chain OK')"
```

Expected: `Full import chain OK`

- [ ] **Step 3: Verify no old imports remain**

```bash
cd /Users/nicolagheza/Developer/nicode-claw && grep -rn "from nicode_claw.config " src/nicode_claw/ || true
grep -rn "from nicode_claw.context " src/nicode_claw/ || true
grep -rn "from nicode_claw.formatting " src/nicode_claw/ || true
grep -rn "from nicode_claw.install_tools " src/nicode_claw/ || true
grep -rn "from nicode_claw.follow_up " src/nicode_claw/ || true
grep -rn "from nicode_claw.scheduler " src/nicode_claw/ || true
grep -rn "from nicode_claw.reflection " src/nicode_claw/ || true
grep -rn "from nicode_claw.agent.agent " src/nicode_claw/ || true
grep -rn "from nicode_claw.bot.telegram_tools " src/nicode_claw/ || true
```

Expected: No output (no matches)

- [ ] **Step 4: Commit any fixes if needed**

If any issues were found, fix and commit:

```bash
git add -A
git commit -m "fix: address issues found during verification"
```
