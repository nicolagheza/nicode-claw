from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from agno.tools.toolkit import Toolkit

logger = logging.getLogger(__name__)

JOBS_FILE = Path("data/scheduled_jobs.json")


def _load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    return json.loads(JOBS_FILE.read_text())


def _save_jobs(jobs: list[dict]) -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))


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
        jobs = _load_jobs()
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "name": name or prompt[:50],
            "cron": cron,
            "prompt": prompt,
            "created_at": datetime.now().isoformat(),
        }
        jobs.append(job)
        _save_jobs(jobs)
        return f"Job '{job['name']}' created with ID {job_id}. Schedule: {cron}"

    def list_scheduled_jobs(self) -> str:
        """List all scheduled jobs.

        Returns:
            A formatted list of all scheduled jobs.
        """
        jobs = _load_jobs()
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
        jobs = _load_jobs()
        new_jobs = [j for j in jobs if j["id"] != job_id]
        if len(new_jobs) == len(jobs):
            return f"Job with ID {job_id} not found."
        _save_jobs(new_jobs)
        return f"Job {job_id} deleted."


def _cron_matches(cron: str, now: datetime) -> bool:
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


async def run_scheduler(agent, bot, chat_id: int, user_id: str) -> None:
    from nicode_claw.agent.agent import process_message, telegram_tools
    from nicode_claw.bot.handlers import reply_formatted

    logger.info("Scheduler started")
    while True:
        try:
            await asyncio.sleep(60)
            now = datetime.now()
            jobs = _load_jobs()
            for job in jobs:
                if _cron_matches(job["cron"], now):
                    logger.info("Running scheduled job: %s", job["name"])
                    try:
                        telegram_tools.set_context(bot, chat_id, asyncio.get_running_loop())
                        response = await process_message(
                            agent,
                            f"[Scheduled task: {job['name']}]\n{job['prompt']}",
                            user_id=user_id,
                            session_id=str(chat_id),
                        )
                        await reply_formatted(bot, chat_id, response)
                    except Exception:
                        logger.exception("Error running scheduled job %s", job["id"])
        except Exception:
            logger.exception("Scheduler error")
