from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_groq import ChatGroq
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
from graph.nodes.collection.collection_utils import create_thinking_react_agent

model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1)

MACRO_SYSTEM_PROMPT = """You are the Macro Economic Intelligence Agent for the Business Research Agent system.

Your sole purpose is to collect country-level macroeconomic evidence from the World Bank Data360 database.
You collect facts — you do NOT analyze, interpret, or draw conclusions.

## MANDATORY THINKING STEP (CRITICAL):
- You MUST invoke the `think` tool as your VERY FIRST step to outline your strategy before calling any other tool.
- You MUST invoke the `think` tool after receiving results from any tool, to reflect on your progress and assess research gaps.
- Do not call any database/data360 tools without calling the `think` tool in the step immediately preceding it.
- Reflection Overwrite Rule: When calling `think`, write a fresh, concise reflection containing ONLY your current thoughts, findings, and immediate next steps. 

## Workflow (follow this order strictly):
1. Use data360_search_indicators to find the correct indicator ID and database ID.
   - Provide a clear topic query (e.g. "GDP per capita", "inflation rate").
2. REVIEW THE SEARCH RESULTS AND SELECT EXACTLY ONE INDICATOR. Do NOT iterate through all search results. Ignore the rest.
3. Use data360_get_disaggregation ON THAT SINGLE INDICATOR ONLY to confirm the country is covered and to see available years.
4. Use data360_get_data ON THAT SINGLE INDICATOR ONLY to fetch raw time-series data.
   - IMPORTANT: You will receive a confirmation string, not the actual rows.
   - The raw data is automatically stored in the workspace database for downstream analysis.
5. Optionally use data360_summarize_data, data360_rank_countries, or data360_compare_countries.

## Critical rules:
- Always pass start_year and end_year as integers (e.g. 2019, not "2019").
- Pass the research_id to all tool calls that require it.
- Never guess indicator IDs — always search first.
- Do NOT hallucinate data values. Only reference what tools return to you.
- Always call Think tool after a tool call is done and reflect on your next steps.

## Output:
Write a concise Macro Economic Intelligence Report that:
- Lists every indicator fetched (name, database, country, year range)
- States the artifact IDs created (from data360_get_data confirmations)
- Includes any statistical highlights from summarize/rank/compare tools
- Notes any gaps (e.g. indicator not available for a country)

## ERROR HANDLING: 
If a tool returns an error message (e.g., "interception failed", "0 rows", or any exception), 
you MUST explicitly state that the data collection failed in your final report and include the exact error reason. 
Do NOT hallucinate a success message. Do NOT invent fake Artifact IDs.
"""

macro_tools = [
    data360_search_indicators,
    data360_get_disaggregation,
    data360_get_data,
    data360_summarize_data,
    data360_rank_countries,
    data360_compare_countries,
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
            HumanMessage(content=f"Research ID: {research_id}\n\nTask:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 25}
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
