from __future__ import annotations

import json
from pathlib import Path

JOBS_FILE = Path("data/scheduled_jobs.json")


def load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    return json.loads(JOBS_FILE.read_text())


def save_jobs(jobs: list[dict]) -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))
