import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

# Ensure 'src' is in the Python path so local modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Load environment variables
load_dotenv()
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "Business Research Agent - Full Graph Test"

from graph.graph_builder import graph
from langchain_core.messages import HumanMessage

async def main():
    print("Starting full graph execution from CLI...")
    
    TEST_UUID = str(uuid.uuid4())
    
    # Provide the initial state for the graph
    inputs = {
        "messages": [
            HumanMessage(content="Research the financial performance of Microsoft (MSFT) and its macroeconomic environment in the United States over the last 5 years (2019-2024).")
        ],
        "research_id": TEST_UUID
    }
    
    config = {
        "recursion_limit": 150, 
        "configurable": {"research_id": TEST_UUID}
    }
    
    try:
        async for event in graph.astream(inputs, config=config):
            for node_name, node_state in event.items():
                print(f"\n{'='*50}")
                print(f"--- Output from node: {node_name} ---")
                
                # Try to print the most recent message if available
                if isinstance(node_state, dict) and "messages" in node_state and node_state["messages"]:
                    last_msg = node_state["messages"][-1]
                    msg_type = getattr(last_msg, 'type', 'message')
                    print(f"[{msg_type.upper()}]: {getattr(last_msg, 'content', '')[:1000]}...") # truncate very long messages
                    
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        print(f"Tool Calls: {last_msg.tool_calls}")
                else:
                    # Print the keys that were updated in the state
                    print(f"State updated: {list(node_state.keys()) if isinstance(node_state, dict) else 'State update'}")
                print(f"{'='*50}\n")
                
    except Exception as e:
        print(f"\n[ERROR] Graph execution crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
