from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from nicode_claw.agent.agent import process_audio, process_image, process_message
from nicode_claw.bot.media import download_file

logger = logging.getLogger(__name__)

# The agent instance is set at startup via set_agent()
_agent = None


def set_agent(agent) -> None:
    global _agent
    _agent = agent


def _get_agent():
    if _agent is None:
        raise RuntimeError("Agent not initialized. Call set_agent() first.")
    return _agent


async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await update.message.reply_text(
        "Ciao! Sono il tuo assistente AI. Inviami un messaggio, "
        "un'immagine o un audio e ti rispondo."
    )


async def reset_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await update.message.reply_text("Conversazione resettata.")


async def handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = str(update.effective_chat.id)
    text = update.message.text

    try:
        response = await process_message(
            _get_agent(), text, session_id=chat_id
        )
        await update.message.reply_text(response)
    except Exception:
        logger.exception("Error processing text message")
        await update.message.reply_text(
            "Mi dispiace, qualcosa è andato storto. Riprova."
        )


async def handle_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = str(update.effective_chat.id)
    photo = update.message.photo[-1]  # highest resolution
    caption = update.message.caption or ""

    try:
        image_bytes = await download_file(context.bot, photo.file_id)
        response = await process_image(
            _get_agent(),
            image_bytes=image_bytes,
            caption=caption,
            session_id=chat_id,
        )
        await update.message.reply_text(response)
    except Exception:
        logger.exception("Error processing photo")
        await update.message.reply_text(
            "Mi dispiace, qualcosa è andato storto. Riprova."
        )


async def handle_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = str(update.effective_chat.id)
    doc = update.message.document
    caption = update.message.caption or ""

    try:
        file_bytes = await download_file(context.bot, doc.file_id)
        text_content = file_bytes.decode("utf-8", errors="replace")
        prompt = f"{caption}\n\nDocument content:\n{text_content}" if caption else f"Analyze this document:\n{text_content}"
        response = await process_message(
            _get_agent(), prompt, session_id=chat_id
        )
        await update.message.reply_text(response)
    except Exception:
        logger.exception("Error processing document")
        await update.message.reply_text(
            "Mi dispiace, qualcosa è andato storto. Riprova."
        )


async def handle_audio(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = str(update.effective_chat.id)
    audio = update.message.audio or update.message.voice
    caption = update.message.caption or ""

    try:
        audio_bytes = await download_file(context.bot, audio.file_id)
        response = await process_audio(
            _get_agent(),
            audio_bytes=audio_bytes,
            caption=caption,
            session_id=chat_id,
        )
        await update.message.reply_text(response)
    except Exception:
        logger.exception("Error processing audio")
        await update.message.reply_text(
            "Mi dispiace, qualcosa è andato storto. Riprova."
        )
