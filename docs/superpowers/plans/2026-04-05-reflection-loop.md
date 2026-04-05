# Reflection Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the agent proactive — it creates follow-up intents during conversations, and a periodic reflection loop processes them, messaging the user only when something noteworthy is found.

**Architecture:** A `FollowUpTools` toolkit gives the agent a `create_follow_up` tool it can call during normal conversations. A `ReflectionRunner` runs on a configurable interval via the existing scheduler infrastructure, loads due intents, invokes the agent with a reflection-focused prompt, and sends Telegram messages when results are worth reporting. Quiet hours and rate limiting protect the user's attention.

**Tech Stack:** Python 3.12, Agno (Toolkit), python-telegram-bot, existing scheduler loop

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/nicode_claw/follow_up.py` | **New** — FollowUpTools toolkit (create/list/delete intents), intent storage (JSON CRUD) |
| `src/nicode_claw/reflection.py` | **New** — ReflectionRunner: loads due intents, invokes reflection agent, handles messaging decisions, generates new intents, prunes expired |
| `src/nicode_claw/config.py` | **Modified** — add quiet hours, rate limit, reflection interval settings |
| `src/nicode_claw/context.py` | **Modified** — add `follow_up_tools` field to AppContext |
| `src/nicode_claw/agent/agent.py` | **Modified** — add FollowUpTools to agent, add follow-up instruction |
| `src/nicode_claw/main.py` | **Modified** — wire up FollowUpTools, start reflection loop |
| `.env.example` | **Modified** — document new config variables |

---

### Task 1: Add Configuration Settings

**Files:**
- Modify: `src/nicode_claw/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add new fields to Settings dataclass**

In `src/nicode_claw/config.py`, add four new fields to the `Settings` dataclass and parse them in `from_env`:

```python
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
```

In `from_env`, add parsing for the new fields:

```python
quiet_hours_start=int(os.environ.get("QUIET_HOURS_START", "23")),
quiet_hours_end=int(os.environ.get("QUIET_HOURS_END", "7")),
max_proactive_messages_per_hour=int(os.environ.get("MAX_PROACTIVE_MESSAGES_PER_HOUR", "5")),
reflection_interval_minutes=int(os.environ.get("REFLECTION_INTERVAL_MINUTES", "15")),
```

- [ ] **Step 2: Update .env.example**

Append to `.env.example`:

```
QUIET_HOURS_START=23
QUIET_HOURS_END=7
MAX_PROACTIVE_MESSAGES_PER_HOUR=5
REFLECTION_INTERVAL_MINUTES=15
```

- [ ] **Step 3: Commit**

```bash
git add src/nicode_claw/config.py .env.example
git commit -m "$(cat <<'EOF'
feat: add reflection loop configuration settings

Add quiet hours, rate limiting, and reflection interval config
to support the upcoming proactive follow-up feature.
EOF
)"
```

---

### Task 2: Create FollowUpTools

**Files:**
- Create: `src/nicode_claw/follow_up.py`

- [ ] **Step 1: Create the follow_up module with intent storage and toolkit**

Create `src/nicode_claw/follow_up.py`:

```python
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from agno.tools.toolkit import Toolkit

logger = logging.getLogger(__name__)

INTENTS_FILE = Path("data/follow_up_intents.json")


def _load_intents() -> list[dict]:
    if not INTENTS_FILE.exists():
        return []
    return json.loads(INTENTS_FILE.read_text())


def _save_intents(intents: list[dict]) -> None:
    INTENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    INTENTS_FILE.write_text(json.dumps(intents, indent=2))


def _parse_check_in(check_in: str) -> datetime:
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
    import re

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
    intents = _load_intents()
    return [
        i for i in intents
        if i["status"] == "pending" and i["check_at"] <= now
    ]


def update_intent(intent_id: str, updates: dict) -> None:
    """Update fields on an intent by ID."""
    intents = _load_intents()
    for i in intents:
        if i["id"] == intent_id:
            i.update(updates)
            break
    _save_intents(intents)


def prune_expired_intents() -> int:
    """Remove intents that have exceeded max_checks. Returns count pruned."""
    intents = _load_intents()
    before = len(intents)
    intents = [
        i for i in intents
        if not (i["checks_done"] >= i["max_checks"] and i["status"] != "reported")
    ]
    pruned = before - len(intents)
    if pruned > 0:
        _save_intents(intents)
    return pruned


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
        intents = _load_intents()
        intent_id = str(uuid.uuid4())[:8]
        check_at = _parse_check_in(check_in)

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
        _save_intents(intents)
        return f"Follow-up created (ID: {intent_id}): will check '{what}' at {check_at.strftime('%Y-%m-%d %H:%M')}"

    def list_follow_ups(self) -> str:
        """List all active follow-up intents.

        Returns:
            A formatted list of all active (non-expired) follow-up intents.
        """
        intents = _load_intents()
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
        intents = _load_intents()
        new_intents = [i for i in intents if i["id"] != intent_id]
        if len(new_intents) == len(intents):
            return f"Follow-up with ID {intent_id} not found."
        _save_intents(new_intents)
        return f"Follow-up {intent_id} deleted."
```

- [ ] **Step 2: Commit**

