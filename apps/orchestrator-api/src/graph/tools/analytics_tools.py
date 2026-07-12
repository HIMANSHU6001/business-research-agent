import os
import json
from langchain_core.tools import tool
from database import AsyncSessionLocal
from sqlalchemy import text
from mcp_clients import call_mcp_tool

ANALYTICS_MCP_URL = os.getenv("ANALYTICS_MCP_URL", "http://mcp-analytics:8000/sse")

@tool
async def read_catalog(research_id: str) -> str:
    """Read the workspace catalog to find available datasets for a given research session.
    
    Returns a list of artifacts including their artifact_id, description, and parquet file paths.
    """
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
                "parquet_path": r[2],
                "status": r[3]
            })
            
        return json.dumps(catalog_info, indent=2)

@tool
async def get_schema(artifact_id: str) -> str:
    """Get the schema (available columns and types) for a specific dataset.
    
    Args:
        artifact_id: The ID of the dataset found via read_catalog.
    """
    async with AsyncSessionLocal() as session:
        query = text(
            "SELECT schema_json FROM schema_registry WHERE artifact_id = :artifact_id"
        )
        result = await session.execute(query, {"artifact_id": artifact_id})
        row = result.first()
        
        if not row:
            return f"No schema found for artifact {artifact_id}."
            
        return row[0]

@tool
async def calculate_summary_statistics(parquet_path: str, column_name: str) -> str:
    """Calculate basic summary statistics (count, mean, std, min, max, median) for a numeric column in a dataset.
    
    Args:
        parquet_path: The file path to the dataset (db_table_pointer from read_catalog).
        column_name: The name of the numeric column to analyze (found via get_schema).
    """
    args = {
        "parquet_path": parquet_path,
        "column_name": column_name
    }
    return await call_mcp_tool(ANALYTICS_MCP_URL, "calculate_summary_statistics", args)
