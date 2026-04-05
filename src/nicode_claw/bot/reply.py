from __future__ import annotations

from telegram.constants import ParseMode

from nicode_claw.core.formatting import md_to_telegram_html


async def reply_formatted(bot, chat_id: int, text: str) -> None:
    """Send with Telegram HTML formatting, falling back to plain text."""
    try:
        formatted = md_to_telegram_html(text)
        await bot.send_message(chat_id=chat_id, text=formatted, parse_mode=ParseMode.HTML)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text)