```bash
git add src/nicode_claw/follow_up.py
git commit -m "$(cat <<'EOF'
feat: add FollowUpTools for creating and managing follow-up intents

Provides create_follow_up, list_follow_ups, and delete_follow_up tools
plus storage helpers for the reflection loop to consume.
EOF
)"
```

---

### Task 3: Create ReflectionRunner

**Files:**
- Create: `src/nicode_claw/reflection.py`

- [ ] **Step 1: Create the reflection module**

Create `src/nicode_claw/reflection.py`:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from agno.agent import Agent

from nicode_claw.follow_up import (
    get_due_intents,
    prune_expired_intents,
    update_intent,
)
from nicode_claw.formatting import reply_formatted

if TYPE_CHECKING:
    from telegram import Bot

    from nicode_claw.config import Settings

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
        from nicode_claw.follow_up import _parse_check_in

        new_check_at = _parse_check_in(check_in)
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

- [ ] **Step 2: Commit**

```bash
git add src/nicode_claw/reflection.py
git commit -m "$(cat <<'EOF'
feat: add ReflectionRunner for proactive follow-up processing

Periodic loop that checks due intents, invokes the agent with a
reflection prompt, messages the user when results are noteworthy,
and respects quiet hours and rate limits.
EOF
)"
```

---

### Task 4: Wire FollowUpTools into the Agent

**Files:**
- Modify: `src/nicode_claw/agent/agent.py`

- [ ] **Step 1: Import FollowUpTools and add it to the agent's tools and instructions**

In `src/nicode_claw/agent/agent.py`, add the import:

```python
from nicode_claw.follow_up import FollowUpTools
```

Update `create_agent` to accept and include `follow_up_tools`:

```python
def create_agent(
    settings: Settings,
    telegram_tools: TelegramTools,
    scheduler_tools: SchedulerTools,
    follow_up_tools: FollowUpTools | None = None,
    mcp_tools: MCPTools | None = None,
) -> Agent:
```

Add `follow_up_tools` to the tools list (after `scheduler_tools`):

```python
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
```

Add a new instruction to the instructions list:

```python
"When a conversation involves something that might benefit from a follow-up (a task in progress, a decision pending, something the user is tracking, an interesting topic), use create_follow_up to schedule one. Be eager — it's better to create a follow-up and have it turn out to be nothing than to miss something the user would have appreciated.",
```

- [ ] **Step 2: Commit**

```bash
git add src/nicode_claw/agent/agent.py
git commit -m "$(cat <<'EOF'
feat: integrate FollowUpTools into the agent

Agent can now create follow-up intents during conversations and
is instructed to be proactive about scheduling them.
EOF
)"
```

---

### Task 5: Update AppContext

**Files:**
- Modify: `src/nicode_claw/context.py`

- [ ] **Step 1: Add follow_up_tools to AppContext**

In `src/nicode_claw/context.py`, add the import and field:

```python
from nicode_claw.follow_up import FollowUpTools
```

Add to the dataclass:

```python
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

- [ ] **Step 2: Commit**

```bash
git add src/nicode_claw/context.py
git commit -m "$(cat <<'EOF'
feat: add follow_up_tools to AppContext
EOF
)"
```

---

### Task 6: Wire Everything in main.py

**Files:**
- Modify: `src/nicode_claw/main.py`

- [ ] **Step 1: Import new modules, create FollowUpTools, pass to agent, and start reflection loop**

In `src/nicode_claw/main.py`, add imports:

```python
from nicode_claw.follow_up import FollowUpTools
from nicode_claw.reflection import run_reflection_loop
```

In the `main()` function, create the FollowUpTools instance alongside the other tools:

```python
def main() -> None:
    settings = Settings.from_env()

    telegram_tools = TelegramTools()
    scheduler_tools = SchedulerTools()
    follow_up_tools = FollowUpTools()
```

In `post_init`, pass `follow_up_tools` to `create_agent` and `AppContext`, and start the reflection loop:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add src/nicode_claw/main.py
git commit -m "$(cat <<'EOF'
feat: wire up FollowUpTools and reflection loop in main

Creates FollowUpTools, passes it to the agent, and starts the
reflection background loop alongside the existing scheduler.
EOF
)"
```

---

### Task 7: Verify End-to-End

**Files:** None (verification only)

- [ ] **Step 1: Verify the app starts without errors**

Run:
```bash
cd /Users/nicolagheza/Developer/nicode-claw && uv run python -c "from nicode_claw.follow_up import FollowUpTools; from nicode_claw.reflection import ReflectionRunner; print('Imports OK')"
```

Expected: `Imports OK`

- [ ] **Step 2: Verify FollowUpTools works standalone**

Run:
```bash
cd /Users/nicolagheza/Developer/nicode-claw && uv run python -c "
from nicode_claw.follow_up import FollowUpTools, _load_intents
tools = FollowUpTools()
print(tools.create_follow_up('test check', 'testing', '1h'))
print(tools.list_follow_ups())
intents = _load_intents()
print(tools.delete_follow_up(intents[0]['id']))
print(tools.list_follow_ups())
"
```

Expected: Creates an intent, lists it, deletes it, shows empty list.

- [ ] **Step 3: Final commit with any fixes if needed**

If any issues were found and fixed in the previous steps, commit them:

```bash
git add -A
git commit -m "fix: address issues found during verification"
```
