"""
Financial MCP Server — Alpha Vantage pass-through for the Business Research Agent.

Exposes fundamental_data and alpha_intelligence tool groups over SSE.
All responses are returned in full (no truncation). The orchestrator's
ingest_to_db middleware handles interception for fundamental_data tools.

Tool groups per TRD §7.7.1:
  fundamental_data (8):  COMPANY_OVERVIEW, INCOME_STATEMENT, BALANCE_SHEET,
                         CASH_FLOW, EARNINGS, EARNINGS_CALENDAR, LISTING_STATUS,
                         IPO_CALENDAR
  alpha_intelligence (7): NEWS_SENTIMENT, EARNINGS_CALL_TRANSCRIPT,
                          TOP_GAINERS_LOSERS, INSIDER_TRANSACTIONS,
                          INSTITUTIONAL_HOLDINGS, ANALYTICS_FIXED_WINDOW,
                          ANALYTICS_SLIDING_WINDOW
"""

import json
import os

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = "https://www.alphavantage.co/query"
API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")

mcp = FastMCP("financial")


# ---------------------------------------------------------------------------
# Alpha Vantage HTTP client
# ---------------------------------------------------------------------------


def _detect_av_error(response_text: str) -> dict | None:
    """Detect Alpha Vantage error envelopes returned with HTTP 200.

    AV signals failures via ``Error Message`` (bad params / invalid key),
    ``Information``, or ``Note`` (rate limit) keys in an otherwise-200 JSON body.
    Returns a structured error dict, or None for normal data responses.
    """
    try:
        parsed = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(parsed, dict):
        return None

    if "Error Message" in parsed:
        message = str(parsed["Error Message"])
        error_type = "invalid_api_key" if "apikey" in message.lower() else "invalid_request"
        return {"error": {"type": error_type, "message": message}}

    for key in ("Information", "Note"):
        if key in parsed:
            return {"error": {"type": "rate_limit", "message": str(parsed[key])}}

    return None


def _make_api_request(function_name: str, params: dict) -> dict | str:
    """Call the Alpha Vantage API and return the full, untruncated response.

    Returns parsed JSON (dict/list) when possible, otherwise raw text (CSV endpoints).
    AV error envelopes are normalized into a structured ``{"error": ...}`` dict.
    """
    api_params = {
        **params,
        "function": function_name,
        "apikey": API_KEY,
    }

    with httpx.Client() as client:
        response = client.get(API_BASE_URL, params=api_params)
        response.raise_for_status()

    response_text = response.text

    # Surface AV error envelopes as structured errors
    av_error = _detect_av_error(response_text)
    if av_error is not None:
        return av_error

    # Parse JSON if possible; fall back to raw text for CSV endpoints
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return response_text


# ===========================================================================
# fundamental_data tools (8)
#
# Per TRD §7.7.1 these are intercepted by ingest_to_db middleware upstream.
# The MCP server returns the full raw response; the orchestrator handles
# ingestion and returns a summary string to the LLM.
# ===========================================================================


@mcp.tool()
def company_overview(symbol: str) -> dict | str:
    """Returns company information, financial ratios, and key metrics for the specified equity.

    Data is generally refreshed on the same day a company reports its latest
    earnings and financials.

    Args:
        symbol: The symbol of the ticker of your choice. For example: symbol=IBM.
    """
    return _make_api_request("OVERVIEW", {"symbol": symbol})


@mcp.tool()
def income_statement(symbol: str) -> dict | str:
    """Returns annual and quarterly income statements with normalized fields.

    Fields are mapped to GAAP and IFRS taxonomies of the SEC. Data is generally
    refreshed on the same day a company reports its latest earnings and financials.

    Args:
        symbol: The symbol of the ticker of your choice. For example: symbol=IBM.
    """
    return _make_api_request("INCOME_STATEMENT", {"symbol": symbol})


@mcp.tool()
def balance_sheet(symbol: str) -> dict | str:
    """Returns annual and quarterly balance sheets with normalized fields.

    Fields are mapped to GAAP and IFRS taxonomies of the SEC. Data is generally
    refreshed on the same day a company reports its latest earnings and financials.

    Args:
        symbol: The symbol of the ticker of your choice. For example: symbol=IBM.
    """
    return _make_api_request("BALANCE_SHEET", {"symbol": symbol})


