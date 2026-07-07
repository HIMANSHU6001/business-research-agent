import os
import json
import uuid
import datetime
import pandas as pd
from sqlalchemy import text
from groq import AsyncGroq
from src.database import get_duckdb_conn, AsyncSessionLocal

async def generate_semantic_summary(artifact_id: str, sample_data_json: str, source_mcp: str) -> str:
    """Calls the Groq LLM to generate a 2-3 sentence semantic summary of the data."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return f"Semantic data catalog for {artifact_id} collected from {source_mcp}."

    try:
        client = AsyncGroq(api_key=api_key)
        prompt = f"""You are a data cataloging assistant. Write a 2-3 sentence semantic summary of the following dataset utility.
Dataset ID: {artifact_id}
Source MCP: {source_mcp}
Sample Data (JSON):
{sample_data_json[:2000]}

Focus on what this data represents, its granularity, and its potential utility for business research. Keep it concise, professional, and strictly under 3 sentences."""

        chat_completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful data cataloging assistant."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",  # Stable Groq model
            max_tokens=150,
            temperature=0.2,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling LLM for summary: {e}")
        return f"Dataset {artifact_id} from {source_mcp}. Summary generation failed."

async def update_catalog_summary(catalog_id: uuid.UUID, artifact_id: str, sample_json: str, source_mcp: str):
    """Background task to generate summary, update status to READY, and commit."""
    summary = await generate_semantic_summary(artifact_id, sample_json, source_mcp)
    
    async with AsyncSessionLocal() as session:
        try:
            # Update semantic catalog status and description
            stmt = text("""
                UPDATE semantic_catalog 
                SET description = :description, status = 'READY'
                WHERE id = :id
            """)
            await session.execute(stmt, {"description": summary, "id": catalog_id})
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Failed to update catalog status: {e}")

def detect_time_boundaries(df: pd.DataFrame):
    """Finds date/time columns and computes min and max boundaries."""
    time_start = None
    time_end = None
    
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["date", "time", "timestamp"]):
            try:
                converted = pd.to_datetime(df[col], errors='coerce')
                valid_dates = converted.dropna()
                if not valid_dates.empty:
                    # Let's set start and end
                    start = valid_dates.min().to_pydatetime()
                    end = valid_dates.max().to_pydatetime()
                    
                    if time_start is None or start < time_start:
                        time_start = start
                    if time_end is None or end > time_end:
                        time_end = end
            except Exception:
                pass
                
    return time_start, time_end

def map_pandas_dtype_to_sql(dtype) -> str:
    """Maps pandas dtype to simple SQL type names for the schema registry."""
    if pd.api.types.is_integer_dtype(dtype):
        return "INTEGER"
    elif pd.api.types.is_float_dtype(dtype):
        return "FLOAT"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    elif pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    else:
        return "VARCHAR"

async def ingest_to_db(research_id: str, artifact_id: str, source_mcp: str, raw_json: any, inputs: dict = None) -> str:
    """Ingest raw JSON payload to Parquet via DuckDB and register metadata in Postgres."""
    # Ensure research_id is a UUID
    r_uuid = uuid.UUID(research_id)
    
    # 1. Flatten the raw_json and convert to Pandas DataFrame
    # If raw_json is a dict, wrap it in a list to load as a dataframe
    if isinstance(raw_json, dict):
        # In case it has a data/results list nested inside
        data_to_load = None
        for key in ["data", "results", "entries", "records"]:
            if key in raw_json and isinstance(raw_json[key], list):
                data_to_load = raw_json[key]
                break
        if data_to_load is None:
            data_to_load = [raw_json]
    else:
        data_to_load = raw_json

    df = pd.json_normalize(data_to_load)
    
    # Define physical storage path
    db_dir = os.getenv("DUCKDB_DATA_DIR", "/shared/workspaces")
    research_dir = os.path.join(db_dir, str(research_id))
    os.makedirs(research_dir, exist_ok=True)
    parquet_path = os.path.join(research_dir, f"{artifact_id}.parquet")
    
    # 2. Execute DuckDB write
    conn = get_duckdb_conn()
    conn.register("my_df", df)
    # Use standard POSIX-like forward slashes for DuckDB path
    posix_parquet_path = parquet_path.replace("\\", "/")
    conn.execute(f"COPY my_df TO '{posix_parquet_path}' (FORMAT PARQUET)")
    conn.unregister("my_df")
    
    # Calculate row count and time boundaries
    row_count = len(df)
    time_start, time_end = detect_time_boundaries(df)
    
    # Format Schema Registry payload
    schema_cols = [{"name": col, "type": map_pandas_dtype_to_sql(df[col].dtype)} for col in df.columns]
    schema_ref = f"schema_{artifact_id}"
    
    # Sample JSON for LLM summarization
    sample_df = df.head(5)
    sample_json = sample_df.to_json(orient="records")
    
    async with AsyncSessionLocal() as session:
        try:
            # 3. Upsert Schema Registry
            schema_stmt = text("""
                INSERT INTO schema_registry (schema_ref, columns, description)
                VALUES (:schema_ref, :columns, :description)
                ON CONFLICT (schema_ref) DO UPDATE 
                SET columns = EXCLUDED.columns, description = EXCLUDED.description
            """)
            await session.execute(schema_stmt, {
                "schema_ref": schema_ref,
                "columns": json.dumps(schema_cols),
                "description": f"Schema for {artifact_id} artifact from {source_mcp}"
            })
            
            # 4. Insert PENDING record into Postgres semantic_catalog
            catalog_id = uuid.uuid4()
            db_pointer = f"/shared/workspaces/{research_id}/{artifact_id}.parquet"
            
            catalog_stmt = text("""
                INSERT INTO semantic_catalog (
                    id, research_id, artifact_id, source_mcp, db_table_pointer, 
                    schema_ref, row_count, time_range_start, time_range_end, 
                    inputs, description, status
                ) VALUES (
                    :id, :research_id, :artifact_id, :source_mcp, :db_table_pointer,
                    :schema_ref, :row_count, :time_range_start, :time_range_end,
                    :inputs, :description, :status
                )
            """)
            await session.execute(catalog_stmt, {
                "id": catalog_id,
                "research_id": r_uuid,
                "artifact_id": artifact_id,
                "source_mcp": source_mcp,
                "db_table_pointer": db_pointer,
                "schema_ref": schema_ref,
                "row_count": row_count,
                "time_range_start": time_start,
                "time_range_end": time_end,
                "inputs": json.dumps(inputs) if inputs else None,
                "description": "Generating summary...",
                "status": "PENDING"
            })
            
            await session.commit()
            
            # Return catalog_id and sample_json to spawn background task
            return str(catalog_id), sample_json
            
        except Exception as e:
            await session.rollback()
            raise e
