from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from nicode_claw.agent.agent import connect_mcp, create_agent, disconnect_mcp
from nicode_claw.scheduler import run_scheduler
from nicode_claw.bot.handlers import (
    handle_audio,
    handle_document,
    handle_photo,
    handle_text,
    set_agent,
    set_allowed_user_ids,
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
    set_allowed_user_ids(settings.allowed_user_ids)

    async def post_init(application: Application) -> None:
        mcp = await connect_mcp()
        agent = create_agent(db_path=settings.db_path, mcp_tools=mcp)
        set_agent(agent)
        if settings.allowed_user_ids:
            chat_id = settings.allowed_user_ids[0]
            user_id = str(chat_id)
            asyncio.create_task(
                run_scheduler(agent, application.bot, chat_id, user_id)
            )

    async def post_shutdown(application: Application) -> None:
        await disconnect_mcp()

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
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
