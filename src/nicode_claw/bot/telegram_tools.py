from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agno.tools.toolkit import Toolkit

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


class TelegramTools(Toolkit):

    def __init__(self):
        super().__init__(name="telegram_tools")
        self._chat_id: int | None = None
        self._bot = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.register(self.send_file)

    def set_context(self, bot, chat_id: int, loop: asyncio.AbstractEventLoop) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._loop = loop

    def send_file(self, file_path: str, caption: str = "") -> str:
        """Send a file to the user via Telegram with an optional caption.

        Args:
            file_path: The path to the file to send.
            caption: Optional caption to display under the file.

        Returns:
            A confirmation message or an error message.
        """
        if self._bot is None or self._chat_id is None or self._loop is None:
            return "Error: Telegram context not set."

        path = Path(file_path)
        if not path.exists():
            # Search in common tool directories
            for search_dir in [Path("tmp/files"), Path("tmp/python")]:
                candidate = search_dir / path.name
                if candidate.exists():
                    path = candidate
                    break
            else:
                return f"Error: File not found: {file_path}"

        try:
            with open(path, "rb") as f:
                data = f.read()

            if path.suffix.lower() in IMAGE_EXTENSIONS:
                future = asyncio.run_coroutine_threadsafe(
                    self._bot.send_photo(
                        chat_id=self._chat_id, photo=data, caption=caption or None
                    ),
                    self._loop,
                )
            else:
                future = asyncio.run_coroutine_threadsafe(
                    self._bot.send_document(
                        chat_id=self._chat_id,
                        document=data,
                        filename=path.name,
                        caption=caption or None,
                    ),
                    self._loop,
                )
            future.result(timeout=30)
            return f"File '{path.name}' sent to user."
        except Exception as e:
            logger.exception("Error sending file %s", file_path)
            return f"Error sending file: {e}"