@mcp.tool()
def cash_flow(symbol: str) -> dict | str:
    """Returns annual and quarterly cash flow with normalized fields.

    Fields are mapped to GAAP and IFRS taxonomies of the SEC. Data is generally
    refreshed on the same day a company reports its latest earnings and financials.

    Args:
        symbol: The symbol of the ticker of your choice. For example: symbol=IBM.
    """
    return _make_api_request("CASH_FLOW", {"symbol": symbol})


@mcp.tool()
def earnings(symbol: str) -> dict | str:
    """Returns annual and quarterly earnings (EPS) for the company.

    Quarterly data also includes analyst estimates and surprise metrics.

    Args:
        symbol: The symbol of the ticker of your choice. For example: symbol=IBM.
    """
    return _make_api_request("EARNINGS", {"symbol": symbol})


@mcp.tool()
def earnings_calendar(symbol: str = None, horizon: str = "3month") -> dict | str:
    """Returns a list of company earnings expected in the next 3, 6, or 12 months.

    Args:
        symbol: By default, no symbol is set and the full list of scheduled earnings
            is returned. If set, returns expected earnings for that specific symbol.
            For example: symbol=IBM.
        horizon: By default, horizon=3month returns earnings in the next 3 months.
            Set horizon=6month or horizon=12month for 6 or 12 months respectively.
    """
    params = {"horizon": horizon}
    if symbol:
        params["symbol"] = symbol
    return _make_api_request("EARNINGS_CALENDAR", params)


@mcp.tool()
def listing_status(date: str = None, state: str = "active") -> dict | str:
    """Returns a list of active or delisted US stocks and ETFs.

    Can return data as of the latest trading day or at a specific time in history.
    Facilitates equity research on asset lifecycle and survivorship.

    Args:
        date: If no date is set, returns symbols as of the latest trading day.
            If set, returns symbols on that date in history. Any YYYY-MM-DD date
            later than 2010-01-01 is supported. For example: date=2013-08-03.
        state: By default, state=active returns actively traded stocks and ETFs.
            Set state=delisted to query delisted assets.
    """
    params = {"state": state}
    if date:
        params["date"] = date
    return _make_api_request("LISTING_STATUS", params)


@mcp.tool()
def ipo_calendar() -> dict | str:
    """Returns a list of IPOs expected in the next 3 months."""
    return _make_api_request("IPO_CALENDAR", {})


@mcp.tool()
def symbol_search(
    keywords: str,
    datatype: str = "csv"
) -> dict | str:
    """Returns best-matching symbols and market information based on keywords.

    Args:
        keywords: A text string of your choice. Example: microsoft
        datatype: By default, datatype=csv. Strings json and csv are accepted with the following specifications:
                 json returns the data in JSON format; csv returns the data as a CSV (comma separated value) file.

    Returns:
        Dict or string containing symbol search results based on datatype parameter.
    """
    params = {
        "keywords": keywords,
        "datatype": datatype,
    }

    return _make_api_request("SYMBOL_SEARCH", params)



# ===========================================================================
# alpha_intelligence tools (7)
#
# Per TRD §7.7.1 these are NOT intercepted. Results are returned directly
# to the Financial Intelligence Agent for inclusion in its topic report.
# ===========================================================================


@mcp.tool()
def news_sentiment(
    tickers: str = None,
    topics: str = None,
    time_from: str = None,
    time_to: str = None,
    sort: str = "LATEST",
    limit: int = 50,
) -> dict | str:
    """Returns live and historical market news & sentiment data from premier news outlets worldwide.

    Covers stocks, cryptocurrencies, forex, and topics like fiscal policy,
    mergers & acquisitions, IPOs.

    Args:
        tickers: Stock/crypto/forex symbols to filter articles.
            Example: "IBM" or "COIN,CRYPTO:BTC,FOREX:USD".
        topics: News topics to filter by.
            Example: "technology" or "technology,ipo".
        time_from: Start time range in YYYYMMDDTHHMM format.
            Example: "20220410T0130".
        time_to: End time range in YYYYMMDDTHHMM format.
            Defaults to current time if time_from specified.
        sort: Sort order — "LATEST" (default), "EARLIEST", or "RELEVANCE".
        limit: Number of results to return. Default 50, max 1000.
    """
    params = {"sort": sort, "limit": str(limit)}
    if tickers:
        params["tickers"] = tickers
    if topics:
        params["topics"] = topics
    if time_from:
        params["time_from"] = time_from
    if time_to:
        params["time_to"] = time_to
    return _make_api_request("NEWS_SENTIMENT", params)


