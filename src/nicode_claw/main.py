from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from nicode_claw.agent.agent import create_agent
from nicode_claw.bot.handlers import (
    handle_audio,
    handle_document,
    handle_photo,
    handle_text,
    reset_command,
    set_agent,
    start_command,
)
from nicode_claw.config import Settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings.from_env()

    agent = create_agent()
    set_agent(agent)

    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(
        MessageHandler(filters.AUDIO | filters.VOICE, handle_audio)
    )

    if settings.mode == "webhook":
        logger.info("Starting in webhook mode: %s", settings.webhook_url)
        app.run_webhook(
            listen="0.0.0.0",
            port=8443,
            webhook_url=settings.webhook_url,
        )
    else:
        logger.info("Starting in polling mode")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
