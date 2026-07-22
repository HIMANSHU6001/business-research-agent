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
                "status": r[3],
                "file_path": f"/shared/workspaces/{research_id}/{r[0]}.parquet"
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
async def run_duckdb_query(sql_query: str) -> str:
    """Executes a raw SQL query against DuckDB. 
    Parquet files can be read using: SELECT * FROM read_parquet('file_path').
    Always use the exact file_path returned by the read_catalog tool.
    
    Args:
        sql_query: The SQL query to execute.
    """
    return await call_mcp_tool(ANALYTICS_MCP_URL, "run_duckdb_query", {"sql_query": sql_query})

@tool
async def execute_python_code(script: str) -> str:
    """Executes an arbitrary Python script in a secure sandbox.
    You must use print() to output your final results, as only stdout is returned.
    Available libraries: pandas (pd), numpy (np), scipy.stats, statsmodels.api (sm).
    To load data, use safe_read_parquet('file_path') using the exact file_path returned by read_catalog.
    
    Args:
        script: The Python code string to execute.
    """
    return await call_mcp_tool(ANALYTICS_MCP_URL, "execute_python_code", {"script": script})
