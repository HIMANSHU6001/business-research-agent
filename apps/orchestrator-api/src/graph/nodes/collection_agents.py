from src.graph.state import ResearchState
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from src.graph.tools.collection_tools import (
    fetch_financial_data,
    fetch_trend_data,
    # Data360 macro tools
    data360_search_indicators,
    data360_get_disaggregation,
    data360_get_data,
    data360_summarize_data,
    data360_rank_countries,
    data360_compare_countries,
)

model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1)

MACRO_SYSTEM_PROMPT = """You are the Macro Economic Intelligence Agent for the Business Research Agent system.

Your sole purpose is to collect country-level macroeconomic evidence from the World Bank Data360 database.
You collect facts — you do NOT analyze, interpret, or draw conclusions.

## Workflow (follow this order strictly):
1. Use data360_search_indicators to find the correct indicator ID and database ID.
   - Provide a clear topic query (e.g. "GDP per capita", "inflation rate", "unemployment").
   - Do NOT combine multiple topics in one query string.
2. Use data360_get_disaggregation to confirm the country is covered and to see available years.
3. Use data360_get_data to fetch raw time-series data.
   - IMPORTANT: You will receive a confirmation string, not the actual rows. This is expected.
   - The raw data is automatically stored in the workspace database for downstream analysis.
4. Optionally use data360_summarize_data, data360_rank_countries, or data360_compare_countries
   for lightweight statistical summaries you can include directly in your report.

## Critical rules:
- Always pass start_year and end_year as integers (e.g. 2019, not "2019").
- Pass the research_id from the brief to all tool calls that require it.
- Never guess indicator IDs — always search first.
- Do NOT hallucinate data values. Only reference what tools return to you.

## Output:
Write a concise Macro Economic Intelligence Report that:
- Lists every indicator fetched (name, database, country, year range)
- States the artifact IDs created (from data360_get_data confirmations)
- Includes any statistical highlights from summarize/rank/compare tools
- Notes any gaps (e.g. indicator not available for a country)
"""

financial_agent_executor = create_react_agent(model, tools=[fetch_financial_data])
macro_agent_executor = create_react_agent(model, tools=[
    data360_search_indicators,
    data360_get_disaggregation,
    data360_get_data,
    data360_summarize_data,
    data360_rank_countries,
    data360_compare_countries,
])
trends_agent_executor = create_react_agent(model, tools=[fetch_trend_data])

async def run_financial_agent(state: ResearchState) -> dict:
    """Collects company-specific financial evidence via Alpha Vantage MCP."""
    print(f"--- FINANCIAL INTELLIGENCE: {state['research_id']} ---")
    research_brief = state.get("research_brief") or ""
    research_id = state.get("research_id") or ""
    
    inputs = {
        "messages": [
            SystemMessage(content="You are the Financial Intelligence Agent. Use your tools to gather data based on the brief. Write a concise topic report of what datasets you collected."),
            HumanMessage(content=f"Brief: {research_brief}\nResearch ID: {research_id}")
        ]
    }
    
    response = await financial_agent_executor.ainvoke(inputs)
    final_response = response["messages"][-1]
    
    return {
        "messages": [AIMessage(content=final_response.content, name="financial_agent")]
    }

async def run_macro_agent(state: ResearchState) -> dict:
    """Collects country-level macroeconomic indicators via Data 360 MCP."""
    print(f"--- MACRO ECONOMIC INTELLIGENCE: {state['research_id']} ---")
    research_brief = state.get("research_brief") or ""
    research_id = state.get("research_id") or ""
    
    inputs = {
        "messages": [
            SystemMessage(content=MACRO_SYSTEM_PROMPT),
            HumanMessage(content=f"Research Brief:\n{research_brief}\n\nResearch ID: {research_id}\n\nCollect all relevant macroeconomic indicators for this research brief.")
        ]
    }
    
    response = await macro_agent_executor.ainvoke(inputs)
    final_response = response["messages"][-1]
    
    return {
        "messages": [AIMessage(content=final_response.content, name="macro_agent")]
    }

async def run_trends_agent(state: ResearchState) -> dict:
    """Collects consumer demand and search trend evidence via Google Trends MCP."""
    print(f"--- TRENDS INTELLIGENCE: {state['research_id']} ---")
    research_brief = state.get("research_brief") or ""
    research_id = state.get("research_id") or ""
    
    inputs = {
        "messages": [
            SystemMessage(content="You are the Trends Intelligence Agent. Use your tools to gather data based on the brief. Write a concise topic report of what datasets you collected."),
            HumanMessage(content=f"Brief: {research_brief}\nResearch ID: {research_id}")
        ]
    }
    
    response = await trends_agent_executor.ainvoke(inputs)
    final_response = response["messages"][-1]
    
    return {
        "messages": [AIMessage(content=final_response.content, name="trends_agent")]
    }
