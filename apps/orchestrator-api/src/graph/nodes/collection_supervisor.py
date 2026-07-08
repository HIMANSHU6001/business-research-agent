from src.graph.state import ResearchState
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)

async def run_collection_supervisor(state: ResearchState) -> dict:
    return {"current_phase": "data_collection"}

async def run_collection_synthesizer(state: ResearchState) -> dict:
    """Synthesizes reports from the three parallel capability agents."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are the Data Collection Supervisor. Synthesize the provided capability reports into a unified 'Data Collection Report'."),
        ("human", "{reports}")
    ])
    
    # Filter state["messages"] for names matching financial_agent, macro_agent, and trends_agent
    reports = [
        m.content for m in state.get("messages", []) 
        if getattr(m, "name", None) in ["financial_agent", "macro_agent", "trends_agent"]
    ]
    
    chain = prompt | llm
    result = await chain.ainvoke({"reports": "\n\n".join(reports)})
    
    return {
        "messages": [AIMessage(content=result.content, name="collection_supervisor")],
        "current_phase": "analysis",
        "next_agent": "analysis_supervisor"
    }
