from __future__ import annotations

import asyncio
import logging

import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from nicode_claw.agent.agent import create_mcp, create_agent
from nicode_claw.bot.handlers import (
    handle_audio,
    handle_document,
    handle_photo,
    handle_text,
    start_command,
)
from nicode_claw.bot.telegram_tools import TelegramTools
from nicode_claw.config import Settings
from nicode_claw.context import AppContext
from nicode_claw.follow_up import FollowUpTools
from nicode_claw.reflection import run_reflection_loop
from nicode_claw.scheduler import SchedulerTools, run_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings.from_env()

    telegram_tools = TelegramTools()
    scheduler_tools = SchedulerTools()
    follow_up_tools = FollowUpTools()

    async def post_init(application: Application) -> None:
        mcp = create_mcp(settings) if settings.google_stitch_api_key else None
        agent = create_agent(settings, telegram_tools, scheduler_tools, follow_up_tools, mcp)
        ctx = AppContext(
            settings=settings,
            agent=agent,
            telegram_tools=telegram_tools,
            scheduler_tools=scheduler_tools,
            openai_client=openai.AsyncOpenAI(),
            follow_up_tools=follow_up_tools,
            mcp_tools=mcp,
        )
        application.bot_data["ctx"] = ctx
        if settings.allowed_user_ids:
            chat_id = settings.allowed_user_ids[0]
            user_id = str(chat_id)
            asyncio.create_task(
                run_scheduler(ctx, application.bot, chat_id, user_id)
            )
            asyncio.create_task(
                run_reflection_loop(settings, agent, application.bot, chat_id)
            )

    async def post_shutdown(application: Application) -> None:
        ctx: AppContext | None = application.bot_data.get("ctx")
        if ctx and ctx.mcp_tools:
            await ctx.mcp_tools.close()

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
