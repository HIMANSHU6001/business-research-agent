from fastmcp import FastMCP
import pandas as pd
import numpy as np
import scipy.stats as stats
import statsmodels.api as sm
import statsmodels.api as sm

def safe_read_parquet(path: str):
    """Safely reads a parquet file by bypassing pyarrow mmap, with retries for Windows WSL2 locks."""
    import io
    import time
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with open(path, 'rb') as f:
                data = f.read()
            return pd.read_parquet(io.BytesIO(data))
        except (IOError, OSError, PermissionError) as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(0.5)

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

@mcp.tool()
def get_descriptive_stats(parquet_path: str, column_name: str, query_filter: str = "") -> str:
    """Calculate basic summary statistics for a column in a parquet file."""
    try:
        df = safe_read_parquet(parquet_path)
        if query_filter:
            try:
                df = df.query(query_filter)
            except Exception as q_e:
                return f"Error evaluating query_filter '{query_filter}'. Ensure it is a valid Pandas query string. Details: {str(q_e)}"
        
        if column_name not in df.columns:
            return f"Error: Column '{column_name}' not found. Available columns: {list(df.columns)}"
        
        # Coerce to numeric in case it was stored as string
        series = pd.to_numeric(df[column_name], errors='coerce').dropna()
        if series.empty:
            return f"Error: Column '{column_name}' contains no valid numeric data."
            
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

@mcp.tool()
def calculate_correlation(table_x: str, col_x: str, table_y: str, col_y: str, join_key: str, query_filter: str = "") -> str:
    """Computes statistical relationship between two numeric series, optionally across two tables joined on a key."""
    try:
        df_x = safe_read_parquet(table_x)
        if table_x != table_y:
            df_y = safe_read_parquet(table_y)
            if query_filter:
                try:
                    df_x = df_x.query(query_filter)
                    df_y = df_y.query(query_filter)
                except Exception as q_e:
                    return f"Error evaluating query_filter '{query_filter}'. Ensure it is a valid Pandas query string. Details: {str(q_e)}"
                    
            if join_key not in df_x.columns: return f"Error: join_key '{join_key}' not in table_x. Available: {list(df_x.columns)}"
            if join_key not in df_y.columns: return f"Error: join_key '{join_key}' not in table_y. Available: {list(df_y.columns)}"
            merged = pd.merge(df_x, df_y, on=join_key, how="inner", suffixes=('_x', '_y'))
            # Resolve column names after merge
            actual_col_x = col_x + '_x' if col_x in df_y.columns and col_x == col_y else col_x
            actual_col_y = col_y + '_y' if col_y in df_x.columns and col_x == col_y else col_y
        else:
            if query_filter:
                try:
                    df_x = df_x.query(query_filter)
                except Exception as q_e:
                    return f"Error evaluating query_filter '{query_filter}'. Ensure it is a valid Pandas query string. Details: {str(q_e)}"
            merged = df_x
            actual_col_x = col_x
            actual_col_y = col_y

        if actual_col_x not in merged.columns: return f"Error: col_x '{actual_col_x}' not in table. Available: {list(merged.columns)}"
        if actual_col_y not in merged.columns: return f"Error: col_y '{actual_col_y}' not in table. Available: {list(merged.columns)}"

        merged[actual_col_x] = pd.to_numeric(merged[actual_col_x], errors='coerce')
        merged[actual_col_y] = pd.to_numeric(merged[actual_col_y], errors='coerce')
        merged = merged[[actual_col_x, actual_col_y]].dropna()

        if len(merged) < 3:
            return "Error: Not enough overlapping non-null data points to calculate correlation (minimum 3 required)."

        pearson_corr, pearson_p = stats.pearsonr(merged[actual_col_x], merged[actual_col_y])
        spearman_corr, spearman_p = stats.spearmanr(merged[actual_col_x], merged[actual_col_y])
        
        # Check for spurious correlation (both series strongly trending)
        n = len(merged)
        idx = np.arange(n)
        slope_x, _, _, _, _ = stats.linregress(idx, merged[actual_col_x])
        slope_y, _, _, _, _ = stats.linregress(idx, merged[actual_col_y])
        
        # Normalize slopes to assess trend magnitude relative to std
        std_x, std_y = merged[actual_col_x].std(), merged[actual_col_y].std()
        trend_warning = ""
        if std_x > 0 and std_y > 0:
            norm_slope_x = abs(slope_x * n / std_x)
            norm_slope_y = abs(slope_y * n / std_y)
            if norm_slope_x > 1.5 and norm_slope_y > 1.5:
                trend_warning = (
                    "\nCAVEAT: Both series exhibit a strong trend over the joined index. "
                    "The high correlation may be spurious (driven by the shared trend rather than a structural relationship). "
                    "Consider detrending before drawing causal conclusions."
                )

        return (
            f"Correlation between {col_x} and {col_y} (n={len(merged)}):\n"
            f"- Pearson: {pearson_corr:.4f} (p-value: {pearson_p:.4e})\n"
            f"- Spearman: {spearman_corr:.4f} (p-value: {spearman_p:.4e}){trend_warning}"
        )
    except Exception as e:
        return f"Error calculating correlation: {str(e)}"

