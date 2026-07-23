import os
import json
import uuid
import datetime
import asyncio
import pandas as pd
from sqlalchemy import text
from llm_utils import get_chat_model, DEFAULT_MODEL
from langchain_core.prompts import ChatPromptTemplate
from database import get_duckdb_conn, AsyncSessionLocal

async def generate_semantic_summary(artifact_id: str, sample_data_json: str, source_mcp: str) -> str:
    """Calls the Groq LLM to generate a 2-3 sentence semantic summary of the data."""
    try:
        llm = get_chat_model(
            model=DEFAULT_MODEL,
            temperature=0.0,
            max_tokens=150,
        )
        system_prompt = "You are a helpful data cataloging assistant."
        user_prompt = """Write a 2-3 sentence semantic summary of the following dataset utility.
    Dataset ID: {artifact_id}
    Source MCP: {source_mcp}
    Sample Data (JSON):
    {sample_data}

    Focus on what this data represents, its granularity, and its potential utility for business research. Keep it concise, professional, and strictly under 3 sentences."""
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
        
        chain = prompt | llm
        response = await chain.ainvoke({
            "artifact_id": artifact_id,
            "source_mcp": source_mcp,
            "sample_data": sample_data_json[:2000]
        })
        return str(response.content).strip()
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

async def ingest_to_db(research_id: str, artifact_id: str, source_mcp: str, raw_json: any, inputs: dict = None, citation: str = None) -> str:
    """Ingest raw JSON payload to Parquet via DuckDB and register metadata in Postgres."""
    # Ensure research_id is a UUID, fallback to zero-UUID if missing (for Studio testing)
    try:
        r_uuid = uuid.UUID(research_id)
    except (ValueError, TypeError):
        r_uuid = uuid.UUID("00000000-0000-0000-0000-000000000000")
        research_id = str(r_uuid)
    
    def _process_data():
        # 1. Flatten the raw_json and convert to Pandas DataFrame
        data_to_load = raw_json
        if isinstance(raw_json, dict):
            # Google Trends special cases
            if "interest_over_time" in raw_json:
                timeline = raw_json["interest_over_time"].get("timeline_data", [])
                # Pivot the timeline_data so each query becomes its own numeric column (Wide format)
                pivoted_data = []
                for row in timeline:
                    new_row = {"date": row.get("date"), "timestamp": row.get("timestamp")}
                    for val_obj in row.get("values", []):
                        query_name = val_obj.get("query", "value")
                        new_row[query_name] = val_obj.get("extracted_value") or val_obj.get("value")
                    pivoted_data.append(new_row)
                data_to_load = pivoted_data
            elif "interest_by_region" in raw_json and isinstance(raw_json["interest_by_region"], list):
                data_to_load = raw_json["interest_by_region"]
            elif "compared_breakdown_by_region" in raw_json and isinstance(raw_json["compared_breakdown_by_region"], list):
                data_to_load = raw_json["compared_breakdown_by_region"]
            else:
                # Alpha Vantage financial payload flattening
                symbol = raw_json.get("symbol", "")
                
                # Check for Alpha Vantage nested list keys
                av_keys = ["annualReports", "quarterlyReports", "annualEarnings", "quarterlyEarnings"]
                found_av_list = None
                for k in av_keys:
                    if k in raw_json and isinstance(raw_json[k], list):
                        found_av_list = raw_json[k]
                        break
                        
                if found_av_list is not None:
                    # Flatten it by injecting the symbol into each row
                    flattened = []
                    for row in found_av_list:
                        new_row = {"symbol": symbol}
                        new_row.update(row)
                        flattened.append(new_row)
                    data_to_load = flattened
                else:
                    # Default generic extraction
                    for key in ["data", "results", "entries", "records"]:
                        if key in raw_json and isinstance(raw_json[key], list):
                            data_to_load = raw_json[key]
                            break
            if data_to_load is None:
                data_to_load = [raw_json]
        
        df = pd.json_normalize(data_to_load)
        
        # We no longer force numeric coercion here because DuckDB and Python scripts
        # executed by the autonomous agent can handle type casting on demand.
            
        # Drop columns that are completely empty/null to save schema token space
        df.dropna(axis=1, how='all', inplace=True)
            
        if len(df.columns) == 0:
            raise ValueError("Data payload is completely empty or null. Nothing to ingest.")
            
        # Parquet doesn't natively support nested lists/dicts well without schema definition,
        # so convert any remaining complex object columns to JSON strings.
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if first non-null element is dict or list
                first_valid = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if isinstance(first_valid, (list, dict)):
                    df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)
        
        db_dir = os.getenv("DUCKDB_DATA_DIR", "/shared/workspaces")
        research_dir = os.path.join(db_dir, str(research_id))
        os.makedirs(research_dir, exist_ok=True)
        parquet_path = os.path.join(research_dir, f"{artifact_id}.parquet")
        
        # 2. Execute DuckDB write
        conn = get_duckdb_conn()
        conn.register("my_df", df)
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
        
        return row_count, time_start, time_end, schema_cols, schema_ref, sample_json

    row_count, time_start, time_end, schema_cols, schema_ref, sample_json = await asyncio.to_thread(_process_data)
    
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
                    inputs, description, status, citation
                ) VALUES (
                    :id, :research_id, :artifact_id, :source_mcp, :db_table_pointer,
                    :schema_ref, :row_count, :time_range_start, :time_range_end,
                    :inputs, :description, :status, :citation
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
                "status": "PENDING",
                "citation": citation
            })
            
            await session.commit()
            
            # Spawn background LLM summarization task automatically
            asyncio.create_task(
                update_catalog_summary(catalog_id, artifact_id, sample_json, source_mcp)
            )
            
            # Return catalog_id and sample_json to caller
            return str(catalog_id), sample_json
            
        except Exception as e:
            await session.rollback()
            raise e

async def get_citations_for_research(research_id: str) -> list[str]:
    """Fetch all automated citations associated with a research_id."""
    try:
        r_uuid = uuid.UUID(research_id)
    except (ValueError, TypeError):
        return []
        
    async with AsyncSessionLocal() as session:
        stmt = text("""
            SELECT citation 
            FROM semantic_catalog 
            WHERE research_id = :research_id 
              AND citation IS NOT NULL
        """)
        result = await session.execute(stmt, {"research_id": r_uuid})
        citations = []
        for row in result:
            citations.append(row[0])
        return citations
