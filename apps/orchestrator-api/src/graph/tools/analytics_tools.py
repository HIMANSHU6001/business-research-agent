import os
import json
from typing import Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from database import AsyncSessionLocal
from sqlalchemy import text
from mcp_clients import call_mcp_tool

ANALYTICS_MCP_URL = os.getenv("ANALYTICS_MCP_URL", "http://mcp-analytics:8000/sse")

def _get_table_path(research_id: str, artifact_id: str) -> str:
    """Helper to resolve the correct parquet file path."""
    return f"/shared/workspaces/{research_id}/{artifact_id}.parquet"

@tool
async def read_catalog(config: RunnableConfig) -> str:
    """Read the workspace catalog to find available datasets for a given research session.
    
    Returns a list of artifacts including their artifact_id, description, and parquet file paths.
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    async with AsyncSessionLocal() as session:
        query = text(
            "SELECT artifact_id, description, db_table_pointer, status "
            "FROM semantic_catalog WHERE research_id = :research_id AND status = 'READY'"
        )
        result = await session.execute(query, {"research_id": research_id})
        rows = result.fetchall()
        
        if not rows:
            return "No ready artifacts found in the catalog for this research session."
            
        catalog_info = []
        for r in rows:
            catalog_info.append({
                "artifact_id": r[0],
                "description": r[1],
                "status": r[3]
            })
            
        return json.dumps(catalog_info, indent=2)

@tool
async def get_schema(artifact_ids: list[str]) -> str:
    """Get the schemas (available columns and types) for one or multiple datasets.
    
    Args:
        artifact_ids: A list of artifact IDs found via read_catalog (e.g. ["dataset1", "dataset2"]).
    """
    if isinstance(artifact_ids, str):
        artifact_ids = [artifact_ids]
        
    async with AsyncSessionLocal() as session:
        results = []
        for artifact_id in artifact_ids:
            query = text(
                "SELECT columns FROM schema_registry WHERE schema_ref = :schema_ref"
            )
            result = await session.execute(query, {"schema_ref": f"schema_{artifact_id}"})
            row = result.first()
            
            if not row:
                results.append({artifact_id: f"No schema found for artifact {artifact_id}."})
            else:
                columns_data = row[0]
                results.append({artifact_id: columns_data})
                
        return json.dumps(results, indent=2)

@tool
async def get_sample_data(artifact_id: str, config: RunnableConfig) -> str:
    """Get a sample (top 4 rows) of the dataset to understand its structure and content before analyzing.
    
    Args:
        artifact_id: The ID of the dataset (found via read_catalog).
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    parquet_path = _get_table_path(research_id, artifact_id)
    return await call_mcp_tool(ANALYTICS_MCP_URL, "get_sample_data", {"parquet_path": parquet_path, "n": 4})

@tool
async def get_descriptive_stats(artifact_id: str, column_name: str, config: RunnableConfig, query_filter: str = "") -> str:
    """Calculate basic summary statistics (count, mean, std, min, max, median) for a numeric column in a dataset.
    
    Args:
        artifact_id: The ID of the dataset (found via read_catalog).
        column_name: The name of the numeric column to analyze (found via get_schema).
        query_filter: (Optional) A Pandas query string to filter the data before analysis (e.g., "date >= '2023-01-01'").
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    parquet_path = _get_table_path(research_id, artifact_id)
    args = {
        "parquet_path": parquet_path,
        "column_name": column_name
    }
    if query_filter:
        args["query_filter"] = query_filter
    return await call_mcp_tool(ANALYTICS_MCP_URL, "get_descriptive_stats", args)

@tool
async def calculate_correlation(artifact_id_x: str, col_x: str, col_y: str, config: RunnableConfig, artifact_id_y: Optional[str] = None, join_key: Optional[str] = None, query_filter: str = "") -> str:
    """Computes statistical relationship (Pearson, Spearman) between two numeric series, optionally across two tables joined on a key.
    
    Args:
        artifact_id_x: ID of the first dataset.
        col_x: The first numeric column.
        col_y: The second numeric column.
        artifact_id_y: (Optional) ID of the second dataset. If omitted, assumes both columns are in the first dataset.
        join_key: REQUIRED if artifact_id_y is provided. The column name to join the tables on (usually 'date' or 'timestamp').
        query_filter: (Optional) A Pandas query string to filter the data before analysis (e.g., "date >= '2023-01-01'").
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    table_x = _get_table_path(research_id, artifact_id_x)
    table_y = _get_table_path(research_id, artifact_id_y) if artifact_id_y else table_x
    
    args = {
        "table_x": table_x, "col_x": col_x, 
        "table_y": table_y, "col_y": col_y
    }
    if join_key:
        args["join_key"] = join_key
    else:
        args["join_key"] = "" # Fallback if MCP server requires it
        
    if query_filter:
        args["query_filter"] = query_filter
        
    return await call_mcp_tool(ANALYTICS_MCP_URL, "calculate_correlation", args)

@tool
async def execute_t_test(artifact_id: str, target_col: str, split_col: str, group_a_condition: str, group_b_condition: str, config: RunnableConfig) -> str:
    """Determines whether there is a statistically significant difference between means of two groups using Welch's t-test.
    
    Args:
        artifact_id: ID of the dataset.
        target_col: Numeric column to compare.
        split_col: Column to use for splitting into groups.
        group_a_condition: Pandas query string for group A (e.g., "== 'Male'" or "< 2020").
        group_b_condition: Pandas query string for group B (e.g., "== 'Female'" or ">= 2020").
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    table = _get_table_path(research_id, artifact_id)
    args = {
        "table": table, "target_col": target_col, 
        "split_col": split_col, 
        "group_a_condition": group_a_condition, 
        "group_b_condition": group_b_condition
    }
    return await call_mcp_tool(ANALYTICS_MCP_URL, "execute_t_test", args)

@tool
async def calculate_trendline(artifact_id: str, target_col: str, date_col: str, config: RunnableConfig, rolling_window: int = 1, query_filter: str = "") -> str:
    """Computes a moving average and fits an OLS linear model over a temporal index to find trend (slope, R-squared).
    
    Args:
        artifact_id: ID of the dataset.
        target_col: Numeric column to find trend for.
        date_col: Column containing time/date for ordering.
        rolling_window: Integer for rolling mean window (default 1 = no smoothing).
        query_filter: (Optional) A Pandas query string to filter the data before analysis (e.g., "date >= '2023-01-01'").
    """
    research_id = config.get("configurable", {}).get("research_id", "")
    table = _get_table_path(research_id, artifact_id)
    args = {
        "table": table, "target_col": target_col, 
        "date_col": date_col, "rolling_window": rolling_window
    }
    if query_filter:
        args["query_filter"] = query_filter
    return await call_mcp_tool(ANALYTICS_MCP_URL, "calculate_trendline", args)