@mcp.tool()
def execute_t_test(table: str, target_col: str, split_col: str, group_a_condition: str, group_b_condition: str) -> str:
    """Determines whether there is a statistically significant difference between means of two groups."""
    try:
        df = safe_read_parquet(table)
        if target_col not in df.columns: return f"Error: target_col '{target_col}' not found. Available: {list(df.columns)}"
        if split_col not in df.columns: return f"Error: split_col '{split_col}' not found. Available: {list(df.columns)}"

        df[target_col] = pd.to_numeric(df[target_col], errors='coerce')

        # Simple string-based query evaluation (safe via pandas .query())
        try:
            group_a = df.query(f"{split_col} {group_a_condition}")[target_col].dropna()
            group_b = df.query(f"{split_col} {group_b_condition}")[target_col].dropna()
        except Exception as q_e:
            return f"Error evaluating conditions. Ensure they are valid Pandas query strings (e.g. '== 1', '> 2020'). Details: {str(q_e)}"

        if len(group_a) < 2 or len(group_b) < 2:
            return f"Error: Insufficient data. Group A has {len(group_a)} obs; Group B has {len(group_b)} obs."

        # Welch's t-test
        t_stat, p_value = stats.ttest_ind(group_a, group_b, equal_var=False)
        
        caveat = ""
        # Basic heuristic to check if split_col might be a date/year
        if pd.api.types.is_datetime64_any_dtype(df[split_col]) or 'year' in split_col.lower() or 'date' in split_col.lower():
            caveat = (
                "\nCAVEAT: The split column appears to represent time/dates. "
                "Adjacent observations in time-series data are often not independent. "
                "The reported p-value assumes independence and may read as overly confident."
            )

        return (
            f"Welch's t-test for {target_col} split by {split_col}:\n"
            f"Group A ({group_a_condition}): n={len(group_a)}, mean={group_a.mean():.4f}\n"
            f"Group B ({group_b_condition}): n={len(group_b)}, mean={group_b.mean():.4f}\n"
            f"T-statistic: {t_stat:.4f}, p-value: {p_value:.4e}{caveat}"
        )
    except Exception as e:
        return f"Error executing t-test: {str(e)}"

@mcp.tool()
def calculate_trendline(table: str, target_col: str, date_col: str, rolling_window: int, query_filter: str = "") -> str:
    """Computes a moving average and fits an OLS linear model over a temporal index."""
    try:
        df = safe_read_parquet(table)
        if query_filter:
            try:
                df = df.query(query_filter)
            except Exception as q_e:
                return f"Error evaluating query_filter '{query_filter}'. Ensure it is a valid Pandas query string. Details: {str(q_e)}"
        
        if target_col not in df.columns: return f"Error: '{target_col}' not found. Available: {list(df.columns)}"
        if date_col not in df.columns: return f"Error: '{date_col}' not found. Available: {list(df.columns)}"

        df[target_col] = pd.to_numeric(df[target_col], errors='coerce')
        df = df.sort_values(by=date_col).dropna(subset=[target_col])
        if len(df) < 3: return "Error: Insufficient data points for OLS trendline."

        # Compute rolling mean if requested
        rolling_series = df[target_col]
        if rolling_window > 1:
            rolling_series = df[target_col].rolling(window=rolling_window, min_periods=1).mean()

        # OLS requires numeric independent variable; we'll use sequential integer index (time proxy)
        X = np.arange(len(df))
        X = sm.add_constant(X)
        y = rolling_series.values

        model = sm.OLS(y, X).fit()
        slope = model.params[1]
        r_squared = model.rsquared

        return (
            f"OLS Trendline for {target_col} over {date_col} (n={len(df)}, rolling_window={rolling_window}):\n"
            f"- Slope (change per period): {slope:.4e}\n"
            f"- R-squared: {r_squared:.4f}\n"
            f"- P-value (slope != 0): {model.pvalues[1]:.4e}"
        )
    except Exception as e:
        return f"Error calculating trendline: {str(e)}"

app = mcp.http_app(path="/sse", transport="sse")
