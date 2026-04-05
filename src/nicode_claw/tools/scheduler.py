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
