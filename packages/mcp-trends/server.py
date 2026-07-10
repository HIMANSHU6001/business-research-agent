from fastmcp import FastMCP

mcp = FastMCP("trends")

@mcp.tool()
def get_trends_status() -> str:
    """Check status of trends MCP placeholder server."""
    return "Trends MCP Placeholder is running."

app = mcp.http_app()
