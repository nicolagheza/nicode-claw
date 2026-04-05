from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    mode: str  # "polling" or "webhook"
    webhook_url: str | None = None
    allowed_user_ids: list[int] | None = None
    db_path: str = "data/nicode_claw.db"
    model_provider: str = "openai"
    model_id: str = "gpt-5.4"
    google_stitch_api_key: str = ""
    quiet_hours_start: int = 23
    quiet_hours_end: int = 7
    max_proactive_messages_per_hour: int = 5
    reflection_interval_minutes: int = 15

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        api_key = os.environ.get("OPENAI_API_KEY")

        if not token or not api_key:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set"
            )

        raw_ids = os.environ.get("ALLOWED_USER_IDS", "")
        allowed_ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip()] or None

        return cls(
            telegram_bot_token=token,
            openai_api_key=api_key,
            mode=os.environ.get("MODE", "polling"),
            webhook_url=os.environ.get("WEBHOOK_URL") or None,
            allowed_user_ids=allowed_ids,
            db_path=os.environ.get("DB_PATH", "data/nicode_claw.db"),
            model_provider=os.environ.get("MODEL_PROVIDER", "openai"),
            model_id=os.environ.get("MODEL_ID", "gpt-5.4"),
            google_stitch_api_key=os.environ.get("GOOGLE_STITCH_API_KEY", ""),
            quiet_hours_start=int(os.environ.get("QUIET_HOURS_START", "23")),
            quiet_hours_end=int(os.environ.get("QUIET_HOURS_END", "7")),
            max_proactive_messages_per_hour=int(os.environ.get("MAX_PROACTIVE_MESSAGES_PER_HOUR", "5")),
            reflection_interval_minutes=int(os.environ.get("REFLECTION_INTERVAL_MINUTES", "15")),
        )
