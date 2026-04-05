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
