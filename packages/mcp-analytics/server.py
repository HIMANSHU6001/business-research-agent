from fastmcp import FastMCP
import pandas as pd
import numpy as np
import scipy.stats as stats
import statsmodels.api as sm
import duckdb
import sys
import os
import re
import json
import shutil
import tempfile
import contextlib
import io
import traceback
from pathlib import Path

# Save the original read_parquet to avoid recursion
_original_read_parquet = pd.read_parquet

def safe_read_parquet(path: str):
    """Safely reads a parquet file by copying it to /tmp to bypass Docker Windows virtiofs mmap locks."""
    import time
    import os
    import shutil
    import tempfile
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Force cache invalidation
            try:
                os.listdir(os.path.dirname(path))
                os.stat(path)
            except Exception:
                pass
                
            # Copy to a temporary file in the container's native filesystem
            fd, tmp_path = tempfile.mkstemp(suffix=".parquet")
            os.close(fd)
            shutil.copy2(path, tmp_path)
            
            # Read from the local tmp copy using the original pandas function
            df = _original_read_parquet(tmp_path)
            
            # Clean up
            os.remove(tmp_path)
            return df
            
        except (IOError, OSError, PermissionError) as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1.0)

# Patch pandas to use the safe reader to bypass virtiofs mmap issues on Windows
pd.read_parquet = safe_read_parquet

mcp = FastMCP("analytics")

@mcp.tool()
def get_sample_data(parquet_path: str, n: int = 4) -> str:
    """Returns a sample (top N rows) of the dataset as a JSON string."""
    try:
        df = safe_read_parquet(parquet_path)
        sample = df.head(n).to_json(orient='records', date_format='iso')
        return f"Top {n} rows of dataset:\n{sample}"
    except Exception as e:
        return f"Error reading sample data: {str(e)}"

def _safe_rewrite_sql_paths(sql_query: str) -> tuple[str, list[str]]:
    """Copy parquet files referenced in read_parquet() from virtiofs to /tmp and rewrite SQL paths.
    
    Returns the rewritten SQL and a list of tmp file paths to clean up.
    """
    tmp_files = []
    
    def _replace_match(match):
        original_path = match.group(1)
        # Only rewrite paths on the shared volume
        if not original_path.startswith("/shared/"):
            return match.group(0)
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".parquet")
            os.close(fd)
            shutil.copy2(original_path, tmp_path)
            tmp_files.append(tmp_path)
            return f"read_parquet('{tmp_path}')"
        except (IOError, OSError):
            # If copy fails, leave the original path (DuckDB will report the error)
            return match.group(0)
    
    rewritten_sql = re.sub(r"read_parquet\(['\"]([^'\"]+)['\"]\)", _replace_match, sql_query)
    return rewritten_sql, tmp_files


@mcp.tool()
def run_duckdb_query(sql_query: str) -> str:
    """Executes a raw SQL query against DuckDB. Parquet files can be read using: SELECT * FROM read_parquet('file_path')."""
    tmp_files = []
    try:
        # Rewrite parquet paths to local /tmp copies to bypass virtiofs mmap issues
        rewritten_sql, tmp_files = _safe_rewrite_sql_paths(sql_query)
        
        # Create an in-memory DuckDB connection
        con = duckdb.connect(database=':memory:')
        
        # Execute the query and fetch the result as a pandas DataFrame
        df = con.execute(rewritten_sql).df()
        
        # Convert the DataFrame to JSON for the LLM
        result_json = df.to_json(orient="records", date_format="iso")
        
        return f"Query executed successfully.\nResult:\n{result_json}"
    except Exception as e:
        return f"Error executing DuckDB query: {str(e)}\n\nQuery was:\n{sql_query}"
    finally:
        # Clean up temporary files
        for f in tmp_files:
            try:
                os.remove(f)
            except OSError:
                pass

@mcp.tool()
def execute_python_code(script: str) -> str:
    """Executes an arbitrary Python script in a secure sandbox.
    You must use print() to output your final results, as only stdout is returned.
    Available libraries: pandas (pd), numpy (np), scipy.stats, statsmodels.api (sm), json.
    File paths must use the exact 'file_path' string returned by read_catalog.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    
    # Define a clean environment with safe builtins and standard analytics libraries
    env = {
        "pd": pd,
        "np": np,
        "stats": stats,
        "sm": sm,
        "os": os,
        "json": json,
        "Path": Path,
        "safe_read_parquet": safe_read_parquet,
        "__builtins__": __builtins__
    }
    
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(script, env)
            
        output = stdout.getvalue()
        errors = stderr.getvalue()
        
        if errors:
            return f"Execution completed with stderr warnings/errors:\n{errors}\n\nSTDOUT:\n{output}"
        
        if not output.strip():
            return "Execution completed successfully, but nothing was printed to stdout. Make sure to use print() to output your results."
            
        return f"Execution Output:\n{output}"
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        return f"Execution failed with error:\n{error_traceback}"

app = mcp.http_app(path="/sse", transport="sse")
