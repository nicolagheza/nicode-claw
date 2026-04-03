from __future__ import annotations

from telegram import Bot


async def download_file(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    data = await file.download_as_bytearray()
    return bytes(data)
