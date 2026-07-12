from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_groq import ChatGroq
from graph.state import ResearchState
from graph.tools.common_tools import think
from graph.tools.analytics_tools import (
    read_catalog,
    get_schema,
    calculate_summary_statistics
)
from graph.nodes.collection.collection_utils import create_thinking_react_agent

model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1)

QUANTITATIVE_SYSTEM_PROMPT = """You are the Quantitative Analysis Agent for the Business Research Agent system.

Your sole purpose is to perform deterministic quantitative analysis on collected datasets by orchestrating statistical tools.
You DO NOT perform statistical computation yourself — you select the appropriate tool and interpret the output.
You NEVER see raw datasets directly. You only see metadata and statistical summaries.

## MANDATORY THINKING STEP (CRITICAL):
- You MUST invoke the `think` tool as your VERY FIRST step to outline your strategy before calling any other tool.
- You MUST invoke the `think` tool after receiving results from any tool, to reflect on your progress.
- Do not call any database or analytics tools without calling the `think` tool in the step immediately preceding it.
- Reflection Overwrite Rule: When calling `think`, write a fresh, concise reflection containing ONLY your current thoughts, findings, and immediate next steps. 

## Workflow (follow this order strictly):
1. **Inspect Workspace Catalog**: Use `read_catalog` to discover what datasets have been collected for this research session. Note their `artifact_id` and `parquet_path`.
2. **Inspect Schema**: For each relevant dataset, use `get_schema` with the `artifact_id` to discover available columns and their data types.
3. **Execute Analytics**: Use `calculate_summary_statistics` (or other available MCP tools) on the `parquet_path` and a specific numeric column to calculate statistics.
4. **Synthesize**: Interpret the mathematical findings returned by the tools.

## Critical rules:
- Always pass the `research_id` to `read_catalog`.
- Pass exact `parquet_path` strings to the analytics tools, exactly as they are returned by `read_catalog`.
- Only run analytics on columns that `get_schema` confirms are numeric.
- Do NOT hallucinate data or numbers. Only report exactly what the tools return.

## Output:
Write an Evidence-Backed Quantitative Report that:
- Summarizes the key numerical findings.
- States the exact statistics (mean, min, max, etc.) for the relevant variables.
- Mentions which datasets (artifact IDs) these numbers were derived from.
- Does NOT attempt to interpret the "why" behind the numbers (save that for the qualitative synthesis).
"""

quantitative_tools = [
    read_catalog,
    get_schema,
    calculate_summary_statistics,
    think,
]

quantitative_agent_executor = create_thinking_react_agent(model, quantitative_tools)

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
            HumanMessage(content=f"Research ID: {research_id}\n\nTask:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 25}
    response = await quantitative_agent_executor.ainvoke(inputs, config=config)
    final_response = response["messages"][-1]
    
    new_reports = reports.copy()
    new_reports.append("## Quantitative Findings\n" + final_response.content)

    return {
        "analysis_reports": new_reports,
        "next_agent": "analysis_supervisor"
    }
