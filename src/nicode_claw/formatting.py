from __future__ import annotations

import html
import re

from telegram.constants import ParseMode

_RE_CODE_BLOCK = re.compile(r"```\w*\n(.*?)```", re.DOTALL)
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_HEADER = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_RE_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*")
_RE_BOLD_UNDER = re.compile(r"__(.+?)__")
_RE_ITALIC_STAR = re.compile(r"(?<!\w)\*([^*]+?)\*(?!\w)")
_RE_ITALIC_UNDER = re.compile(r"(?<!\w)_([^_]+?)_(?!\w)")
_RE_STRIKE = re.compile(r"~~(.+?)~~")
_RE_BLOCKQUOTE = re.compile(r"^>\s?(.+)$", re.MULTILINE)
_RE_LIST_ITEM = re.compile(r"^[-*]\s+", re.MULTILINE)


def md_to_telegram_html(text: str) -> str:
    """Convert common Markdown to Telegram-supported HTML."""
    code_blocks: list[str] = []

    def _save_code_block(m):
        code_blocks.append(html.escape(m.group(1)))
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = _RE_CODE_BLOCK.sub(_save_code_block, text)

    inline_codes: list[str] = []

    def _save_inline(m):
        inline_codes.append(html.escape(m.group(1)))
        return f"\x00INLINE{len(inline_codes) - 1}\x00"

    text = _RE_INLINE_CODE.sub(_save_inline, text)

    text = html.escape(text)

    text = _RE_HEADER.sub(r"<b>\1</b>", text)
    text = _RE_BOLD_STAR.sub(r"<b>\1</b>", text)
    text = _RE_BOLD_UNDER.sub(r"<b>\1</b>", text)
    text = _RE_ITALIC_STAR.sub(r"<i>\1</i>", text)
    text = _RE_ITALIC_UNDER.sub(r"<i>\1</i>", text)
    text = _RE_STRIKE.sub(r"<s>\1</s>", text)
    text = _RE_BLOCKQUOTE.sub(r"\1", text)
    text = _RE_LIST_ITEM.sub("• ", text)

    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{i}\x00", f"<pre>{block}</pre>")
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00INLINE{i}\x00", f"<code>{code}</code>")

    return text


async def reply_formatted(bot, chat_id: int, text: str) -> None:
    """Send with Telegram HTML formatting, falling back to plain text."""
    try:
        formatted = md_to_telegram_html(text)
        await bot.send_message(chat_id=chat_id, text=formatted, parse_mode=ParseMode.HTML)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text)
