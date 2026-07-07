import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.database import init_duckdb, close_duckdb, get_pg_session, get_duckdb_conn
from src.context.workspace import ingest_to_db, update_catalog_summary

# Keep raw postgresql:// connection string for LangGraph checkpointer
RAW_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres-db:5432/research_db")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DuckDB global connection
    print("Initializing DuckDB...")
    init_duckdb()
    
    # 2. Initialize LangGraph Postgres Checkpointer
    print("Initializing LangGraph Postgres Saver...")
    # AsyncPostgresSaver uses psycopg3, which uses postgresql://
    async with AsyncPostgresSaver.from_conn_string(RAW_DATABASE_URL) as checkpointer:
        # Create checkpoint tables if they don't exist
        await checkpointer.setup()
        app.state.checkpointer = checkpointer
        print("LangGraph Postgres Checkpointer setup completed.")
        yield
        
    # 3. Cleanup on shutdown
    print("Closing DuckDB...")
    close_duckdb()

app = FastAPI(
    title="Business Research Agent - Orchestrator API",
    version="1.0.0",
    lifespan=lifespan
)

class IngestRequest(BaseModel):
    research_id: str
    artifact_id: str
    source_mcp: str
    raw_json: any
    inputs: dict = None

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_pg_session)):
    try:
        # Verify PG connection
        await db.execute(text("SELECT 1"))
        pg_status = "healthy"
    except Exception as e:
        pg_status = f"unhealthy: {str(e)}"
        
    try:
        # Verify DuckDB connection
        conn = get_duckdb_conn()
        conn.execute("SELECT 1")
        duck_status = "healthy"
    except Exception as e:
        duck_status = f"unhealthy: {str(e)}"
        
    return {
        "status": "online",
        "databases": {
            "postgres": pg_status,
            "duckdb": duck_status
        }
    }

@app.post("/ingest")
async def ingest_artifact(request: IngestRequest, background_tasks: BackgroundTasks):
    try:
        catalog_id, sample_json = await ingest_to_db(
            research_id=request.research_id,
            artifact_id=request.artifact_id,
            source_mcp=request.source_mcp,
            raw_json=request.raw_json,
            inputs=request.inputs
        )
        
        # Enqueue the background LLM summarization task
        background_tasks.add_task(
            update_catalog_summary,
            catalog_id=catalog_id,
            artifact_id=request.artifact_id,
            sample_json=sample_json,
            source_mcp=request.source_mcp
        )
        
        return {
            "status": "success",
            "catalog_id": catalog_id,
            "message": "Ingestion initiated. LLM summary is processing in the background."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
