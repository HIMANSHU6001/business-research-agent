"""MCP Tools for the Data360 server.

Thin wrapper layer that registers the 6 required API functions as MCP tools
with optimized signatures and concise docstrings to reduce token context bloat.
"""

import json
from typing import Any, Literal

import pydantic_core
from fastmcp.tools.tool import Tool

from data360 import api as data360_api

from ._server_definition import mcp
from .tool_spans import instrument_mcp_tool


def _compact_aggregation_serializer(data: Any) -> str:
    """Compact serializer for aggregation tool responses."""
    if hasattr(data, "to_compact"):
        return json.dumps(data.to_compact(), separators=(",", ":"))
    return pydantic_core.to_json(data, fallback=str).decode()


def _coerce_int(val: Any) -> int | None:
    """Coerce string or other inputs to integer if possible, returning None otherwise."""
    if val is None or val == "":
        return None
    if isinstance(val, int):
        return val
    try:
        val_str = str(val).strip()
        if not val_str:
            return None
        return int(val_str)
    except (ValueError, TypeError):
        return None


async def _search_indicators(
    query: str | None = None,
    required_country: str | None = None,
    limit: int = 5,
    offset: int = 0,
    queries: list[str] | None = None,
    query_groups: list[dict[str, Any]] | None = None,
    result_layout: str = "merged",
    dedupe: bool = True,
    database: str | None = None,
) -> Any:
    """Search for Data360 indicators with enriched metadata for selection.

    Use when the user asks for data on a development topic.
    Provide exactly one of query, queries, or query_groups.

    Args:
        query: Single topic query. Avoid parentheses or dollar signs.
        required_country: Semicolon-separated ISO country codes.
        limit: Max indicators per query (default 5).
        offset: Offset for pagination.
        queries: List of topics for multi-topic search (min 2 strings).
        query_groups: Grouped queries with specific country scopes.
        result_layout: merged or by_query.
        dedupe: De-duplicate indicators across query results.
        database: Optional database filter. Semicolon-separated for multiple.
    """
    return await data360_api.search(
        query=query,
        required_country=required_country,
        limit=limit,
        offset=offset,
        queries=queries,
        query_groups=query_groups,
        result_layout=result_layout,
        dedupe=dedupe,
        database=database,
    )


async def _get_data(
    database_id: str,
    indicator_id: str,
    country_code: str | None = None,
    disaggregation_filters: dict[str, str | None] | None = None,
    start_year: int | str | None = None,
    end_year: int | str | None = None,
    limit: int = 50,
    offset: int = 0,
    ref_area_filter: Literal["none", "member_economies_only"] = "member_economies_only",
) -> Any:
    """Retrieve indicator observations from the Data360 API.

    Use when you need actual numeric values for specific countries and years.
    Ensure database ID and indicator ID are already in context.
    Call data360_get_disaggregation first to find available years and filter options.
    start_year and end_year must be integers.

    Args:
        database_id: Database identifier, e.g. WB_WDI.
        indicator_id: Indicator ID, e.g. WB_WDI_NY_GDP_PCAP_KD.
        country_code: Semicolon-separated ISO country codes.
        disaggregation_filters: Optional dimension filters as string values or null.
        start_year: Start year inclusive.
        end_year: End year inclusive.
        limit: Max records per page (default 50, max 100).
        offset: Records to skip for pagination.
        ref_area_filter: member_economies_only (default) or none.
    """
    return await data360_api.get_data(
        database_id=database_id,
        indicator_id=indicator_id,
        country_code=country_code,
        disaggregation_filters=disaggregation_filters,
        start_year=_coerce_int(start_year),
        end_year=_coerce_int(end_year),
        limit=limit,
        offset=offset,
        ref_area_filter=ref_area_filter,
    )


async def _get_disaggregation(
    database_id: str,
    indicator_id: str,
    required_country: str | None = None,
) -> dict[str, Any]:
    """Get valid filter values and disaggregation options for an indicator.

    Use to find available dimensions and years before querying data.
    Ensure database ID and indicator ID are already in context.

    Args:
        database_id: Database identifier, e.g. WB_WDI.
        indicator_id: Indicator ID, e.g. WB_WDI_NY_GDP_PCAP_KD.
        required_country: Semicolon-separated ISO country codes to check coverage.
    """
    return await data360_api.get_disaggregation(
        database_id=database_id,
        indicator_id=indicator_id,
        required_country=required_country,
    )


