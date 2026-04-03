from __future__ import annotations

from agno.agent import Agent
from agno.media import Audio, Image
from agno.models.openai import OpenAIChat


def create_agent() -> Agent:
    return Agent(
        model=OpenAIChat(id="gpt-4o"),
        description="A helpful AI assistant available via Telegram.",
        instructions=[
            "You are a helpful assistant.",
            "Respond concisely and clearly.",
            "You can analyze images, documents, and audio.",
        ],
        markdown=True,
        add_history_to_context=True,
        num_history_runs=10,
    )


async def process_message(
    agent: Agent,
    text: str,
    *,
    session_id: str,
) -> str:
    run_output = await agent.arun(text, session_id=session_id)
    return run_output.content


async def process_image(
    agent: Agent,
    *,
    image_bytes: bytes,
    caption: str,
    session_id: str,
) -> str:
    prompt = caption if caption else "Describe this image."
    image = Image(content=image_bytes)
    run_output = await agent.arun(
        prompt, images=[image], session_id=session_id
    )
    return run_output.content


async def process_audio(
    agent: Agent,
    *,
    audio_bytes: bytes,
    caption: str,
    session_id: str,
) -> str:
    prompt = caption if caption else "What is in this audio?"
    audio = Audio(content=audio_bytes, format="ogg")
    run_output = await agent.arun(
        prompt, audio=[audio], session_id=session_id
    )
    return run_output.content
