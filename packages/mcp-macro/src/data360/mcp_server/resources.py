"""Resources for the Data360 MCP Server.

Exposes minimal static context resources for the research agent.
"""

import json
from datetime import datetime

from data360.providers import get_database_mapping

from ._server_definition import mcp
from .prompts import SYSTEM_PROMPT


@mcp.resource("data360://system-prompt")
async def system_prompt_resource() -> str:
    """System prompt with tool-loop guidance for agent integration."""
    return SYSTEM_PROMPT


@mcp.resource("data360://context")
async def context_resource() -> str:
    """Runtime context including current date. Read this to know today date."""
    return json.dumps(
        {
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_year": datetime.now().year,
            "note": "Use current_year to calculate last N years queries",
        },
        indent=2,
    )


@mcp.resource("data360://databases")
async def databases_resource() -> str:
    """List of available Data360 databases."""
    db_mapping = await get_database_mapping()
    formatted = {"databases": [{"id": k, "name": v} for k, v in db_mapping.items()]}
    return json.dumps(formatted, indent=2)