async def _summarize_data(
    database_id: str,
    indicator_id: str,
    country_code: str,
    disaggregation_filters: dict[str, str | None] | None = None,
    start_year: int | str | None = None,
    end_year: int | str | None = None,
    group_by: list[str] | None = None,
) -> Any:
    """Compute summary statistics for indicator data, grouped by dimensions.

    Use when the user asks about trends, changes over time, or statistical summaries.
    Ensure database ID and indicator ID are already in context.

    Args:
        database_id: Database identifier, e.g. WB_WDI.
        indicator_id: Indicator ID, e.g. WB_WDI_NY_GDP_PCAP_KD.
        country_code: REQUIRED. Semicolon-separated ISO country codes. Use 'WLD' for global aggregate.
        disaggregation_filters: Optional dimension filters.
        start_year: Start year inclusive.
        end_year: End year inclusive.
        group_by: Dimensions to group by (default ref_area).
    """
    return await data360_api.summarize_data(
        database_id=database_id,
        indicator_id=indicator_id,
        country_code=country_code,
        disaggregation_filters=disaggregation_filters,
        start_year=_coerce_int(start_year),
        end_year=_coerce_int(end_year),
        group_by=group_by,
    )


async def _rank_countries(
    database_id: str,
    indicator_id: str,
    country_group: str | None = None,
    country_codes: str | None = None,
    year: int | str | None = None,
    order: Literal["desc", "asc"] = "desc",
    top_n: int = 10,
    disaggregation_filters: dict[str, str | None] | None = None,
    rank_universe: Literal["explicit", "all_member_economies"] = "explicit",
) -> Any:
    """Rank countries by indicator value for a specific year.

    Use when asked to rank countries or find top/bottom performing economies.
    Ensure database ID and indicator ID are already in context.

    Args:
        database_id: Database identifier, e.g. WB_WDI.
        indicator_id: Indicator ID, e.g. WB_WDI_NY_GDP_PCAP_KD.
        country_group: Region or income group code, e.g. SAS.
        country_codes: Semicolon-separated ISO country codes.
        year: Year for ranking. Auto-selected if omitted.
        order: desc (default, highest first) or asc.
        top_n: Number of ranked entries to return.
        disaggregation_filters: Optional dimension filters.
        rank_universe: explicit (default) or all_member_economies.
    """
    return await data360_api.rank_countries(
        database_id=database_id,
        indicator_id=indicator_id,
        country_group=country_group,
        country_codes=country_codes,
        year=_coerce_int(year),
        order=order,
        top_n=top_n,
        disaggregation_filters=disaggregation_filters,
        rank_universe=rank_universe,
    )


async def _compare_countries(
    database_id: str,
    indicator_id: str,
    country_codes: str,
    year: int | str | None = None,
    include_time_series: bool = False,
    start_year: int | str | None = None,
    end_year: int | str | None = None,
    disaggregation_filters: dict[str, str | None] | None = None,
) -> Any:
    """Compare an indicator across multiple countries (2 to 8).

    Use when asked to compare specific countries or find gaps between them.
    Ensure database ID and indicator ID are already in context.

    Args:
        database_id: Database identifier, e.g. WB_WDI.
        indicator_id: Indicator ID, e.g. WB_WDI_NY_GDP_PCAP_KD.
        country_codes: Semicolon-separated ISO country codes.
        year: Snapshot comparison year. Auto-selected if omitted.
        include_time_series: Return time-series data for trend comparison.
        start_year: Start year for time-series.
        end_year: End year for time-series.
        disaggregation_filters: Optional dimension filters.
    """
    return await data360_api.compare_countries(
        database_id=database_id,
        indicator_id=indicator_id,
        country_codes=country_codes,
        year=_coerce_int(year),
        include_time_series=include_time_series,
        start_year=_coerce_int(start_year),
        end_year=_coerce_int(end_year),
        disaggregation_filters=disaggregation_filters,
    )


# ---------------------------------------------------------------------------
# Tool Registration
# ---------------------------------------------------------------------------

search_indicators = mcp.tool(
    instrument_mcp_tool(_search_indicators, tool_name="data360_search_indicators"),
    name="data360_search_indicators",
)

get_data = mcp.tool(
    instrument_mcp_tool(_get_data, tool_name="data360_get_data"),
    name="data360_get_data",
)

get_disaggregation = mcp.tool(
    instrument_mcp_tool(_get_disaggregation, tool_name="data360_get_disaggregation"),
    name="data360_get_disaggregation",
)

# ---------------------------------------------------------------------------
# Aggregation Tools (with compact serialization)
# ---------------------------------------------------------------------------

summarize_data = mcp.add_tool(
    Tool.from_function(
        instrument_mcp_tool(_summarize_data, tool_name="data360_summarize_data"),
        name="data360_summarize_data",
        serializer=_compact_aggregation_serializer,
    )
)

rank_countries = mcp.add_tool(
    Tool.from_function(
        instrument_mcp_tool(_rank_countries, tool_name="data360_rank_countries"),
        name="data360_rank_countries",
        serializer=_compact_aggregation_serializer,
    )
)

compare_countries = mcp.add_tool(
    Tool.from_function(
        instrument_mcp_tool(_compare_countries, tool_name="data360_compare_countries"),
        name="data360_compare_countries",
        serializer=_compact_aggregation_serializer,
    )
)