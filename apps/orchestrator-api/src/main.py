import os
import asyncio
import json
import uuid
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from .database import init_duckdb, close_duckdb, get_pg_session, get_duckdb_conn
from .context.workspace import ingest_to_db, update_catalog_summary
from .graph.graph_builder import compile_graph

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

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend-ui:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== EXISTING ENDPOINTS =====

class IngestRequest(BaseModel):
    research_id: str
    artifact_id: str
    source_mcp: str
    raw_json: Any
    inputs: Optional[Dict[str, Any]] = None

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


# ===== RESEARCH SSE ENDPOINTS =====

def serialize_message(msg: BaseMessage) -> dict:
    """Convert a LangChain message to a JSON-serializable dict."""
    return {
        "type": getattr(msg, "type", "unknown"),
        "content": msg.content if isinstance(msg.content, str) else str(msg.content),
        "name": getattr(msg, "name", None),
    }

def serialize_state_update(node_data: dict) -> dict:
    """Convert a node state update to a JSON-serializable dict."""
    result = {}
    for key, value in node_data.items():
        if key == "messages" and isinstance(value, list):
            result["messages"] = [serialize_message(m) for m in value]
        elif isinstance(value, list):
            result[key] = [str(v) for v in value]
        else:
            result[key] = value
    return result

def detect_interrupt_type(state_values: dict) -> dict:
    """Detect what kind of human input the graph is waiting for based on state."""
    current_phase = state_values.get("current_phase", "scoping")
    next_agent = state_values.get("next_agent", None)
    messages = state_values.get("messages", [])
    
    # Get the last AI message content
    last_ai_content = ""
    last_ai_name = ""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai":
            last_ai_content = msg.content if isinstance(msg.content, str) else str(msg.content)
            last_ai_name = getattr(msg, "name", "") or ""
            break
    
    if current_phase == "scoping_review":
        return {
            "type": "brief_review",
            "message": last_ai_content,
            "research_brief": state_values.get("research_brief", ""),
            "selected_framework": state_values.get("selected_framework", ""),
        }
    elif next_agent == "ask_human":
        return {
            "type": "ask_human",
            "message": last_ai_content,
            "agent": last_ai_name,
        }
    else:
        # Default: scoping clarification
        return {
            "type": "clarification",
            "message": last_ai_content,
            "agent": last_ai_name,
        }


class StartResearchRequest(BaseModel):
    query: str

class RespondRequest(BaseModel):
    message: str


