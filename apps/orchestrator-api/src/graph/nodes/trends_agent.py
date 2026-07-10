from langchain_core.messages import AIMessage
from graph.state import ResearchState

async def run_trends_agent(state: ResearchState) -> dict:
    """Collects consumer demand and search trend evidence via Google Trends MCP."""
    print(f"--- TRENDS INTELLIGENCE (STUB): {state['research_id']} ---")
    return {
        "messages": [AIMessage(content="Trends Agent is currently disabled.", name="trends_agent")]
    }
