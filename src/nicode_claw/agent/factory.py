from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
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

from nicode_claw.core.config import Settings
from nicode_claw.tools.follow_up import FollowUpTools
from nicode_claw.tools.install import InstallTools
from nicode_claw.tools.telegram import TelegramTools

if TYPE_CHECKING:
    from nicode_claw.tools.scheduler import SchedulerTools


def create_mcp(settings: Settings) -> MCPTools:
    return MCPTools(
        transport="streamable-http",
        server_params=StreamableHTTPClientParams(
            url="https://stitch.googleapis.com/mcp",
            headers={"X-Goog-Api-Key": settings.google_stitch_api_key},
            timeout=timedelta(seconds=120),
        ),
        timeout_seconds=120,
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
    follow_up_tools: FollowUpTools | None = None,
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
    if follow_up_tools:
        tools.append(follow_up_tools)
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
            "When a conversation involves something that might benefit from a follow-up (a task in progress, a decision pending, something the user is tracking, an interesting topic), use create_follow_up to schedule one. Be eager — it's better to create a follow-up and have it turn out to be nothing than to miss something the user would have appreciated.",
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
