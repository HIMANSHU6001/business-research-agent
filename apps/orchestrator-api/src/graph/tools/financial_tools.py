import os
import json
import traceback
from langchain_core.tools import tool
from context.workspace import ingest_to_db
from mcp_clients import call_mcp_tool

FINANCIAL_MCP_URL = os.getenv("FINANCIAL_MCP_URL", "http://mcp-financial:8000/sse")


async def _get_and_ingest_financial_data(
    tool_name: str,
    args: dict,
    research_id: str,
    artifact_id: str
) -> str:
    """Helper to fetch financial data and ingest it into the workspace database."""
    raw_response = await call_mcp_tool(FINANCIAL_MCP_URL, tool_name, args)
    try:
        parsed = json.loads(raw_response)
        if isinstance(parsed, dict) and "error" in parsed:
            return f"Error from Alpha Vantage: {parsed['error'].get('message', 'Unknown error')}"

        catalog_id, _ = await ingest_to_db(
            research_id=research_id,
            artifact_id=artifact_id,
            source_mcp="financial",
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


# --- Lookup & Search ---

@tool
async def symbol_search(
    keywords: str,
    research_id: str,
    datatype: str = "json"
) -> str:
    """Returns best-matching symbols and market information based on keywords.

    Use this first if the company ticker is not known or is unclear.

    Args:
        keywords: A text string of your choice. Example: microsoft
        research_id: Current research session ID.
        datatype: Defaults to json. Strings json and csv are accepted.
    """
    args = {"keywords": keywords, "datatype": datatype}
    return await call_mcp_tool(FINANCIAL_MCP_URL, "symbol_search", args)


# --- Intercepted Fundamental Data Tools ---

@tool
async def company_overview(symbol: str, research_id: str) -> str:
    """Returns company information, financial ratios, and key metrics for the specified equity.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
        research_id: Current research session ID.
    """
    return await _get_and_ingest_financial_data("company_overview", {"symbol": symbol}, research_id, f"overview_{symbol.lower()}")


@tool
async def income_statement(symbol: str, research_id: str) -> str:
    """Returns annual and quarterly income statements for the specified company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
        research_id: Current research session ID.
    """
    return await _get_and_ingest_financial_data("income_statement", {"symbol": symbol}, research_id, f"income_statement_{symbol.lower()}")


@tool
async def balance_sheet(symbol: str, research_id: str) -> str:
    """Returns annual and quarterly balance sheets for the specified company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
        research_id: Current research session ID.
    """
    return await _get_and_ingest_financial_data("balance_sheet", {"symbol": symbol}, research_id, f"balance_sheet_{symbol.lower()}")


@tool
async def cash_flow(symbol: str, research_id: str) -> str:
    """Returns annual and quarterly cash flows for the specified company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
        research_id: Current research session ID.
    """
    return await _get_and_ingest_financial_data("cash_flow", {"symbol": symbol}, research_id, f"cash_flow_{symbol.lower()}")


@tool
async def earnings(symbol: str, research_id: str) -> str:
    """Returns annual and quarterly earnings (EPS) for the company.

    Args:
        symbol: The symbol of the ticker (e.g. IBM).
        research_id: Current research session ID.
    """
    return await _get_and_ingest_financial_data("earnings", {"symbol": symbol}, research_id, f"earnings_{symbol.lower()}")


@tool
async def earnings_calendar(research_id: str, symbol: str = None, horizon: str = "3month") -> str:
    """Returns a list of expected earnings reports in the next 3, 6, or 12 months.

    Args:
        research_id: Current research session ID.
        symbol: Optional specific ticker symbol to filter (e.g. IBM).
        horizon: Next 3month, 6month, or 12month.
    """
    args = {"horizon": horizon}
    if symbol:
        args["symbol"] = symbol
    return await _get_and_ingest_financial_data("earnings_calendar", args, research_id, "earnings_calendar")


@tool
async def listing_status(research_id: str, date: str = None, state: str = "active") -> str:
    """Returns a list of active or delisted US stocks and ETFs.

    Args:
        research_id: Current research session ID.
        date: Optional YYYY-MM-DD history snapshot date.
        state: "active" or "delisted".
    """
    args = {"state": state}
    if date:
        args["date"] = date
    return await _get_and_ingest_financial_data("listing_status", args, research_id, f"listing_status_{state}")


@tool
async def ipo_calendar(research_id: str) -> str:
    """Returns a list of IPOs expected in the next 3 months.

    Args:
        research_id: Current research session ID.
    """
    return await _get_and_ingest_financial_data("ipo_calendar", {}, research_id, "ipo_calendar")


# --- Non-Intercepted Alpha Intelligence Tools ---

@tool
async def news_sentiment(
    research_id: str,
    tickers: str = None,
    topics: str = None,
    time_from: str = None,
    time_to: str = None,
    sort: str = "LATEST",
    limit: int = 50,
) -> str:
    """Returns live and historical market news & sentiment data.

    Args:
        research_id: Current research session ID.
        tickers: Optional tickers filter (e.g. "IBM").
        topics: Optional topics filter (e.g. "technology").
        time_from: Optional start time YYYYMMDDTHHMM.
        time_to: Optional end time YYYYMMDDTHHMM.
        sort: "LATEST", "EARLIEST", or "RELEVANCE".
        limit: Number of results (default 50, max 1000).
    """
    args = {"sort": sort, "limit": limit}
    if tickers:
        args["tickers"] = tickers
    if topics:
        args["topics"] = topics
    if time_from:
        args["time_from"] = time_from
    if time_to:
        args["time_to"] = time_to
    return await call_mcp_tool(FINANCIAL_MCP_URL, "news_sentiment", args)


@tool
async def earnings_call_transcript(symbol: str, quarter: str, research_id: str) -> str:
    """Returns earnings call transcript for a company in a specific quarter.

    Args:
        symbol: Ticker symbol (e.g. IBM).
        quarter: Fiscal quarter in YYYYQM format (e.g. "2024Q1").
        research_id: Current research session ID.
    """
    return await call_mcp_tool(FINANCIAL_MCP_URL, "earnings_call_transcript", {"symbol": symbol, "quarter": quarter})


@tool
async def top_gainers_losers(research_id: str) -> str:
    """Returns top 20 gainers, losers, and most active traded tickers in the US market.

    Args:
        research_id: Current research session ID.
    """
    return await call_mcp_tool(FINANCIAL_MCP_URL, "top_gainers_losers", {})


@tool
async def insider_transactions(symbol: str, research_id: str, from_date: str = None) -> str:
    """Returns latest and historical insider transactions by key stakeholders.

    Args:
        symbol: Ticker symbol (e.g. IBM).
        research_id: Current research session ID.
        from_date: Optional start date in YYYY-MM-DD format.
    """
    args = {"symbol": symbol}
    if from_date:
        args["from_date"] = from_date
    return await call_mcp_tool(FINANCIAL_MCP_URL, "insider_transactions", args)


@tool
async def institutional_holdings(symbol: str, research_id: str) -> str:
    """Returns institutional ownership and holdings information for an equity.

    Args:
        symbol: Ticker symbol (e.g. IBM).
        research_id: Current research session ID.
    """
    return await call_mcp_tool(FINANCIAL_MCP_URL, "institutional_holdings", {"symbol": symbol})


@tool
async def analytics_fixed_window(
    symbols: str,
    range_param: str,
    interval: str,
    calculations: str,
    research_id: str,
    ohlc: str = "close",
) -> str:
    """Returns advanced analytics metrics for time series over a fixed temporal window.

    Args:
        symbols: Comma-separated list of symbols.
        range_param: Date range for the series.
        interval: Time interval (e.g. DAILY, WEEKLY).
        calculations: Comma-separated list of metrics (e.g. variance).
        research_id: Current research session ID.
        ohlc: OHLC field for calculation (default "close").
    """
    return await call_mcp_tool(
        FINANCIAL_MCP_URL,
        "analytics_fixed_window",
        {
            "symbols": symbols,
            "range_param": range_param,
            "interval": interval,
            "calculations": calculations,
            "ohlc": ohlc,
        },
    )


@tool
async def analytics_sliding_window(
    symbols: str,
    range_param: str,
    interval: str,
    window_size: int,
    calculations: str,
    research_id: str,
    ohlc: str = "close",
) -> str:
    """Returns advanced analytics metrics for time series over sliding time windows.

    Args:
        symbols: Comma-separated list of symbols.
        range_param: Date range for the series.
        interval: Time interval (e.g. DAILY).
        window_size: Size of moving window (min 10).
        calculations: Comma-separated analytics metrics.
        research_id: Current research session ID.
        ohlc: OHLC field for calculation.
    """
    return await call_mcp_tool(
        FINANCIAL_MCP_URL,
        "analytics_sliding_window",
        {
            "symbols": symbols,
            "range_param": range_param,
            "interval": interval,
            "window_size": window_size,
            "calculations": calculations,
            "ohlc": ohlc,
        },
    )
