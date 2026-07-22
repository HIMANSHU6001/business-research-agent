from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_utils import get_chat_groq, DEFAULT_MODEL
from graph.state import ResearchState
from graph.tools.trends_tools import (
    interest_by_region,
    interest_over_time,
)
from graph.tools.analytics_tools import read_catalog
from graph.nodes.collection.collection_utils import create_react_agent

model = get_chat_groq(model=DEFAULT_MODEL, temperature=0.1)

TRENDS_SYSTEM_PROMPT = """You are the Trends Intelligence Agent. Collect Google Trends data via SerpApi. Do NOT analyze.

CRITICAL RULES & WORKFLOW:
1. BEFORE fetching data, ALWAYS use `read_catalog` to check if the data already exists in the database. DO NOT fetch the same data twice.
3. Identify key topics from the task.
3. Use `interest_over_time` and `interest_by_region` to collect trend data. They return confirmation strings.
4. NEVER hallucinate data or tool arguments.
5. Do NOT re-call tools to verify artifact IDs. Stop when you have enough data.
6. STRICT DATE FORMATTING: If passing a date range to tools, you MUST use either the predefined keywords (e.g. "today 12-m", "all") or exact "YYYY-MM-DD YYYY-MM-DD" format. Do NOT use textual dates like "July 2024 to July 2026".
7. MISSING DATA HANDLING: If a tool returns an empty result, or an error message indicating no data is available for the requested trend/keyword, this means the required data is NOT available. You MUST explicitly state in your report exactly which keyword/region was missing (e.g. "The requested search trends data for 'Reliance' in India is not available") and do not attempt to fetch it again.

OUTPUT:
Write a concise report listing collected trend data, Artifact IDs, and any gaps or errors. If data was missing or unavailable, explicitly state exactly which data is not available.
"""

trends_tools = [
    interest_by_region,
    interest_over_time,
    read_catalog
]

trends_agent_executor = create_react_agent(model, trends_tools)

async def run_trends_agent(state: ResearchState) -> dict:
    """Collects consumer demand and search trend evidence via Google Trends MCP."""
    print(f"--- TRENDS INTELLIGENCE: {state['research_id']} ---")
    research_id = state.get("research_id") or ""
    agent_task = state.get("agent_task") or "Collect all relevant trends indicators."
    
    inputs = {
        "messages": [
            SystemMessage(content=TRENDS_SYSTEM_PROMPT),
            HumanMessage(content=f"Task:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 25, "configurable": {"research_id": research_id}}
    response = await trends_agent_executor.ainvoke(inputs, config=config)
    final_response = response["messages"][-1]
    
    try:
        from context.knowledge import KnowledgeManager
        km = KnowledgeManager()
        await km.store_context(
            research_id=research_id,
            agent_namespace="trends_agent",
            task_context=agent_task,
            content=final_response.content
        )
    except Exception as e:
        print(f"Failed to store context in pgVector for trends_agent: {e}")
    
    return {
        "messages": [AIMessage(content=final_response.content, name="trends_agent")]
    }
