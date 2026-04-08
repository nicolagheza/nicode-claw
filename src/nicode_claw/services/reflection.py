from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from agno.agent import Agent

from nicode_claw.storage.intents import (
    get_due_intents,
    parse_check_in,
    prune_expired_intents,
    update_intent,
)
from nicode_claw.bot.reply import reply_formatted

if TYPE_CHECKING:
    from telegram import Bot

    from nicode_claw.core.config import Settings

logger = logging.getLogger(__name__)

REFLECTION_INSTRUCTIONS = """You are in reflection mode, reviewing a follow-up intent.

Steps:
1. Use your tools to check the intent (search, finance data, etc.)
2. Decide: is this worth messaging the user about?
3. If YES — write a short, ready-to-send message for the user.
   If NO — just say so.

For "direct_ask" intents, always write a message.
For "silent_check" intents, only write a message if the result is significant.

Message style — use one of these prefixes:
- "💭 Thinking of you — ..." for pattern-based insights
- "🔔 Quick follow-up — ..." for task follow-ups
- "⚡ Heads up — ..." for monitoring alerts"""

# Negative indicators — if the LLM response contains these, it's a NO verdict
_NEGATIVE_PATTERNS = re.compile(
    r"nothing (notable|significant|noteworthy|important|new)"
    r"|no (notable|significant|noteworthy|important|new|relevant)"
    r"|nothing to report"
    r"|no updates?"
    r"|no major"
    r"|not worth"
    r"|I('ll| will) keep (monitoring|watching|checking)"
    r"|keep the follow.up active",
    re.IGNORECASE,
)


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
            f"{REFLECTION_INSTRUCTIONS}\n\n"
            f"---\n\n"
            f"Follow-up intent to process:\n"
            f"- What: {intent['what']}\n"
            f"- Why: {intent['why']}\n"
            f"- Type: {intent['how']}\n"
            f"- Priority: {intent['priority']}\n"
            f"- Checks so far: {intent['checks_done']}/{intent['max_checks']}"
        )

        try:
            run_output = await self._agent.arun(
                prompt,
                user_id="reflection",
                session_id="reflection",
            )
            response = run_output.content
            logger.debug("Reflection response for %s: %s", intent["id"], response[:200])

            is_noteworthy = self._is_noteworthy(response, intent)

            if is_noteworthy:
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
                    logger.warning("Reflection: noteworthy but no message extracted for %s", intent["id"])
                    self._reschedule_intent(intent, "1h")
            else:
                self._reschedule_intent(intent, "1h")

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

    def _is_noteworthy(self, response: str, intent: dict) -> bool:
        """Determine if the agent's response indicates something worth reporting."""
        # "direct_ask" intents are always noteworthy
        if intent["how"] == "direct_ask":
            return True

        # Check for explicit negative indicators
        if _NEGATIVE_PATTERNS.search(response):
            return False

        # Check for explicit verdict lines (works if LLM follows format)
        if re.search(r"verdict\s*:\s*yes", response, re.IGNORECASE):
            return True
        if re.search(r"verdict\s*:\s*no\b", response, re.IGNORECASE):
            return False

        # Heuristic: if the response is substantive (not just a short "nothing found"),
        # and doesn't contain negative patterns, the LLM found something worth reporting.
        # Short responses (< 50 chars) without clear findings are likely "nothing to report".
        stripped = response.strip()
        if len(stripped) < 50:
            return False

        return True

    def _extract_message(self, response: str) -> str | None:
        """Extract or compose the message to send to the user."""
        # Look for explicit MESSAGE: line (with or without markdown)
        for line in response.split("\n"):
            cleaned = re.sub(r"\*+", "", line).strip()
            match = re.match(r"message\s*:\s*(.+)", cleaned, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Look for a line starting with one of our prefixes — that IS the message
        for line in response.split("\n"):
            stripped = line.strip()
            if re.match(r"[💭🔔⚡]", stripped):
                return stripped

        # Fallback: use the full response, stripping meta lines (verdict/reschedule)
        lines = []
        for line in response.split("\n"):
            cleaned = re.sub(r"\*+", "", line).strip()
            if re.match(r"(verdict|reschedule)\s*:", cleaned, re.IGNORECASE):
                continue
            if line.strip():
                lines.append(line.strip())

        content = "\n".join(lines).strip()
        return content if content else None


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
