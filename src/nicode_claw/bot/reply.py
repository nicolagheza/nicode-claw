from __future__ import annotations

from telegram.constants import ParseMode

from nicode_claw.core.formatting import md_to_telegram_html

TELEGRAM_MAX_LENGTH = 4096


def _split_text(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Split text into chunks that fit within Telegram's message limit.

    Splits at paragraph boundaries (\n\n) first, then at line boundaries (\n),
    and finally at the hard limit if a single line exceeds it.
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to split at a double newline (paragraph boundary)
        split_pos = remaining.rfind("\n\n", 0, max_length)
        if split_pos != -1:
            chunks.append(remaining[:split_pos])
            remaining = remaining[split_pos + 2:]
            continue

        # Try to split at a single newline
        split_pos = remaining.rfind("\n", 0, max_length)
        if split_pos != -1:
            chunks.append(remaining[:split_pos])
            remaining = remaining[split_pos + 1:]
            continue

        # Hard split at max_length
        chunks.append(remaining[:max_length])
        remaining = remaining[max_length:]

    return chunks


async def reply_formatted(bot, chat_id: int, text: str) -> None:
    """Send with Telegram HTML formatting, falling back to plain text."""
    try:
        formatted = md_to_telegram_html(text)
        for chunk in _split_text(formatted):
            await bot.send_message(
                chat_id=chat_id, text=chunk, parse_mode=ParseMode.HTML
            )
    except Exception:
        for chunk in _split_text(text):
            await bot.send_message(chat_id=chat_id, text=chunk)
