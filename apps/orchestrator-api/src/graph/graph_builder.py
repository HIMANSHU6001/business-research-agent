from langgraph.graph import StateGraph, START, END
from graph.state import ResearchState
from graph.nodes.scoping import clarify_with_user, write_research_brief
from graph.nodes.collection.financial_agent import run_financial_agent
from graph.nodes.collection.macro_agent import run_macro_agent
from graph.nodes.collection.trends_agent import run_trends_agent
from graph.nodes.collection.collection_supervisor import run_collection_supervisor, run_collection_synthesizer
from graph.nodes.analysis.analysis_supervisor import run_analysis_supervisor, run_analysis_synthesizer
from graph.nodes.analysis.quantitative_agent import run_quantitative_agent
from graph.nodes.analysis.qualitative_agent import run_qualitative_agent

def route_collection(state: ResearchState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "analysis_supervisor" or not next_agent:
        return "collection_synthesizer"
    return next_agent

def route_analysis(state: ResearchState) -> str:
    return state.get("next_agent", "analysis_synthesizer")

def build_research_graph():
    # Initialize the graph with our state schema
    builder = StateGraph(ResearchState)

    # Add scoping nodes
    builder.add_node("clarify_with_user", clarify_with_user)
    builder.add_node("write_research_brief", write_research_brief)
    
    # Add collection nodes
    builder.add_node("data_collection_supervisor", run_collection_supervisor)
    builder.add_node("financial_agent", run_financial_agent)
    builder.add_node("macro_agent", run_macro_agent)
    builder.add_node("trends_agent", run_trends_agent)
    builder.add_node("collection_synthesizer", run_collection_synthesizer)

    # Add analysis nodes
    builder.add_node("data_analysis_supervisor", run_analysis_supervisor)
    builder.add_node("quantitative_agent", run_quantitative_agent)
    builder.add_node("qualitative_agent", run_qualitative_agent)
    builder.add_node("analysis_synthesizer", run_analysis_synthesizer)

    # Wiring the flow
    builder.add_edge(START, "clarify_with_user")
    
    # After research brief is written, start data collection routing
    builder.add_edge("write_research_brief", "data_collection_supervisor")
    
    # Dynamic routing from supervisor
    builder.add_conditional_edges(
        "data_collection_supervisor",
        route_collection,
        {
            "financial_agent": "financial_agent",
            "macro_agent": "macro_agent",
            "trends_agent": "trends_agent",
            "collection_synthesizer": "collection_synthesizer"
        }
    )
    
    # Capability agents route back to the supervisor
    builder.add_edge("financial_agent", "data_collection_supervisor")
    builder.add_edge("macro_agent", "data_collection_supervisor")
    builder.add_edge("trends_agent", "data_collection_supervisor")
    
    # Synthesizer routes to Data Analysis Supervisor
    builder.add_edge("collection_synthesizer", "data_analysis_supervisor")
    
    # Dynamic routing for analysis supervisor
    builder.add_conditional_edges(
        "data_analysis_supervisor",
        route_analysis,
        {
            "quantitative_agent": "quantitative_agent",
            "qualitative_agent": "qualitative_agent",
            "analysis_synthesizer": "analysis_synthesizer"
        }
    )
    
    # Capability agents route back to analysis supervisor
    builder.add_edge("quantitative_agent", "data_analysis_supervisor")
    builder.add_edge("qualitative_agent", "data_analysis_supervisor")
    
    # Final analysis synthesizer ends the graph
    builder.add_edge("analysis_synthesizer", END)
    
    return builder

# Compile the graph for LangGraph Studio
graph = build_research_graph().compile()
