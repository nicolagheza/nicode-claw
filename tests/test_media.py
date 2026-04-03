import pytest
from unittest.mock import AsyncMock, MagicMock
from io import BytesIO

from nicode_claw.bot.media import download_file


@pytest.mark.asyncio
async def test_download_file():
    mock_file = AsyncMock()
    mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"file-content"))

    mock_bot = AsyncMock()
    mock_bot.get_file = AsyncMock(return_value=mock_file)

    result = await download_file(mock_bot, "file-id-123")

    assert result == b"file-content"
    mock_bot.get_file.assert_called_once_with("file-id-123")
