from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_groq import ChatGroq
from graph.state import ResearchState
from graph.tools.financial_tools import (
    symbol_search,
    company_overview,
    income_statement,
    balance_sheet,
    cash_flow,
    earnings,
    earnings_calendar,
    listing_status,
    ipo_calendar,
    news_sentiment,
    earnings_call_transcript,
    top_gainers_losers,
    insider_transactions,
    institutional_holdings,
    analytics_fixed_window,
    analytics_sliding_window,
)
from graph.tools.common_tools import think
from graph.nodes.collection.collection_utils import create_thinking_react_agent

model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1)

FINANCIAL_SYSTEM_PROMPT = """You are the Financial Intelligence Agent for the Business Research Agent system.

Your sole purpose is to collect public company financial data and indicators using Alpha Vantage tools.
You collect facts — you do NOT analyze, interpret, or draw conclusions.

## MANDATORY THINKING STEP (CRITICAL):
- You MUST invoke the `think` tool as your VERY FIRST step to outline your strategy before calling any other tool.
- You MUST invoke the `think` tool after receiving results from any tool, to reflect on your progress and assess research gaps.
- Reflection Overwrite Rule: When calling `think`, write a fresh, concise reflection containing ONLY your current thoughts, findings, and immediate next steps.

## Workflow (follow this order strictly):
1. Resolve the company name to a ticker symbol using `symbol_search`.
   - IMPORTANT: Always use `symbol_search` first to find/confirm the ticker symbol of the company if it is not explicitly provided in ticker format (e.g. MSFT).
   - If the search returns no results or indicates it is a private company, explicitly report in your final message that the company is private/unlisted and no data could be retrieved.
2. For public companies, use the appropriate tools to collect information (e.g. `company_overview`, `income_statement`, `balance_sheet`, `cash_flow`, `earnings`, etc.) as required by the research brief.
   - Note that fundamental data tools (overview, financial statements, etc.) will return a confirmation string and automatically ingest the data.
   - Other intelligence tools (news sentiment, insider transactions, etc.) will return raw data for you to summarize in your report.

## Critical rules:
- Pass the research_id to all tool calls that require it.
- Do NOT hallucinate data values. Only reference what tools return to you.
- Always call Think tool after a tool call is done and reflect on your next steps.
- Remember you have limited turns only so stop when you have enough data to answer confidently.

## Output:
Write a concise Financial Intelligence Report that:
- Lists all financial data and artifacts successfully collected (including artifact IDs).
- Summarizes non-intercepted data (e.g. news sentiment highlights, top gainers, insider transactions).
- Notes any gaps (e.g. private company status, API rate limits).
"""

financial_tools = [
    symbol_search,
    company_overview,
    income_statement,
    balance_sheet,
    cash_flow,
    earnings,
    earnings_calendar,
    listing_status,
    ipo_calendar,
    news_sentiment,
    earnings_call_transcript,
    top_gainers_losers,
    insider_transactions,
    institutional_holdings,
    analytics_fixed_window,
    analytics_sliding_window,
    think,
]

financial_agent_executor = create_thinking_react_agent(model, financial_tools)

async def run_financial_agent(state: ResearchState) -> dict:
    """Collects company-specific financial evidence via Alpha Vantage MCP."""
    print(f"--- FINANCIAL INTELLIGENCE: {state['research_id']} ---")
    research_id = state.get("research_id") or ""
    agent_task = state.get("agent_task") or "Collect all relevant financial indicators."
    
    inputs = {
        "messages": [
            SystemMessage(content=FINANCIAL_SYSTEM_PROMPT),
            HumanMessage(content=f"Research ID: {research_id}\n\nTask:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 25}
    response = await financial_agent_executor.ainvoke(inputs, config=config)
    final_response = response["messages"][-1]
    
    try:
        from context.knowledge import KnowledgeManager
        km = KnowledgeManager()
        await km.store_context(
            research_id=research_id,
            agent_namespace="financial_agent",
            task_context=agent_task,
            content=final_response.content
        )
    except Exception as e:
        print(f"Failed to store context in pgVector for financial_agent: {e}")
    
    return {
        "messages": [AIMessage(content=final_response.content, name="financial_agent")]
    }
