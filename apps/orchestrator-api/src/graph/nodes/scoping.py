import os
from datetime import datetime
from typing_extensions import Literal
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langgraph.graph import END
from langgraph.types import Command

# pyrefly: ignore [missing-import]
from src.graph.state import ResearchState

# ===== CONFIGURATION =====

# Initialize model (You can swap this to qwen if you prefer, keeping Llama-3.1 as the established baseline)
model = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0
)

def get_today_str() -> str:
    now = datetime.now()
    return f"{now.strftime('%a %b')} {now.day}, {now.year}"

# ===== STRUCTURED OUTPUT SCHEMAS =====

class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(
        description="True if the user's request lacks specific entities, industries, or clear business goals required to conduct research."
    )
    question: str = Field(
        description="The specific, direct question to ask the user if clarification is needed.", 
        default=""
    )
    verification: str = Field(
        description="A short, 1-sentence acknowledgment of the research goal if no clarification is needed.", 
        default=""
    )

class ResearchScope(BaseModel):
    research_brief: str = Field(
        description="A detailed, 3-4 paragraph expansion of the user's query identifying key entities, required metrics, and temporal scope."
    )
    selected_framework: Literal["SWOT", "PESTEL", "PORTER", "THEMATIC", "CONCEPTUAL"] = Field(
        description="The single most appropriate analytical framework for this research."
    )

# ===== PROMPTS =====

CLARIFY_PROMPT = """You are the Scoping Agent for an elite business intelligence system.
Review the conversation history. Does the latest request contain enough specific information (entities, targets, or metrics) to conduct meaningful business research?

If NO, you must ask a precise question for clarification.
If YES, provide a brief verification.

Current Date: {date}
Conversation History:
{messages}"""

BRIEF_PROMPT = """You are the Scoping Agent for an elite business intelligence system.
Transform the conversation history into a comprehensive, formal research brief and select the optimal analytical framework to execute it.

Current Date: {date}
Conversation History:
{messages}"""

# ===== WORKFLOW NODES =====

def clarify_with_user(state: ResearchState) -> Command[Literal["write_research_brief", "__end__"]]:
    """
    Determines if the user's request contains sufficient information.
    Routes to research brief generation or pauses execution to ask the human.
    """
    print(f"--- SCOPING: CLARIFICATION CHECK ({state['research_id']}) ---")
    
    # 1. Budget check to prevent infinite human-in-the-loop loops
    if len(state["messages"]) > 6:
        print("Turn budget exceeded for scoping. Forcing brief generation.")
        return Command(goto="write_research_brief")

    structured_output_model = model.with_structured_output(ClarifyWithUser)

    response = structured_output_model.invoke([
        HumanMessage(content=CLARIFY_PROMPT.format(
            messages=get_buffer_string(state.get("messages", [])), 
            date=get_today_str()
        ))
    ])

    if response.need_clarification:
        # Route to END (pauses the graph to return the question to the frontend via FastAPI)
        return Command(
            goto=END, 
            update={"messages": [AIMessage(content=response.question, name="scoping_agent")]}
        )
    else:
        # Route to the next node in the scoping phase
        return Command(
            goto="write_research_brief", 
            update={"messages": [AIMessage(content=response.verification, name="scoping_agent")]}
        )

def write_research_brief(state: ResearchState) -> dict:
    """
    Transforms the conversation history into the formal TRD specifications:
    a structured research brief and a selected analytical framework.
    """
    print(f"--- SCOPING: GENERATING BRIEF ({state['research_id']}) ---")
    
    structured_output_model = model.with_structured_output(ResearchScope)

    response = structured_output_model.invoke([
        HumanMessage(content=BRIEF_PROMPT.format(
            messages=get_buffer_string(state.get("messages", [])),
            date=get_today_str()
        ))
    ])

    # Update global state and advance the phase
    return {
        "research_brief": response.research_brief,
        "selected_framework": response.selected_framework,
        "current_phase": "collection",
        "next_agent": "data_collection_supervisor"
    }