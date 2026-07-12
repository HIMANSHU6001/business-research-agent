from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_groq import ChatGroq
from graph.state import ResearchState
from graph.tools.trends_tools import (
    interest_by_region,
    interest_over_time,
)
from graph.tools.common_tools import think
from graph.nodes.collection.collection_utils import create_thinking_react_agent

model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1)

TRENDS_SYSTEM_PROMPT = """You are the Trends Intelligence Agent for the Business Research Agent system.

Your sole purpose is to collect consumer demand and search trend evidence using Google Trends tools via SerpApi.
You collect facts — you do NOT analyze, interpret, or draw conclusions.

## MANDATORY THINKING STEP (CRITICAL):
- You MUST invoke the `think` tool as your VERY FIRST step to outline your strategy before calling any other tool.
- You MUST invoke the `think` tool after receiving results from any tool, to reflect on your progress and assess research gaps.
- Reflection Overwrite Rule: When calling `think`, write a fresh, concise reflection containing ONLY your current thoughts, findings, and immediate next steps.

## Workflow (follow this order strictly):
1. Identify the key brands, products, or topics from the provided Task instruction.
2. Use `interest_over_time` and `interest_by_region` to collect trend data for those topics.
   - Note that these tools will return a confirmation string and automatically ingest the data.

## Critical rules:
- Pass the research_id to all tool calls that require it.
- Do NOT hallucinate data values. Only reference what tools return to you.
- Always call Think tool after a tool call is done and reflect on your next steps.
- Remember you have limited turns only so stop when you have enough data to answer confidently.

## Output:
Write a concise Trends Report that:
- Lists all trend data and artifacts successfully collected (including artifact IDs).
- Notes any gaps or errors.
"""

trends_tools = [
    interest_by_region,
    interest_over_time,
    think,
]

trends_agent_executor = create_thinking_react_agent(model, trends_tools)

async def run_trends_agent(state: ResearchState) -> dict:
    """Collects consumer demand and search trend evidence via Google Trends MCP."""
    print(f"--- TRENDS INTELLIGENCE: {state['research_id']} ---")
    research_id = state.get("research_id") or ""
    agent_task = state.get("agent_task") or "Collect all relevant trends indicators."
    
    inputs = {
        "messages": [
            SystemMessage(content=TRENDS_SYSTEM_PROMPT),
            HumanMessage(content=f"Research ID: {research_id}\n\nTask:\n{agent_task}")
        ]
    }
    
    config = {"recursion_limit": 25}
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
