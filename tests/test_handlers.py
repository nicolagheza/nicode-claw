import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_update(chat_id=123, text="hello", photo=None, document=None, audio=None, voice=None):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.photo = photo
    update.message.document = document
    update.message.audio = audio
    update.message.voice = voice
    update.message.caption = "test caption"
    update.message.reply_text = AsyncMock()
    return update


def _make_context():
    context = MagicMock()
    context.bot = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_start_command():
    from nicode_claw.bot.handlers import start_command

    update = _make_update()
    context = _make_context()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert len(call_args) > 0


@pytest.mark.asyncio
async def test_reset_command():
    from nicode_claw.bot.handlers import reset_command

    update = _make_update()
    context = _make_context()

    await reset_command(update, context)

    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
@patch("nicode_claw.bot.handlers.process_message")
async def test_handle_text(mock_process):
    from nicode_claw.bot.handlers import handle_text, set_agent

    set_agent(MagicMock())
    mock_process.return_value = "Agent response"
    update = _make_update(text="hello agent")
    context = _make_context()

    await handle_text(update, context)

    mock_process.assert_called_once()
    update.message.reply_text.assert_called_once_with("Agent response")


@pytest.mark.asyncio
@patch("nicode_claw.bot.handlers.download_file")
@patch("nicode_claw.bot.handlers.process_image")
async def test_handle_photo(mock_process_image, mock_download):
    from nicode_claw.bot.handlers import handle_photo, set_agent

    set_agent(MagicMock())
    mock_download.return_value = b"image-bytes"
    mock_process_image.return_value = "I see a photo."

    photo = MagicMock()
    photo.file_id = "photo-file-id"
    update = _make_update(photo=[photo])
    context = _make_context()

    await handle_photo(update, context)

    mock_download.assert_called_once_with(context.bot, "photo-file-id")
    mock_process_image.assert_called_once()
    update.message.reply_text.assert_called_once_with("I see a photo.")
