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
