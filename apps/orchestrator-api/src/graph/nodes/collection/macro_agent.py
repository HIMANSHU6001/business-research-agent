from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_utils import get_chat_groq
from graph.state import ResearchState
from graph.tools.macro_tools import (
    data360_search_indicators,
    data360_get_disaggregation,
    data360_get_data,
    data360_summarize_data,
    data360_rank_countries,
    data360_compare_countries,
)
from graph.tools.common_tools import think
from graph.tools.analytics_tools import read_catalog
from graph.nodes.collection.collection_utils import create_thinking_react_agent

model = get_chat_groq(model="qwen/qwen3-32b", temperature=0.1)

MACRO_SYSTEM_PROMPT = """You are the Macro Economic Intelligence Agent. Collect country-level data from World Bank Data360. Do NOT analyze.

CRITICAL RULES & WORKFLOW:
1. ALWAYS use the `think` tool before and after any other tool call to outline strategy and reflect.
2. BEFORE fetching data, ALWAYS use `read_catalog` to check if the data already exists in the database. DO NOT fetch the same data twice.
3. Step 1: Use `data360_search_indicators` with a clear query.
3. Step 2: Select EXACTLY ONE indicator. Ignore others.
4. Step 3: Use `data360_get_disaggregation` on it to check coverage.
5. Step 4: Use `data360_get_data` on it to fetch raw data (returns a confirmation string).
   - CRITICAL: You MUST pass the EXACT `idno` string returned by the search tool. DO NOT strip prefixes (e.g., if it says `WB_WDI_NY_GDP_MKTP_KD_ZG`, do NOT shorten it to `NY_GDP...`).
6. Step 5: Stop and write your report. (Only use summarize/rank/compare tools if explicitly requested).
7. NEVER guess indicator IDs. Pass years as integers.
8. NEVER hallucinate data, success messages, or Artifact IDs. If a tool fails, report the exact error.
9. Do NOT re-call tools to verify artifact IDs.

OUTPUT:
Write a concise report listing fetched indicators, Artifact IDs, statistical highlights, and any gaps/errors.
"""

macro_tools = [
    data360_search_indicators,
    data360_get_disaggregation,
    data360_get_data,
    data360_summarize_data,
    data360_rank_countries,
    data360_compare_countries,
    read_catalog,
    think,
]

macro_agent_executor = create_thinking_react_agent(model, macro_tools)

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
