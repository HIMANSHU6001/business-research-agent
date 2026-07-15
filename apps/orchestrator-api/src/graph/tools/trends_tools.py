import os
import json
import traceback
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
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

        metadata = parsed.get("metadata", {}) if isinstance(parsed, dict) else {}
        raw_data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed
        
        citation_str = None
        if metadata:
            citation_str = f"In-Text: {metadata.get('in_text', '')}\nCitation: {metadata.get('full_citation', '')}"

        catalog_id, _ = await ingest_to_db(
            research_id=research_id,
            artifact_id=artifact_id,
            source_mcp="trends",
            raw_json=raw_data,
            inputs=args,
            citation=citation_str
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
    query: str, config: RunnableConfig, date: str = "today 12-m", geo: str = "US"
) -> str:
    """
    Returns regional interest data for a specific search query using Google Trends.
    
    Args:
        query (str): A SINGLE search term to query (e.g., "Coffee"). Do not use commas.
        date (str): The time range (e.g., "today 12-m", "today 5-y", "today 1-m", "today 3-m", "all", or "YYYY-MM-DD YYYY-MM-DD").
        geo (str): The location for the query (e.g., "US", "IN").
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    args = {"query": query, "date": date, "geo": geo}
    safe_query = "".join(c if c.isalnum() else "_" for c in query.lower())
    artifact_id = f"trends_geo_{safe_query}"
    return await _get_and_ingest_trends_data("interest_by_region", args, research_id, artifact_id)


@tool
async def interest_over_time(
    query: str, config: RunnableConfig, date: str = "today 12-m", geo: str = "US"
) -> str:
    """
    Returns interest over time data (timeseries) for a specific search query using Google Trends.
    
    Args:
        query (str): A SINGLE search term to query (e.g., "Coffee"). Do not use commas.
        date (str): The time range (e.g., "today 12-m", "today 5-y", "today 1-m", "today 3-m", "all", or "YYYY-MM-DD YYYY-MM-DD").
        geo (str): The location for the query (e.g., "US", "IN").
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    args = {"query": query, "date": date, "geo": geo}
    safe_query = "".join(c if c.isalnum() else "_" for c in query.lower())
    artifact_id = f"trends_time_{safe_query}"
    return await _get_and_ingest_trends_data("interest_over_time", args, research_id, artifact_id)
