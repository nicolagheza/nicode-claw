from __future__ import annotations

import io

import openai
from agno.agent import Agent
from agno.media import Image


async def process_message(
    agent: Agent,
    text: str,
    *,
    user_id: str,
    session_id: str,
    images: list[bytes] | None = None,
) -> str:
    image_objects = [Image(content=b) for b in images] if images else []
    run_output = await agent.arun(
        text,
        images=image_objects or None,
        user_id=user_id,
        session_id=session_id,
    )
    return run_output.content


async def transcribe_audio(client: openai.AsyncOpenAI, audio_bytes: bytes) -> str:
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.ogg"
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text
