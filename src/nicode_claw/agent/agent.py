from __future__ import annotations

import io

from pathlib import Path

import os

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
from agno.tools.python import PythonTools
from agno.tools.shell import ShellTools
from agno.tools.mcp import MCPTools
from agno.tools.mcp.params import StreamableHTTPClientParams
from agno.tools.yfinance import YFinanceTools

from nicode_claw.bot.telegram_tools import TelegramTools
from nicode_claw.install_tools import InstallTools
from nicode_claw.scheduler import SchedulerTools

telegram_tools = TelegramTools()
scheduler_tools = SchedulerTools()
_openai_client: openai.AsyncOpenAI | None = None

_stitch_mcp: MCPTools | None = None


async def connect_mcp() -> MCPTools:
    global _stitch_mcp
    _stitch_mcp = MCPTools(
        transport="streamable-http",
        server_params=StreamableHTTPClientParams(
            url="https://stitch.googleapis.com/mcp",
            headers={"X-Goog-Api-Key": os.environ.get("GOOGLE_STITCH_API_KEY", "")},
        ),
        refresh_connection=True,
    )
    await _stitch_mcp.connect()
    return _stitch_mcp


async def disconnect_mcp() -> None:
    if _stitch_mcp is not None:
        await _stitch_mcp.close()


def _get_model():
    provider = os.environ.get("MODEL_PROVIDER", "openai")
    model_id = os.environ.get("MODEL_ID", "gpt-5.4")
    if provider == "openrouter":
        return OpenRouter(id=model_id)
    return OpenAIChat(id=model_id)


def create_agent(db_path: str = "data/nicode_claw.db", mcp_tools: MCPTools | None = None) -> Agent:
    db = SqliteDb(db_file=db_path)

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
        model=_get_model(),
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


async def transcribe_audio(audio_bytes: bytes) -> str:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.ogg"
    transcript = await _openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text
