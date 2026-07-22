import asyncio
import os
from dotenv import load_dotenv

# Load environment variables (including LangSmith tracing keys)
load_dotenv()

# Ensure LangSmith tracing is enabled
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "Business Research Agent - Single Agent Test"

from graph.nodes.collection.macro_agent import macro_agent_executor
from langchain_core.messages import SystemMessage, HumanMessage

async def main():
    print("Starting single agent execution with LangSmith tracing enabled...")
    
    # Example input for the Macro Agent
    inputs = {
        "messages": [
            HumanMessage(content="Task:\nCollect GDP and inflation data for India over the last 5 years.")
        ]
    }
    
    config = {
        "recursion_limit": 30, 
        "configurable": {"research_id": "single-agent-test-001"}
    }
    
    # Stream the agent's execution
    async for event in macro_agent_executor.astream(inputs, config=config):
        for node_name, node_state in event.items():
            print(f"\n--- Update from {node_name} ---")
            if "messages" in node_state and node_state["messages"]:
                last_msg = node_state["messages"][-1]
                print(f"[{last_msg.type}]: {last_msg.content}")
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    print(f"Tool Calls: {last_msg.tool_calls}")

if __name__ == "__main__":
    asyncio.run(main())
