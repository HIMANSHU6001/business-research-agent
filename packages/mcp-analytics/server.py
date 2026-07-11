from fastmcp import FastMCP
import pandas as pd
import numpy as np

mcp = FastMCP("analytics")

@mcp.tool()
def calculate_summary_statistics(parquet_path: str, column_name: str) -> str:
    """Calculate basic summary statistics for a column in a parquet file."""
    try:
        df = pd.read_parquet(parquet_path)
        if column_name not in df.columns:
            return f"Error: Column '{column_name}' not found. Available columns: {list(df.columns)}"
        
        series = df[column_name]
        if not pd.api.types.is_numeric_dtype(series):
            return f"Error: Column '{column_name}' is not numeric."
            
        summary = {
            "count": int(series.count()),
            "mean": float(series.mean()),
            "std": float(series.std()) if series.count() > 1 else 0.0,
            "min": float(series.min()),
            "max": float(series.max()),
            "median": float(series.median())
        }
        return f"Summary statistics for {column_name}: {summary}"
    except Exception as e:
        return f"Error calculating statistics: {str(e)}"

app = mcp.http_app(path="/sse", transport="sse")
