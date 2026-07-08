import json
import asyncio
from langchain_core.tools import tool
from src.context.workspace import ingest_to_db
from src.mcp_clients import call_mcp_tool

MACRO_MCP_URL = "http://mcp-macro:8000/sse"

# ---------------------------------------------------------------------------
# Pass-through tools (NOT intercepted — result returned directly to agent)
# ---------------------------------------------------------------------------

@tool
async def data360_search_indicators(
    query: str,
    required_country: str = None,
    limit: int = 5,
    database: str = None,
) -> str:
    """Search for World Bank Data360 indicators by topic.

    Use this first to discover the correct indicator ID and database ID before fetching data.
    Returns enriched metadata including indicator IDs, names, and coverage.

    Args:
        query: Topic to search for (e.g. "GDP per capita", "inflation", "unemployment").
               Avoid parentheses or dollar signs in the query.
        required_country: ISO country code to filter coverage (e.g. "IND", "USA").
        limit: Max results to return (default 5).
        database: Optional database filter (e.g. "wdi", "wgi").
    """
    args = {"query": query, "limit": limit}
    if required_country:
        args["required_country"] = required_country
    if database:
        args["database"] = database
    return await call_mcp_tool(MACRO_MCP_URL, "data360_search_indicators", args)


@tool
async def data360_get_disaggregation(
    database_id: str,
    indicator_id: str,
    required_country: str = None,
) -> str:
    """Get valid filter values and available time periods for an indicator.

    Always call this before data360_get_data to confirm country coverage and available years.

    Args:
        database_id: Database identifier returned by search (e.g. "WB_WDI").
        indicator_id: Indicator ID returned by search (e.g. "WB_WDI_NY_GDP_PCAP_CD").
        required_country: ISO country code to check coverage (e.g. "IND").
    """
    args = {"database_id": database_id, "indicator_id": indicator_id}
    if required_country:
        args["required_country"] = required_country
    return await call_mcp_tool(MACRO_MCP_URL, "data360_get_disaggregation", args)


@tool
async def data360_summarize_data(
    database_id: str,
    indicator_id: str,
    research_id: str,
    country_code: str = None,
    start_year: int = None,
    end_year: int = None,
) -> str:
    """Compute statistical summary (min, max, mean, trend) for an indicator.

    Use when the user asks about trends or general summaries rather than raw values.
    Result is returned directly to you — no interception.

    Args:
        database_id: Database identifier (e.g. "WB_WDI").
        indicator_id: Indicator ID (e.g. "WB_WDI_NY_GDP_PCAP_CD").
        research_id: The current research session ID (for context only, not passed to MCP).
        country_code: Semicolon-separated ISO country codes (e.g. "IND;CHN").
        start_year: Start year (integer).
        end_year: End year (integer).
    """
    args = {"database_id": database_id, "indicator_id": indicator_id}
    if country_code:
        args["country_code"] = country_code
    if start_year:
        args["start_year"] = start_year
    if end_year:
        args["end_year"] = end_year
    return await call_mcp_tool(MACRO_MCP_URL, "data360_summarize_data", args)


@tool
async def data360_rank_countries(
    database_id: str,
    indicator_id: str,
    research_id: str,
    country_group: str = None,
    top_n: int = 10,
    year: int = None,
    order: str = "desc",
) -> str:
    """Rank countries by indicator value for a given year.

    Use for leaderboard-style questions: 'top 10 countries by GDP', 'lowest infant mortality'.
    Result is returned directly to you — no interception.

    Args:
        database_id: Database identifier (e.g. "WB_WDI").
        indicator_id: Indicator ID (e.g. "WB_WDI_NY_GDP_PCAP_CD").
        research_id: The current research session ID (for context only, not passed to MCP).
        country_group: Regional/income group code (e.g. "SAS" for South Asia).
        top_n: Number of top results to return (default 10).
        year: Year for ranking snapshot. Auto-selected if omitted.
        order: "desc" (highest first, default) or "asc" (lowest first).
    """
    args = {"database_id": database_id, "indicator_id": indicator_id, "top_n": top_n, "order": order}
    if country_group:
        args["country_group"] = country_group
    if year:
        args["year"] = year
    return await call_mcp_tool(MACRO_MCP_URL, "data360_rank_countries", args)


