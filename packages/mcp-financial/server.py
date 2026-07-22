"""
Financial MCP Server — Alpha Vantage pass-through for the Business Research Agent.

Exposes fundamental_data and alpha_intelligence tool groups over SSE.
All responses are returned in full (no truncation). The orchestrator's
ingest_to_db middleware handles interception for fundamental_data tools.

Tool groups per TRD §7.7.1:
  fundamental_data (7):  COMPANY_OVERVIEW, INCOME_STATEMENT, BALANCE_SHEET,
                         CASH_FLOW, EARNINGS, EARNINGS_CALENDAR, IPO_CALENDAR
  alpha_intelligence (7): NEWS_SENTIMENT, EARNINGS_CALL_TRANSCRIPT,
                          TOP_GAINERS_LOSERS, INSIDER_TRANSACTIONS,
                          INSTITUTIONAL_HOLDINGS, ANALYTICS_FIXED_WINDOW,
                          ANALYTICS_SLIDING_WINDOW
"""

import json
import os
import datetime

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
        data = json.loads(response_text)
    except json.JSONDecodeError:
        data = response_text

    current_date = datetime.datetime.now().strftime("%d %B %Y")
    current_year = datetime.datetime.now().strftime("%Y")
    
    # We strip the apikey from the URL for the citation so it doesn't leak
    clean_url = str(response.url).replace(f"&apikey={API_KEY}", "").replace(f"?apikey={API_KEY}", "?")

    return {
        "metadata": {
            "in_text": "(Alpha Vantage)",
            "full_citation": f"Alpha Vantage APIs. Alpha Vantage Inc., {current_year}, {clean_url}. Accessed {current_date}."
        },
        "data": data
    }


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






# ---------------------------------------------------------------------------
# SSE transport (docker-compose expects uvicorn server:app on port 8000)
# ---------------------------------------------------------------------------

app = mcp.http_app(path="/sse", transport="sse")
