from __future__ import annotations

import asyncio
import html
import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from nicode_claw.agent.agent import process_message, telegram_tools, transcribe_audio
from nicode_claw.bot.media import download_file

logger = logging.getLogger(__name__)

_agent = None
_allowed_user_ids: set[int] | None = None

_ERROR_MSG = "Mi dispiace, qualcosa è andato storto. Riprova."

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


def set_agent(agent) -> None:
    global _agent
    _agent = agent


def set_allowed_user_ids(user_ids: list[int] | None) -> None:
    global _allowed_user_ids
    _allowed_user_ids = set(user_ids) if user_ids else None


def _get_agent():
    if _agent is None:
        raise RuntimeError("Agent not initialized. Call set_agent() first.")
    return _agent


def _is_allowed(update: Update) -> bool:
    if _allowed_user_ids is None:
        return True
    user = update.effective_user
    return user is not None and user.id in _allowed_user_ids


def md_to_telegram_html(text: str) -> str:
    """Convert common Markdown to Telegram-supported HTML."""
    # Extract code blocks before escaping
    code_blocks: list[str] = []

    def _save_code_block(m):
        code_blocks.append(html.escape(m.group(1)))
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = _RE_CODE_BLOCK.sub(_save_code_block, text)

    # Extract inline code before escaping
    inline_codes: list[str] = []

    def _save_inline(m):
        inline_codes.append(html.escape(m.group(1)))
        return f"\x00INLINE{len(inline_codes) - 1}\x00"

    text = _RE_INLINE_CODE.sub(_save_inline, text)

    # HTML-escape the rest
    text = html.escape(text)

    # Apply formatting
    text = _RE_HEADER.sub(r"<b>\1</b>", text)
    text = _RE_BOLD_STAR.sub(r"<b>\1</b>", text)
    text = _RE_BOLD_UNDER.sub(r"<b>\1</b>", text)
    text = _RE_ITALIC_STAR.sub(r"<i>\1</i>", text)
    text = _RE_ITALIC_UNDER.sub(r"<i>\1</i>", text)
    text = _RE_STRIKE.sub(r"<s>\1</s>", text)
    text = _RE_BLOCKQUOTE.sub(r"\1", text)
    text = _RE_LIST_ITEM.sub("• ", text)

    # Restore code blocks and inline code
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


async def _handle(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, *, images: list[bytes] | None = None) -> None:
    """Common handler logic: auth check, set context, call agent, reply."""
    if not _is_allowed(update):
        return
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    try:
        telegram_tools.set_context(context.bot, chat_id, asyncio.get_running_loop())
        response = await process_message(
            _get_agent(), prompt, user_id=user_id, session_id=str(chat_id), images=images
        )
        await reply_formatted(context.bot, chat_id, response)
    except Exception:
        logger.exception("Error processing message")
        await update.message.reply_text(_ERROR_MSG)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "Ciao! Sono il tuo assistente AI. Inviami un messaggio, "
        "un'immagine o un audio e ti rispondo."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle(update, context, update.message.text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    photo = update.message.photo[-1]
    caption = update.message.caption or "Describe this image."
    image_bytes = await download_file(context.bot, photo.file_id)
    await _handle(update, context, caption, images=[image_bytes])


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    doc = update.message.document
    caption = update.message.caption or ""
    file_bytes = await download_file(context.bot, doc.file_id)
    text_content = file_bytes.decode("utf-8", errors="replace")
    prompt = f"{caption}\n\nDocument content:\n{text_content}" if caption else f"Analyze this document:\n{text_content}"
    await _handle(update, context, prompt)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    audio = update.message.audio or update.message.voice
    caption = update.message.caption or ""
    audio_bytes = await download_file(context.bot, audio.file_id)
    transcription = await transcribe_audio(audio_bytes)
    await update.message.reply_text(f"🎙 Trascrizione:\n{transcription}")
    prompt = f"{caption}\n\nAudio transcription:\n{transcription}" if caption else transcription
    await _handle(update, context, prompt)
