from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

import openai
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.media import Image
from agno.models.openai import OpenAIChat
from agno.models.openrouter import OpenRouter
from agno.skills import Skills, LocalSkills
from agno.tools.csv_toolkit import CsvTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.file import FileTools
from agno.tools.hackernews import HackerNewsTools
from agno.tools.mcp import MCPTools
from agno.tools.mcp.params import StreamableHTTPClientParams
from agno.tools.python import PythonTools
from agno.tools.shell import ShellTools
from agno.tools.yfinance import YFinanceTools

from nicode_claw.bot.telegram_tools import TelegramTools
from nicode_claw.config import Settings
from nicode_claw.install_tools import InstallTools

if TYPE_CHECKING:
    from nicode_claw.scheduler import SchedulerTools


def create_mcp(settings: Settings) -> MCPTools:
    return MCPTools(
        transport="streamable-http",
        server_params=StreamableHTTPClientParams(
            url="https://stitch.googleapis.com/mcp",
            headers={"X-Goog-Api-Key": settings.google_stitch_api_key},
        ),
        refresh_connection=True,
    )


def _get_model(settings: Settings):
    if settings.model_provider == "openrouter":
        return OpenRouter(id=settings.model_id)
    return OpenAIChat(id=settings.model_id)


def create_agent(
    settings: Settings,
    telegram_tools: TelegramTools,
    scheduler_tools: SchedulerTools,
    mcp_tools: MCPTools | None = None,
) -> Agent:
    db = SqliteDb(db_file=settings.db_path)

    tools = [
        DuckDuckGoTools(),
        HackerNewsTools(),
        CsvTools(),
        FileTools(base_dir=Path("tmp/files")),
        PythonTools(
            base_dir=Path("tmp/python"),
            exclude_tools=["pip_install_package", "uv_pip_install_package"],
        ),
        ShellTools(),
        YFinanceTools(),
        InstallTools(),
        telegram_tools,
        scheduler_tools,
    ]
    if mcp_tools:
        tools.append(mcp_tools)

    return Agent(
        model=_get_model(settings),
        description="A helpful AI assistant called nicodeclaw and you live in your creator's computer. You communicate via Telegram.",
        instructions=[
            "You are a helpful assistant.",
            "Respond concisely and clearly.",
            "You can analyze images, documents, and audio.",
            "When you generate a file (chart, image, CSV, etc.), use the send_file tool to send it to the user.",
            "When you need to install a Python package, use the install_package tool.",
            "Files saved by FileTools are in tmp/files/. Files saved by PythonTools are in tmp/python/. Use the full path when calling send_file.",
            "For complex coding tasks, you can delegate to Claude Code via shell: claude -p 'your prompt here' --dangerously-skip-permissions --output-format text",
        ],
        tools=tools,
        markdown=True,
        db=db,
        add_history_to_context=True,
        num_history_runs=10,
        enable_agentic_memory=True,
        skills=Skills(loaders=[LocalSkills(".agents/skills")]),
        debug_mode=True,
    )


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
