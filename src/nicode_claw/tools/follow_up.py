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

        # Deduplicate: if an active intent with a similar 'what' exists, update it instead
        what_lower = what.lower()
        for existing in intents:
            if existing["status"] in ("pending", "checked") and existing["what"].lower() == what_lower:
                existing["check_at"] = parse_check_in(check_in).isoformat()
                existing["priority"] = priority
                save_intents(intents)
                return f"Follow-up already exists (ID: {existing['id']}), updated next check time."

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
