"""
Trends MCP Server — SerpApi Google Trends pass-through for the Business Research Agent.

Exposes interest_by_region and interest_over_time tools over SSE.
All responses are returned in full (no truncation). The orchestrator's
ingest_to_db middleware handles interception for these tools.
"""

import json
import os

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = "https://serpapi.com/search"
API_KEY = os.environ.get("SERPAPI_KEY", "")

mcp = FastMCP("trends")


# ---------------------------------------------------------------------------
# SerpApi HTTP client
# ---------------------------------------------------------------------------

def _detect_serpapi_error(response_text: str) -> dict | None:
    """Detect SerpApi error envelopes returned with HTTP 200 or 4xx.
    
    Returns a structured error dict, or None for normal data responses.
    """
    try:
        parsed = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(parsed, dict):
        return None

    if "error" in parsed:
        message = str(parsed["error"])
        return {"error": {"type": "api_error", "message": message}}

    return None


def _make_api_request(data_type: str, query: str, date: str, geo: str) -> dict | str:
    """Call the SerpApi Google Trends API and return the full, untruncated response.

    Returns parsed JSON. SerpApi error envelopes are normalized into a structured
    ``{"error": ...}`` dict.
    """
    api_params = {
        "engine": "google_trends",
        "q": query,
        "data_type": data_type,
        "api_key": API_KEY,
    }
    
    if date:
        api_params["date"] = date
    if geo:
        api_params["geo"] = geo

    try:
        transport = httpx.HTTPTransport(retries=3)
        with httpx.Client(timeout=60.0, transport=transport) as client:
            # SerpApi may return 4xx for some API errors, so we capture the response
            response = client.get(API_BASE_URL, params=api_params)
            
        response_text = response.text
    except httpx.RequestError as e:
        return {"error": {"message": f"Network error connecting to SerpApi: {e}"}}

    # Surface SerpApi error envelopes as structured errors
    serpapi_error = _detect_serpapi_error(response_text)
    if serpapi_error is not None:
        return serpapi_error
        
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {"error": {"message": f"HTTP Error {e.response.status_code}: {response_text}"}}

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return response_text


# ===========================================================================
# Trends Tools
# ===========================================================================

@mcp.tool()
def interest_by_region(query: str, date: str = "today 12-m", geo: str = "US") -> dict | str:
    """Returns regional interest data for a specific search query.

    Args:
        query: The search term to query. For example: query="Coffee".
        date: The time range for the query. Default is "today 12-m" (past 12 months).
        geo: The location for the query. Default is "US".
    """
    return _make_api_request("GEO_MAP_0", query, date, geo)


@mcp.tool()
def interest_over_time(query: str, date: str = "today 12-m", geo: str = "US") -> dict | str:
    """Returns interest over time data (timeseries) for a specific search query.

    Args:
        query: The search term to query. For example: query="Coffee".
        date: The time range for the query. Default is "today 12-m" (past 12 months).
        geo: The location for the query. Default is "US".
    """
    return _make_api_request("TIMESERIES", query, date, geo)


# ---------------------------------------------------------------------------
# SSE Setup
# ---------------------------------------------------------------------------
app = mcp.http_app(path="/sse", transport="sse")