@mcp.tool()
def earnings_call_transcript(symbol: str, quarter: str) -> dict | str:
    """Returns earnings call transcript for a company in a specific quarter.

    Covers 15+ years of history enriched with LLM-based sentiment signals.

    Args:
        symbol: Ticker symbol. Example: "IBM".
        quarter: Fiscal quarter in YYYYQM format. Example: "2024Q1".
            Supports quarters since 2010Q1.
    """
    return _make_api_request(
        "EARNINGS_CALL_TRANSCRIPT", {"symbol": symbol, "quarter": quarter}
    )


@mcp.tool()
def top_gainers_losers() -> dict | str:
    """Returns top 20 gainers, losers, and most active traded tickers in the US market."""
    return _make_api_request("TOP_GAINERS_LOSERS", {})


@mcp.tool()
def insider_transactions(symbol: str, from_date: str = None) -> dict | str:
    """Returns latest and historical insider transactions by key stakeholders.

    Covers transactions by founders, executives, board members, etc.

    Args:
        symbol: Ticker symbol. Example: "IBM".
        from_date: Optional start date in YYYY-MM-DD format. Only return
            transactions on or after this date. Example: "2026-03-01".
    """
    params = {"symbol": symbol}
    if from_date:
        params["from"] = from_date
    return _make_api_request("INSIDER_TRANSACTIONS", params)


@mcp.tool()
def institutional_holdings(symbol: str) -> dict | str:
    """Returns institutional ownership and holdings information for an equity.

    Args:
        symbol: Ticker symbol. Example: "IBM".
    """
    return _make_api_request("INSTITUTIONAL_HOLDINGS", {"symbol": symbol})


@mcp.tool()
def analytics_fixed_window(
    symbols: str,
    range_param: str,
    interval: str,
    calculations: str,
    ohlc: str = "close",
) -> dict | str:
    """Returns advanced analytics metrics for time series over a fixed temporal window.

    Calculates metrics like total return, variance, auto-correlation, etc.

    Args:
        symbols: Comma-separated list of symbols.
        range_param: Date range for the series. Defaults to full equity history.
        interval: Time interval — 1min, 5min, 15min, 30min, 60min, DAILY,
            WEEKLY, MONTHLY.
        calculations: Comma-separated list of analytics metrics to calculate.
        ohlc: OHLC field for calculation — open, high, low, close.
            Default "close".
    """
    return _make_api_request(
        "ANALYTICS_FIXED_WINDOW",
        {
            "SYMBOLS": symbols,
            "RANGE": range_param,
            "INTERVAL": interval,
            "CALCULATIONS": calculations,
            "OHLC": ohlc,
        },
    )


@mcp.tool()
def analytics_sliding_window(
    symbols: str,
    range_param: str,
    interval: str,
    window_size: int,
    calculations: str,
    ohlc: str = "close",
) -> dict | str:
    """Returns advanced analytics metrics for time series over sliding time windows.

    Calculates moving metrics like variance over time periods.

    Args:
        symbols: Comma-separated list of symbols.
        range_param: Date range for the series. Defaults to full equity history.
        interval: Time interval — 1min, 5min, 15min, 30min, 60min, DAILY,
            WEEKLY, MONTHLY.
        window_size: Size of moving window. Minimum 10, larger recommended
            for statistical significance.
        calculations: Comma-separated analytics metrics.
        ohlc: OHLC field for calculation — open, high, low, close.
            Default "close".
    """
    return _make_api_request(
        "ANALYTICS_SLIDING_WINDOW",
        {
            "SYMBOLS": symbols,
            "RANGE": range_param,
            "INTERVAL": interval,
            "WINDOW_SIZE": str(window_size),
            "CALCULATIONS": calculations,
            "OHLC": ohlc,
        },
    )


# ---------------------------------------------------------------------------
# SSE transport (docker-compose expects uvicorn server:app on port 8000)
# ---------------------------------------------------------------------------

app = mcp.http_app(path="/sse", transport="sse")
