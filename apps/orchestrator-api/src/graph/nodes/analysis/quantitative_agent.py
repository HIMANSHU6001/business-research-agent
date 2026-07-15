from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_utils import get_chat_groq
from graph.state import ResearchState
from graph.tools.common_tools import think
from graph.tools.analytics_tools import (
    read_catalog,
    get_schema,
    get_sample_data,
    get_descriptive_stats,
    calculate_correlation,
    execute_t_test,
    calculate_trendline
)
from graph.nodes.collection.collection_utils import create_thinking_react_agent

model = get_chat_groq(model="qwen/qwen3-32b", temperature=0.1)

QUANTITATIVE_SYSTEM_PROMPT = """You are the Quantitative Analysis Agent.
You execute precise statistical tools on collected data. You do NOT perform calculations yourself. You do NOT try to draw insights or any interpretation from the results of the tests
You are capped at 35 recursion limit
# RULES (CRITICAL):
1. USE REAL DATA: Use `read_catalog` to find valid `artifact_id`s. NEVER guess or make up datasets.
2. CHECK SCHEMAS FIRST: Use `get_schema` (pass `artifact_ids` as a list) to see exact column names. NEVER query a column that is not in the schema.
3. HANDLE MISSING/COMPLEX COLUMNS: If the column you need (e.g. 'revenue') is NOT explicitly listed in the schema as a flat numeric column (e.g., if you only see 'annualReports' which is VARCHAR/JSON), you MUST STOP CALLING TOOLS immediately. Output a final plain text report stating the exact column is missing or is too complex to analyze directly. DO NOT loop by calling get_schema or read_catalog again.
4. FILTERING: Use the `query_filter` parameter in statistical tools to slice data BEFORE analysis when required (e.g. `query_filter="date >= '2023-01-01'"`). This takes standard Pandas query strings.
5. NO CREATIVITY: You are a strict data processor. Do not invent variables like 'temperature' to correlate against.
6. STOPPING CONDITION: When your task is complete or if data is missing, STOP calling tools. Write your final numerical report as plain text to signal completion.

# WORKFLOW:
1. `think`: Reflect on your goal.
2. `read_catalog`: Find the dataset IDs.
3. `get_schema`: Find the numeric columns.
4. `get_sample_data`: You MUST call this to view the top 4 rows of the dataset to understand the actual data before analyzing.
5. Call statistical tools (e.g. `get_descriptive_stats`, `calculate_correlation`, `execute_t_test`, `calculate_trendline`). If columns are missing or data sample looks unanalyzable, skip this step.
6. Output your Evidence-Backed Quantitative Report in plain text.
"""

quantitative_tools = [
    read_catalog,
    get_schema,
    get_sample_data,
    get_descriptive_stats,
    calculate_correlation,
    execute_t_test,
    calculate_trendline,
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
