import os
import httpx
from mcp.client.sse import sse_client
from mcp import ClientSession
from langchain_core.tools import tool, StructuredTool

FINANCIAL_MCP_URL = os.getenv("FINANCIAL_MCP_URL", "http://mcp-financial:8000/sse")
MACRO_MCP_URL = os.getenv("MACRO_MCP_URL", "http://mcp-macro:8000/sse")
TRENDS_MCP_URL = os.getenv("TRENDS_MCP_URL", "http://mcp-trends:8000/sse")
ANALYTICS_MCP_URL = os.getenv("ANALYTICS_MCP_URL", "http://mcp-analytics:8000/sse")

async def call_mcp_tool(server_url: str, tool_name: str, arguments: dict) -> str:
    """Connect to an SSE MCP server, execute a tool, and return the content."""
    async with sse_client(server_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            
            # Combine content items into a single string
            text_contents = []
            for item in result.content:
                if hasattr(item, "text"):
                    text_contents.append(item.text)
                elif isinstance(item, dict) and "text" in item:
                    text_contents.append(item["text"])
                else:
                    text_contents.append(str(item))
            return "\n".join(text_contents)

# Static wrappers using LangChain's @tool decorator
@tool
async def invoke_analytics_tool(tool_name: str, arguments: dict) -> str:
    """
    Invoke a quantitative/statistical analysis tool on the mcp-analytics server.
    
    Args:
        tool_name (str): The name of the tool to execute.
        arguments (dict): The arguments/parameters to pass to the tool.
    """
    return await call_mcp_tool(ANALYTICS_MCP_URL, tool_name, arguments)

@tool
async def invoke_financial_tool(tool_name: str, arguments: dict) -> str:
    """
    Invoke a financial data collection tool on the mcp-financial server.
    
    Args:
        tool_name (str): The name of the tool to execute.
        arguments (dict): The arguments/parameters to pass to the tool.
    """
    return await call_mcp_tool(FINANCIAL_MCP_URL, tool_name, arguments)

@tool
async def invoke_macro_tool(tool_name: str, arguments: dict) -> str:
    """
    Invoke a macroeconomic data collection tool on the mcp-macro server.
    
    Args:
        tool_name (str): The name of the tool to execute.
        arguments (dict): The arguments/parameters to pass to the tool.
    """
    return await call_mcp_tool(MACRO_MCP_URL, tool_name, arguments)


# Dynamic Tool Discovery and Wrapping
async def discover_mcp_tools(server_url: str) -> list[StructuredTool]:
    """Dynamically discover tools from an SSE MCP server and wrap them as LangChain StructuredTools."""
    wrapped_tools = []
    try:
        async with sse_client(server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                mcp_tools = await session.list_tools()
                
                for t in mcp_tools.tools:
                    # Capture tool name in closure
                    def create_mcp_caller(t_name=t.name):
                        async def mcp_caller(**kwargs) -> str:
                            return await call_mcp_tool(server_url, t_name, kwargs)
                        return mcp_caller

                    # Convert argument schema if it exists
                    args_schema = None
                    if hasattr(t, "inputSchema") and t.inputSchema:
                        args_schema = t.inputSchema
                    elif isinstance(t, dict) and "inputSchema" in t:
                        args_schema = t["inputSchema"]

                    structured_tool = StructuredTool.from_function(
                        coroutine=create_mcp_caller(t.name),
                        name=t.name,
                        description=t.description or f"MCP tool: {t.name}",
                        args_schema=args_schema
                    )
                    wrapped_tools.append(structured_tool)
    except Exception as e:
        print(f"Warning: Could not discover tools from {server_url}: {e}")
    return wrapped_tools
