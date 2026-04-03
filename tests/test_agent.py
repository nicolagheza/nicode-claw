import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_create_agent():
    from nicode_claw.agent.agent import create_agent
    from agno.models.openai import OpenAIChat

    with patch("nicode_claw.agent.agent.OpenAIChat", spec=OpenAIChat) as mock_model:
        agent = create_agent()
        assert agent is not None
        mock_model.assert_called_once()


@pytest.mark.asyncio
async def test_process_message():
    from nicode_claw.agent.agent import process_message

    mock_agent = MagicMock()
    mock_run_output = MagicMock()
    mock_run_output.content = "Hello back!"
    mock_agent.arun = AsyncMock(return_value=mock_run_output)

    result = await process_message(mock_agent, "Hello", session_id="user_123")

    assert result == "Hello back!"
    mock_agent.arun.assert_called_once_with("Hello", session_id="user_123")


@pytest.mark.asyncio
async def test_process_image():
    from nicode_claw.agent.agent import process_image

    mock_agent = MagicMock()
    mock_run_output = MagicMock()
    mock_run_output.content = "I see a cat."
    mock_agent.arun = AsyncMock(return_value=mock_run_output)

    result = await process_image(
        mock_agent,
        image_bytes=b"fake-image-data",
        caption="What is this?",
        session_id="user_123",
    )

    assert result == "I see a cat."
    mock_agent.arun.assert_called_once()
    call_kwargs = mock_agent.arun.call_args
    assert call_kwargs.kwargs["images"] is not None
    assert call_kwargs.kwargs["session_id"] == "user_123"


@pytest.mark.asyncio
async def test_process_audio():
    from nicode_claw.agent.agent import process_audio

    mock_agent = MagicMock()
    mock_run_output = MagicMock()
    mock_run_output.content = "You said hello."
    mock_agent.arun = AsyncMock(return_value=mock_run_output)

    result = await process_audio(
        mock_agent,
        audio_bytes=b"fake-audio-data",
        caption="",
        session_id="user_123",
    )

    assert result == "You said hello."
    mock_agent.arun.assert_called_once()
