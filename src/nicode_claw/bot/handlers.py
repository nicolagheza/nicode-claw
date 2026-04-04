from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from nicode_claw.agent.agent import process_message, transcribe_audio
from nicode_claw.bot.media import download_file
from nicode_claw.context import AppContext
from nicode_claw.formatting import reply_formatted

logger = logging.getLogger(__name__)

_ERROR_MSG = "Mi dispiace, qualcosa è andato storto. Riprova."


def _get_ctx(context: ContextTypes.DEFAULT_TYPE) -> AppContext:
    return context.bot_data["ctx"]


def _is_allowed(ctx: AppContext, update: Update) -> bool:
    allowed = ctx.settings.allowed_user_ids
    if allowed is None:
        return True
    user = update.effective_user
    return user is not None and user.id in allowed


async def _handle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str,
    *,
    images: list[bytes] | None = None,
) -> None:
    """Common handler logic: auth check, set context, call agent, reply."""
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    try:
        ctx.telegram_tools.set_context(context.bot, chat_id, asyncio.get_running_loop())
        response = await process_message(
            ctx.agent, prompt, user_id=user_id, session_id=str(chat_id), images=images
        )
        await reply_formatted(context.bot, chat_id, response)
    except Exception:
        logger.exception("Error processing message")
        await update.message.reply_text(_ERROR_MSG)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    await update.message.reply_text(
        "Ciao! Sono il tuo assistente AI. Inviami un messaggio, "
        "un'immagine o un audio e ti rispondo."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle(update, context, update.message.text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    photo = update.message.photo[-1]
    caption = update.message.caption or "Describe this image."
    image_bytes = await download_file(context.bot, photo.file_id)
    await _handle(update, context, caption, images=[image_bytes])


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    doc = update.message.document
    caption = update.message.caption or ""
    file_bytes = await download_file(context.bot, doc.file_id)
    text_content = file_bytes.decode("utf-8", errors="replace")
    prompt = f"{caption}\n\nDocument content:\n{text_content}" if caption else f"Analyze this document:\n{text_content}"
    await _handle(update, context, prompt)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = _get_ctx(context)
    if not _is_allowed(ctx, update):
        return
    audio = update.message.audio or update.message.voice
    caption = update.message.caption or ""
    audio_bytes = await download_file(context.bot, audio.file_id)
    transcription = await transcribe_audio(ctx.openai_client, audio_bytes)
    await update.message.reply_text(f"\U0001f399 Trascrizione:\n{transcription}")
    prompt = f"{caption}\n\nAudio transcription:\n{transcription}" if caption else transcription
    await _handle(update, context, prompt)
