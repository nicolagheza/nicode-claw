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
