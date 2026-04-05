from __future__ import annotations

from dataclasses import dataclass

import openai
from agno.agent import Agent
from agno.tools.mcp import MCPTools

from nicode_claw.bot.telegram_tools import TelegramTools
from nicode_claw.config import Settings
from nicode_claw.follow_up import FollowUpTools
from nicode_claw.scheduler import SchedulerTools


@dataclass
class AppContext:
    settings: Settings
    agent: Agent
    telegram_tools: TelegramTools
    scheduler_tools: SchedulerTools
    openai_client: openai.AsyncOpenAI
    follow_up_tools: FollowUpTools | None = None
    mcp_tools: MCPTools | None = None
