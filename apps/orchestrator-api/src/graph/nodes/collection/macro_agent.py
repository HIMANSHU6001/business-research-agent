from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_utils import get_chat_groq, DEFAULT_MODEL
from graph.state import ResearchState
from graph.tools.macro_tools import (
    data360_search_indicators,
    data360_get_disaggregation,
    data360_get_data,
    data360_summarize_data,
    data360_rank_countries,
    data360_compare_countries,
)
from graph.tools.analytics_tools import read_catalog
from graph.nodes.collection.collection_utils import create_react_agent

model = get_chat_groq(model=DEFAULT_MODEL, temperature=0.1)

MACRO_SYSTEM_PROMPT = """You are the Macro Economic Intelligence Agent. Collect country-level data from World Bank Data360. Do NOT analyze.

CRITICAL RULES & WORKFLOW:
1. BEFORE fetching data, ALWAYS use `read_catalog` to check if the data already exists in the database. DO NOT fetch the same data twice.
2. For EACH macroeconomic indicator requested, repeat the following steps:
   a. Use `data360_search_indicators` with a clear query.
   b. Select the BEST matching indicator ID from the search results.
   c. Use `data360_get_disaggregation` on it to check coverage.
   d. Use `data360_get_data` on it to fetch raw data (returns a confirmation string).
      - CRITICAL: You MUST pass the EXACT `idno` string returned by the search tool. DO NOT strip prefixes!
3. Do NOT call tools in parallel. Call ONE tool, wait for the result, then call the next.
4. Stop and write your report only when ALL requested indicators are collected. (Only use summarize/rank/compare tools if explicitly requested).
5. NEVER guess indicator IDs. Pass years as integers.
6. NEVER hallucinate data, success messages, or Artifact IDs. If a tool fails, report the exact error.
7. Do NOT re-call tools to verify artifact IDs.
8. MISSING DATA HANDLING: If a tool returns an empty result, or an error message indicating no data is available for the requested country/indicator, this means the required data is NOT available. You MUST explicitly state in your report exactly which indicator and country was missing (e.g. "The requested GDP data for India is not available") and do not attempt to fetch it again.

OUTPUT:
Write a concise report listing fetched indicators, Artifact IDs, statistical highlights, and any gaps/errors. If data was missing or unavailable, explicitly state exactly which data is not available."""

macro_tools = [
    data360_search_indicators,
    data360_get_disaggregation,
    data360_get_data,
    data360_summarize_data,
    data360_rank_countries,
    data360_compare_countries,
    read_catalog
]

macro_agent_executor = create_react_agent(model, macro_tools, parallel_tool_calls=False)

async def run_macro_agent(state: ResearchState) -> dict:
    """Collects country-level macroeconomic indicators via Data 360 MCP."""
    print(f"--- MACRO ECONOMIC INTELLIGENCE: {state['research_id']} ---")
    research_id = state.get("research_id") or ""
    agent_task = state.get("agent_task") or "Collect all relevant macroeconomic indicators."
    
    inputs = {
        "messages": [
            SystemMessage(content=MACRO_SYSTEM_PROMPT),
            HumanMessage(content=f"Task:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 30, "configurable": {"research_id": research_id}}
    response = await macro_agent_executor.ainvoke(inputs, config=config)
    final_response = response["messages"][-1]
    
    try:
        from context.knowledge import KnowledgeManager
        km = KnowledgeManager()
        await km.store_context(
            research_id=research_id,
            agent_namespace="macro_agent",
            task_context=agent_task,
            content=final_response.content
        )
    except Exception as e:
        print(f"Failed to store context in pgVector for macro_agent: {e}")
    
    return {
        "messages": [AIMessage(content=final_response.content, name="macro_agent")]
    }
