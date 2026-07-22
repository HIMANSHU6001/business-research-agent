from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_utils import get_chat_groq, DEFAULT_MODEL
from graph.state import ResearchState
from graph.tools.financial_tools import (
    symbol_search,
    company_overview,
    income_statement,
    balance_sheet,
    cash_flow,
    earnings,
    earnings_calendar,
    ipo_calendar,
)
from graph.tools.analytics_tools import read_catalog
from graph.nodes.collection.collection_utils import create_react_agent

model = get_chat_groq(model=DEFAULT_MODEL, temperature=0.1)

FINANCIAL_SYSTEM_PROMPT = """You are the Financial Intelligence Agent. Collect public company financial data using Alpha Vantage tools. Do NOT analyze.

CRITICAL RULES & WORKFLOW:
1. STEP 1: ALWAYS call `read_catalog` first to check if the requested data already exists in the database. If it exists (e.g., `income_statement_msft` is already present), you MUST skip fetching it and just report that it was found. DO NOT fetch the same data twice!
2. If ticker is unknown, ALWAYS use `symbol_search` first. Trust its results. If private/unlisted, report it and stop.
3. Use ONLY requested tools. Do not verify symbols with `company_overview`.
4. STRICT SCHEMAS: Only pass a `symbol` to fundamental tools (e.g. cash_flow). They return multi-year data by default.
5. CRITICAL ANTI-HALLUCINATION: The data-fetching tools (like income_statement) ONLY return a success confirmation string and an Artifact ID. They DO NOT return the actual raw numerical data to you.
6. NEVER hallucinate data, tool arguments, or numerical figures (like revenue amounts). Since you do not receive the raw numbers, you MUST NOT invent them. Do NOT re-call tools just to verify artifact IDs.
7. MISSING DATA HANDLING: If a tool returns an empty JSON object (e.g., `{}` or `Data payload is completely empty`), or a message about a `demo` API key limit, this means the required data is NOT available for this company. You MUST explicitly state in your report exactly which data was missing (e.g. "The requested income statement data for RELIANCE.BSE is not available") and do not attempt to fetch it again.

OUTPUT:
Write a concise report listing the datasets successfully collected and their corresponding Artifact IDs. If data was missing or unavailable, explicitly state exactly which data is not available. DO NOT attempt to summarize raw numerical data or quote specific financial figures (you do not have access to them).
"""

financial_tools = [
    symbol_search,
    company_overview,
    income_statement,
    balance_sheet,
    cash_flow,
    earnings,
    earnings_calendar,
    ipo_calendar,
    read_catalog
]

financial_agent_executor = create_react_agent(model, financial_tools, parallel_tool_calls=False)

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
