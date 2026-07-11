import os
import json
import traceback
from langchain_core.tools import tool
from context.workspace import ingest_to_db
from mcp_clients import call_mcp_tool

TRENDS_MCP_URL = os.getenv("TRENDS_MCP_URL", "http://mcp-trends:8000/sse")


async def _get_and_ingest_trends_data(
    tool_name: str,
    args: dict,
    research_id: str,
    artifact_id: str
) -> str:
    """Helper to fetch trends data and ingest it into the workspace database."""
    raw_response = await call_mcp_tool(TRENDS_MCP_URL, tool_name, args)
    try:
        parsed = json.loads(raw_response)
        if isinstance(parsed, dict) and "error" in parsed:
            return f"Error from SerpApi: {parsed['error'].get('message', 'Unknown error')}"

        catalog_id, _ = await ingest_to_db(
            research_id=research_id,
            artifact_id=artifact_id,
            source_mcp="trends",
            raw_json=parsed,
            inputs=args,
        )
        return (
            f"Successfully ingested {tool_name} data into workspace. "
            f"Artifact ID: {artifact_id}."
        )
    except (json.JSONDecodeError, Exception) as e:
        tb = traceback.format_exc()
        print(f"DEBUG {tool_name} exception:\n{tb}", flush=True)
        return f"{tool_name} completed but interception failed: {e}. Raw response length: {len(raw_response)} chars."


@tool
async def interest_by_region(
    query: str, research_id: str, date: str = "today 12-m", geo: str = "US"
) -> str:
    """
    Returns regional interest data for a specific search query using Google Trends.
    
    Args:
        query (str): A SINGLE search term to query (e.g., "Coffee"). Do not use commas.
        research_id (str): The UUID of the research context.
        date (str): The time range. Must be one of: "today 12-m", "today 1-m", "today 3-m". No custom dates.
        geo (str): The location for the query (e.g., "US", "IN").
    """
    args = {"query": query, "date": date, "geo": geo}
    safe_query = "".join(c if c.isalnum() else "_" for c in query.lower())
    artifact_id = f"trends_geo_{safe_query}"
    return await _get_and_ingest_trends_data("interest_by_region", args, research_id, artifact_id)


@tool
async def interest_over_time(
    query: str, research_id: str, date: str = "today 12-m", geo: str = "US"
) -> str:
    """
    Returns interest over time data (timeseries) for a specific search query using Google Trends.
    
    Args:
        query (str): A SINGLE search term to query (e.g., "Coffee"). Do not use commas.
        research_id (str): The UUID of the research context.
        date (str): The time range. Must be one of: "today 12-m", "today 1-m", "today 3-m". No custom dates.
        geo (str): The location for the query (e.g., "US", "IN").
    """
    args = {"query": query, "date": date, "geo": geo}
    safe_query = "".join(c if c.isalnum() else "_" for c in query.lower())
    artifact_id = f"trends_time_{safe_query}"
    return await _get_and_ingest_trends_data("interest_over_time", args, research_id, artifact_id)
