from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import openai

if TYPE_CHECKING:
    from agno.agent import Agent
    from agno.tools.mcp import MCPTools

    from nicode_claw.tools.follow_up import FollowUpTools
    from nicode_claw.tools.scheduler import SchedulerTools
    from nicode_claw.tools.telegram import TelegramTools

from nicode_claw.core.config import Settings


@dataclass
class AppContext:
    settings: Settings
    agent: Agent
    telegram_tools: TelegramTools
    scheduler_tools: SchedulerTools
    openai_client: openai.AsyncOpenAI
    follow_up_tools: FollowUpTools | None = None
    mcp_tools: MCPTools | None = None