@tool
async def data360_compare_countries(
    database_id: str,
    indicator_id: str,
    country_codes: str,
    research_id: str,
    year: int = None,
    include_time_series: bool = False,
    start_year: int = None,
    end_year: int = None,
) -> str:
    """Compare an indicator across 2 to 8 specific countries.

    Use for comparative questions: 'compare GDP of India and China'.
    Result is returned directly to you — no interception.

    Args:
        database_id: Database identifier (e.g. "WB_WDI").
        indicator_id: Indicator ID (e.g. "WB_WDI_NY_GDP_PCAP_CD").
        country_codes: Semicolon-separated ISO codes (e.g. "IND;CHN;USA").
        research_id: The current research session ID (for context only, not passed to MCP).
        year: Snapshot year. Auto-selected if omitted.
        include_time_series: Include time-series trend data alongside snapshot.
        start_year: Start year for time-series (integer).
        end_year: End year for time-series (integer).
    """
    args = {
        "database_id": database_id,
        "indicator_id": indicator_id,
        "country_codes": country_codes,
        "include_time_series": include_time_series,
    }
    if year:
        args["year"] = year
    if start_year:
        args["start_year"] = start_year
    if end_year:
        args["end_year"] = end_year
    return await call_mcp_tool(MACRO_MCP_URL, "data360_compare_countries", args)


# ---------------------------------------------------------------------------
# Intercepted tool — raw data is ingested to DB; agent gets confirmation only
# ---------------------------------------------------------------------------

@tool
async def data360_get_data(
    database_id: str,
    indicator_id: str,
    research_id: str,
    country_code: str = None,
    start_year: int = None,
    end_year: int = None,
    disaggregation_filters: dict = None,
) -> str:
    """Fetch raw indicator time-series observations and ingest them into the workspace database.

    IMPORTANT: The raw data is automatically intercepted and stored in the Workspace Manager.
    You will receive only a confirmation string — not the actual rows.
    Use data360_summarize_data or data360_compare_countries if you need statistical insights.

    Args:
        database_id: Database identifier (e.g. "WB_WDI"). From data360_search_indicators.
        indicator_id: Indicator ID (e.g. "WB_WDI_NY_GDP_PCAP_CD"). From data360_search_indicators.
        research_id: Current research session ID for artifact tracking.
        country_code: Semicolon-separated ISO country codes (e.g. "IND;CHN").
        start_year: Start year (integer, e.g. 2015).
        end_year: End year (integer, e.g. 2024).
        disaggregation_filters: Optional dimension filters from data360_get_disaggregation.
    """
    args = {"database_id": database_id, "indicator_id": indicator_id}
    if country_code:
        args["country_code"] = country_code
    if start_year:
        args["start_year"] = start_year
    if end_year:
        args["end_year"] = end_year
    if disaggregation_filters:
        args["disaggregation_filters"] = disaggregation_filters

    # Call the MCP server to get the raw data
    raw_response = await call_mcp_tool(MACRO_MCP_URL, "data360_get_data", args)

    # Intercept: parse and ingest into Workspace Manager
    try:
        parsed = json.loads(raw_response)
        # Extract the data array — the data360 API returns {"data": [...], "metadata": {...}}
        data_rows = parsed.get("data", [])
        metadata = parsed.get("metadata", {})

        if data_rows:
            artifact_id = indicator_id
            inputs = {
                "indicator_id": indicator_id,
                "database_id": database_id,
                "country_code": country_code,
                "start_year": start_year,
                "end_year": end_year,
            }
            catalog_id, _ = await ingest_to_db(
                research_id=research_id,
                artifact_id=artifact_id,
                source_mcp="data360",
                raw_json=data_rows,
                inputs=inputs,
            )
            return (
                f"{len(data_rows)} rows ingested into workspace. "
                f"Artifact ID: {artifact_id}. "
                f"Indicator: {metadata.get('name', indicator_id)}. "
                f"Source: {metadata.get('database_name', database_id)}."
            )
        else:
            return f"data360_get_data returned 0 rows for {indicator_id}. Try adjusting the year range or country code."

    except (json.JSONDecodeError, Exception) as e:
        # If parsing fails, still return something useful rather than crashing
        return f"data360_get_data completed but interception failed: {e}. Raw response length: {len(raw_response)} chars."


# ---------------------------------------------------------------------------
# Legacy placeholder (kept for backward compatibility, do not use)
# ---------------------------------------------------------------------------

@tool
async def fetch_macro_data(indicator: str, country: str, research_id: str) -> str:
    """Deprecated. Use data360_search_indicators + data360_get_data instead."""
    return "This tool is deprecated. Use the data360_* tools to fetch macroeconomic data."