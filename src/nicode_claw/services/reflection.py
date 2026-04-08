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

REFLECTION_INSTRUCTIONS = """You are in reflection mode. You are reviewing follow-up intents to decide what's worth acting on.

For each intent you receive, you must:
1. Execute the check described in the intent using your available tools (search, finance data, code execution, etc.)
2. Evaluate: is the result noteworthy enough to message the user?
3. Respond with your verdict.

Guidelines:
- Be proactive but respect the user's attention — only recommend messaging if you have something genuinely useful to say.
- A silent check that finds nothing interesting is a success, not a failure.
- For "direct_ask" intents, always recommend messaging (these are explicit follow-up questions).
- For "silent_check" intents, only recommend messaging if the result is significant.
- When recommending a message, compose it ready to send. Use these prefixes:
  - "💭 Thinking of you" — for pattern-based insights
  - "🔔 Quick follow-up" — for task follow-ups
  - "⚡ Heads up" — for monitoring alerts

CRITICAL: You MUST end your response with EXACTLY one of these lines (no markdown, no bold, no extra text on the line):

VERDICT: YES
MESSAGE: <the exact message to send to the user>

or

VERDICT: NO
RESCHEDULE: <relative time like "1h", "6h", "1d", or "expire">

These MUST be the last lines of your response. Do NOT use markdown formatting on these lines."""


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

            # Strip markdown formatting before parsing
            clean = self._strip_markdown(response)

            # Parse the response for verdict
            if self._has_yes_verdict(clean):
                # Extract message
                message = self._extract_message(clean, response)
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
                reschedule = self._extract_reschedule(clean)
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

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Strip markdown bold/italic markers for reliable parsing."""
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        return text

    @staticmethod
    def _has_yes_verdict(clean_response: str) -> bool:
        """Check if the response contains a YES verdict, tolerant of formatting variations."""
        # Explicit "Verdict: YES"
        if re.search(r"verdict\s*:\s*yes", clean_response, re.IGNORECASE):
            return True
        # Explicit "Verdict: NO" means definitely not yes
        if re.search(r"verdict\s*:\s*no\b", clean_response, re.IGNORECASE):
            return False
        # If there's a MESSAGE: line, the LLM intended YES even without saying it
        if re.search(r"^message\s*:", clean_response, re.IGNORECASE | re.MULTILINE):
            return True
        return False

    def _extract_message(self, clean: str, original: str) -> str | None:
        """Extract the message to send from a reflection response."""
        # Look for explicit MESSAGE: line
        for line in clean.split("\n"):
            stripped = line.strip()
            if re.match(r"message\s*:", stripped, re.IGNORECASE):
                return re.sub(r"^message\s*:\s*", "", stripped, flags=re.IGNORECASE).strip()

        # Fallback: take everything after the verdict line, excluding meta lines
        lines = original.split("\n")
        past_verdict = False
        content_lines = []
        for line in lines:
            stripped = line.strip()
            clean_line = self._strip_markdown(stripped)
            if re.match(r"verdict\s*:", clean_line, re.IGNORECASE):
                past_verdict = True
                continue
            if not past_verdict:
                continue
            # Skip meta lines
            if re.match(r"(reschedule|message)\s*:", clean_line, re.IGNORECASE):
                continue
            content_lines.append(stripped)

        content = "\n".join(content_lines).strip()
        return content if content else None

    def _extract_reschedule(self, clean_response: str) -> str:
        """Extract the RESCHEDULE value from a reflection response."""
        for line in clean_response.split("\n"):
            stripped = line.strip()
            match = re.match(r"reschedule\s*:\s*(.+)", stripped, re.IGNORECASE)
            if match:
                return match.group(1).strip().lower()
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
