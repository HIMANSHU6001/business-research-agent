from typing import Annotated, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class ResearchState(TypedDict):
    # Core Identifiers
    research_id: str
    
    # Conversation & Working Memory
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Scoping Outputs (Set once at the beginning)
    research_brief: Optional[str]
    selected_framework: Optional[str] # e.g., "SWOT", "PESTEL", "PORTER", "THEMATIC", "CONCEPTUAL"
    
    # Collection Tracker
    collected_artifacts: List[str]
    
    # Analysis Tracker
    analysis_reports: List[str]
    
    # Supervisor Routing State
    current_phase: str # "scoping", "collection", "analysis", "synthesis", "complete"
    next_agent: Optional[str] 
    agent_task: Optional[str]
