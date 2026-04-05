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
