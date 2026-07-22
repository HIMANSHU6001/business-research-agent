from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_utils import get_chat_groq, QUANTITATIVE_MODEL
from graph.state import ResearchState
from graph.tools.analytics_tools import (
    read_catalog,
    get_schema,
    get_sample_data,
    run_duckdb_query,
    execute_python_code
)
from graph.nodes.collection.collection_utils import create_react_agent

model = get_chat_groq(model=QUANTITATIVE_MODEL, temperature=0.1)

QUANTITATIVE_SYSTEM_PROMPT = """You are the Quantitative Analysis Agent.
You execute precise data manipulation and statistical tools on collected data. 
You are an autonomous data scientist. You do NOT try to draw thematic business insights, but you DO compute statistics.
You are capped at 35 recursion limit.

# RULES (CRITICAL):
1. USE REAL DATA: Use `read_catalog` to find valid `artifact_id`s. NEVER guess or make up datasets.
2. CHECK SCHEMAS FIRST: Use `get_schema` (pass `artifact_ids` as a list) to see exact column names and data types. NEVER query a column that is not in the schema.
3. DATA NORMALIZATION: If two datasets have mismatched temporal keys (e.g., 'TIME_PERIOD' integer years vs 'fiscalDateEnding' string dates), you MUST use `execute_python_code` to write a pandas script to extract the years and join the data properly before calculating stats.
4. PYTHON SANDBOX: 
   - ALWAYS `import pandas as pd`, `from scipy import stats`.
   - Use the exact `file_path` returned by `read_catalog` to load the data (e.g. `pd.read_parquet(file_path)`).
   - You MUST use `print()` to output your statistical findings, otherwise you will not see the result.
   - WARNING: Do NOT print raw dataframes unless absolutely necessary, and always use `.head()` if you do. Printing too much data will bloat your context window and crash the system. Only print aggregated statistics (e.g., correlation coefficients, p-values).
   - If your code crashes with a Traceback, read the error and try again.
5. DUCKDB SQL:
   - Use `run_duckdb_query` for quick joins, filtering, and simple stats (avg, corr, etc).
   - Use `SELECT * FROM read_parquet('file_path')` using the exact `file_path` returned by `read_catalog`.
   - WARNING: Do NOT use `SELECT *` without a `LIMIT` clause on large datasets. Fetching thousands of rows will bloat your context window and crash the system. Only fetch aggregations or a few sample rows.
6. STOPPING CONDITION: When your statistical task is complete or if data is totally missing, STOP calling tools. Write your final numerical report as plain text to signal completion.

# WORKFLOW:
1. `read_catalog`: Find the dataset IDs.
2. `get_schema`: Find the exact column names.
3. `get_sample_data`: View the top 4 rows of the dataset to understand the actual data before analyzing.
4. Choose either `run_duckdb_query` or `execute_python_code` to process the data and compute the statistics requested.
5. Output your Evidence-Backed Quantitative Report in plain text.
"""

quantitative_tools = [
    read_catalog,
    get_schema,
    get_sample_data,
    run_duckdb_query,
    execute_python_code
]

quantitative_agent_executor = create_react_agent(model, quantitative_tools)

async def run_quantitative_agent(state: ResearchState) -> dict:
    print(f"--- QUANTITATIVE ANALYSIS AGENT: {state['research_id']} ---")
    
    research_id = state.get("research_id") or ""
    agent_task = state.get("agent_task") or "Perform quantitative analysis on collected datasets."
    reports = state.get("analysis_reports", [])
    if reports is None:
        reports = []
        
    print(f"Task: {agent_task}")
    
    inputs = {
        "messages": [
            SystemMessage(content=QUANTITATIVE_SYSTEM_PROMPT),
            HumanMessage(content=f"Task:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 35, "configurable": {"research_id": research_id}}
    response = await quantitative_agent_executor.ainvoke(inputs, config=config)
    final_response = response["messages"][-1]
    
    content = final_response.content
    if isinstance(content, list):
        text_content = "\\n".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
    else:
        text_content = str(content)
    
    new_reports = reports.copy()
    new_reports.append("## Quantitative Findings\\n" + text_content)

    return {
        "analysis_reports": new_reports,
        "next_agent": "analysis_supervisor"
    }