@app.post("/research/start")
async def start_research(request: StartResearchRequest):
    """Start a new research session. Returns an SSE stream of graph events."""
    thread_id = str(uuid.uuid4())
    research_id = str(uuid.uuid4())
    
    checkpointer = app.state.checkpointer
    compiled_graph = compile_graph(checkpointer=checkpointer)
    
    config = {
        "configurable": {"thread_id": thread_id, "research_id": research_id},
        "recursion_limit": 150,
    }
    
    inputs = {
        "messages": [HumanMessage(content=request.query)],
        "research_id": research_id,
    }
    
    async def event_generator():
        # Send init event with thread_id
        yield f"event: init\ndata: {json.dumps({'thread_id': thread_id, 'research_id': research_id})}\n\n"
        
        try:
            async for event in compiled_graph.astream(inputs, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    serializable = serialize_state_update(node_data)
                    yield f"event: node_update\ndata: {json.dumps({'node': node_name, 'data': serializable})}\n\n"
            
            # After stream ends, check if graph is paused for human input
            state = await compiled_graph.aget_state(config)
            if state.next:
                # Graph paused at a node — it's waiting for input to resume
                interrupt_info = detect_interrupt_type(state.values)
                yield f"event: interrupt\ndata: {json.dumps(interrupt_info)}\n\n"
            else:
                # Graph completed — check if it ended naturally or paused via Command(goto=END)
                values = state.values
                current_phase = values.get("current_phase", "")
                next_agent = values.get("next_agent", "")
                
                if current_phase == "complete":
                    # Research is truly finished
                    # Extract final report from analysis_reports
                    reports = values.get("analysis_reports", [])
                    final_report = reports[-1] if reports else "No report generated."
                    yield f"event: complete\ndata: {json.dumps({'status': 'complete', 'final_report': final_report})}\n\n"
                else:
                    # Graph ended via Command(goto=END) — human input needed
                    interrupt_info = detect_interrupt_type(values)
                    yield f"event: interrupt\ndata: {json.dumps(interrupt_info)}\n\n"
                    
        except Exception as e:
            error_info = {
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
            yield f"event: error\ndata: {json.dumps(error_info)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/research/{thread_id}/respond")
async def respond_to_research(thread_id: str, request: RespondRequest):
    """Send a human response to resume a paused research graph. Returns an SSE stream."""
    checkpointer = app.state.checkpointer
    compiled_graph = compile_graph(checkpointer=checkpointer)
    
    # Get current state to find research_id
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        current_state = await compiled_graph.aget_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {str(e)}")
    
    if not current_state.values:
        raise HTTPException(status_code=404, detail="No state found for this thread.")
    
    research_id = current_state.values.get("research_id", "")
    config["configurable"]["research_id"] = research_id
    config["recursion_limit"] = 150
    
    # Resume by invoking with the human message appended
    inputs = {
        "messages": [HumanMessage(content=request.message)],
    }
    
    async def event_generator():
        try:
            async for event in compiled_graph.astream(inputs, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    serializable = serialize_state_update(node_data)
                    yield f"event: node_update\ndata: {json.dumps({'node': node_name, 'data': serializable})}\n\n"
            
            # Check if graph paused again or completed
            state = await compiled_graph.aget_state(config)
            if state.next:
                interrupt_info = detect_interrupt_type(state.values)
                yield f"event: interrupt\ndata: {json.dumps(interrupt_info)}\n\n"
            else:
                values = state.values
                current_phase = values.get("current_phase", "")
                
                if current_phase == "complete":
                    reports = values.get("analysis_reports", [])
                    final_report = reports[-1] if reports else "No report generated."
                    yield f"event: complete\ndata: {json.dumps({'status': 'complete', 'final_report': final_report})}\n\n"
                else:
                    interrupt_info = detect_interrupt_type(values)
                    yield f"event: interrupt\ndata: {json.dumps(interrupt_info)}\n\n"
                    
        except Exception as e:
            error_info = {
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
            yield f"event: error\ndata: {json.dumps(error_info)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/research/{thread_id}/state")
async def get_research_state(thread_id: str):
    """Get the current state of a research thread (for page refresh / reconnection)."""
    checkpointer = app.state.checkpointer
    compiled_graph = compile_graph(checkpointer=checkpointer)
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        state = await compiled_graph.aget_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {str(e)}")
    
    if not state.values:
        raise HTTPException(status_code=404, detail="No state found for this thread.")
    
    values = state.values
    messages = values.get("messages", [])
    
    # Determine if graph is waiting for input
    is_interrupted = bool(state.next) or (
        values.get("current_phase", "") not in ("complete", "") 
        and values.get("current_phase", "") != "collection"
        and values.get("current_phase", "") != "analysis"
    )
    
    # If the graph ended via goto=END and isn't "complete", it's waiting for input
    if not state.next and values.get("current_phase", "") not in ("complete",):
        next_agent = values.get("next_agent", "")
        current_phase = values.get("current_phase", "")
        if current_phase in ("scoping", "scoping_review") or next_agent == "ask_human":
            is_interrupted = True
    
    interrupt_info = None
    if is_interrupted:
        interrupt_info = detect_interrupt_type(values)
    
    return {
        "thread_id": thread_id,
        "research_id": values.get("research_id", ""),
        "current_phase": values.get("current_phase", "scoping"),
        "next_agent": values.get("next_agent", None),
        "research_brief": values.get("research_brief", None),
        "selected_framework": values.get("selected_framework", None),
        "messages": [serialize_message(m) for m in messages],
        "is_interrupted": is_interrupted,
        "interrupt_info": interrupt_info,
        "analysis_reports": values.get("analysis_reports", []),
    }
