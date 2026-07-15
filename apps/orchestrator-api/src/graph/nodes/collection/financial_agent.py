from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_utils import get_chat_groq
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
)
from graph.tools.common_tools import think
from graph.tools.analytics_tools import read_catalog
from graph.nodes.collection.collection_utils import create_thinking_react_agent

model = get_chat_groq(model="qwen/qwen3-32b", temperature=0.1)

FINANCIAL_SYSTEM_PROMPT = """You are the Financial Intelligence Agent. Collect public company financial data using Alpha Vantage tools. Do NOT analyze.

CRITICAL RULES & WORKFLOW:
1. ALWAYS use the `think` tool before and after any other tool call to outline strategy and reflect. Keep reflections concise.
2. STEP 1: ALWAYS call `read_catalog` first to check if the requested data already exists in the database. If it exists (e.g., `income_statement_msft` is already present), you MUST skip fetching it and just report that it was found. DO NOT fetch the same data twice!
3. If ticker is unknown, ALWAYS use `symbol_search` first. Trust its results. If private/unlisted, report it and stop.
4. Use ONLY requested tools. Do not verify symbols with `company_overview`.
5. STRICT SCHEMAS: Only pass a `symbol` to fundamental tools (e.g. cash_flow). They return multi-year data by default.
6. NEVER hallucinate data or tool arguments. Do NOT re-call tools just to verify artifact IDs.

OUTPUT:
Write a concise report listing collected artifacts (with IDs), summarizing raw data, and noting any gaps.
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
    read_catalog,
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
            HumanMessage(content=f"Task:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 30, "configurable": {"research_id": research_id}}
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
