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

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        api_key = os.environ.get("OPENAI_API_KEY")

        if not token or not api_key:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set"
            )

        return cls(
            telegram_bot_token=token,
            openai_api_key=api_key,
            mode=os.environ.get("MODE", "polling"),
            webhook_url=os.environ.get("WEBHOOK_URL") or None,
        )
