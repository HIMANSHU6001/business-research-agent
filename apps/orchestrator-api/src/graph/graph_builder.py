from langgraph.graph import StateGraph, START, END
from graph.state import ResearchState
from graph.nodes.scoping import clarify_with_user, write_research_brief
from graph.nodes.financial_agent import run_financial_agent
from graph.nodes.macro_agent import run_macro_agent
from graph.nodes.trends_agent import run_trends_agent
from graph.nodes.collection_supervisor import run_collection_synthesizer

def build_research_graph():
    # Initialize the graph with our state schema
    builder = StateGraph(ResearchState)

    # Add scoping nodes
    builder.add_node("clarify_with_user", clarify_with_user)
    builder.add_node("write_research_brief", write_research_brief)
    
    # Add collection nodes
    builder.add_node("financial_agent", run_financial_agent)
    builder.add_node("macro_agent", run_macro_agent)
    builder.add_node("trends_agent", run_trends_agent)
    builder.add_node("collection_synthesizer", run_collection_synthesizer)

    # Wiring the flow
    builder.add_edge(START, "clarify_with_user")
    
    # Fan-out from write_research_brief to parallel collection agents
    builder.add_edge("write_research_brief", "financial_agent")
    builder.add_edge("write_research_brief", "macro_agent")
    builder.add_edge("write_research_brief", "trends_agent")
    
    # Fan-in from parallel collection agents to collection synthesizer
    builder.add_edge("financial_agent", "collection_synthesizer")
    builder.add_edge("macro_agent", "collection_synthesizer")
    builder.add_edge("trends_agent", "collection_synthesizer")
    
    # Synthesizer routes to END
    builder.add_edge("collection_synthesizer", END)
    
    return builder

# Compile the graph for LangGraph Studio
graph = build_research_graph().compile()
