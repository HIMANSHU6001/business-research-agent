from typing import Optional
import os
import json
import traceback
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from context.workspace import ingest_to_db
from mcp_clients import call_mcp_tool

FINANCIAL_MCP_URL = os.getenv("FINANCIAL_MCP_URL", "http://mcp-financial:8000/sse")


async def _get_and_ingest_financial_data(
    tool_name: str,
    args: dict,
    research_id: str,
    artifact_id: str,
    return_raw_data: bool = False
) -> str:
    """Helper to fetch financial data and ingest it into the workspace database."""
    raw_response = await call_mcp_tool(FINANCIAL_MCP_URL, tool_name, args)
    try:
        parsed = json.loads(raw_response)
        if isinstance(parsed, dict) and "error" in parsed:
            return f"Error from Alpha Vantage: {parsed['error'].get('message', 'Unknown error')}"

        metadata = parsed.get("metadata", {}) if isinstance(parsed, dict) else {}
        raw_data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed

        if tool_name in ["ipo_calendar", "earnings_calendar"] and isinstance(raw_data, str):
            import pandas as pd
            import io
            try:
                df = pd.read_csv(io.StringIO(raw_data))
                if df.empty:
                    return f"The Alpha Vantage API returned an empty dataset (0 rows) for {tool_name}. No data to ingest."
                raw_data = df.to_dict(orient="records")
            except Exception as e:
                return f"Failed to parse CSV response for {tool_name}: {e}"
        
        citation_str = None
        if metadata:
            citation_str = f"In-Text: {metadata.get('in_text', '')}\nCitation: {metadata.get('full_citation', '')}"

        catalog_id, _ = await ingest_to_db(
            research_id=research_id,
            artifact_id=artifact_id,
            source_mcp="financial",
            raw_json=raw_data,
            inputs=args,
            citation=citation_str
        )
        if return_raw_data:
            return (
                f"Successfully ingested {tool_name} data into workspace. "
                f"Artifact ID: {artifact_id}.\n"
                f"Raw Data:\n{json.dumps(raw_data, indent=2)}"
            )
        else:
            return (
                f"Successfully ingested {tool_name} data into workspace. "
                f"Artifact ID: {artifact_id}."
            )
    except (json.JSONDecodeError, Exception) as e:
        tb = traceback.format_exc()
        print(f"DEBUG {tool_name} exception:\n{tb}", flush=True)
        return f"{tool_name} completed but interception failed: {e}. Raw response length: {len(raw_response)} chars."


# --- Lookup & Search ---

@tool
async def symbol_search(
    keywords: str,
    config: RunnableConfig,
    datatype: str = "json"
) -> str:
    """Returns best-matching symbols and market information based on keywords.

    Use this first if the company ticker is not known or is unclear.

    Args:
        keywords: A text string of your choice. Example: microsoft
        datatype: Defaults to json. Strings json and csv are accepted.
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    args = {"keywords": keywords, "datatype": datatype}
    return await call_mcp_tool(FINANCIAL_MCP_URL, "symbol_search", args)


# --- Intercepted Fundamental Data Tools ---

@tool
async def company_overview(symbol: str, config: RunnableConfig) -> str:
    """Returns company information, financial ratios, and key metrics for the specified equity.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    return await _get_and_ingest_financial_data("company_overview", {"symbol": symbol}, research_id, f"overview_{symbol.lower()}", return_raw_data=True)


@tool
async def income_statement(symbol: str, config: RunnableConfig) -> str:
    """Returns annual and quarterly income statements for the specified company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    return await _get_and_ingest_financial_data("income_statement", {"symbol": symbol}, research_id, f"income_statement_{symbol.lower()}")


@tool
async def balance_sheet(symbol: str, config: RunnableConfig) -> str:
    """Returns annual and quarterly balance sheets for the specified company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    return await _get_and_ingest_financial_data("balance_sheet", {"symbol": symbol}, research_id, f"balance_sheet_{symbol.lower()}")


@tool
async def cash_flow(symbol: str, config: RunnableConfig) -> str:
    """Returns annual and quarterly cash flows for the specified company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    return await _get_and_ingest_financial_data("cash_flow", {"symbol": symbol}, research_id, f"cash_flow_{symbol.lower()}")


@tool
async def earnings(symbol: str, config: RunnableConfig) -> str:
    """Returns annual and quarterly earnings (EPS) for the company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    return await _get_and_ingest_financial_data("earnings", {"symbol": symbol}, research_id, f"earnings_{symbol.lower()}")


@tool
async def earnings_calendar(config: RunnableConfig, symbol: Optional[str] = None, horizon: str = "3month") -> str:
    """Returns a list of expected earnings reports in the next 3, 6, or 12 months.

    Args:
        symbol: Optional specific ticker symbol to filter (e.g. IBM).
        horizon: Next 3month, 6month, or 12month.
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    args = {"horizon": horizon}
    if symbol:
        args["symbol"] = symbol
    return await _get_and_ingest_financial_data("earnings_calendar", args, research_id, "earnings_calendar")



@tool
async def ipo_calendar(config: RunnableConfig) -> str:
    """Returns a list of IPOs expected in the next 3 months.

    Args:
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    return await _get_and_ingest_financial_data("ipo_calendar", {}, research_id, "ipo_calendar")



