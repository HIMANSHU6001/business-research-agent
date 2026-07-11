import os
from datetime import datetime
from typing_extensions import Literal
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import END
from langgraph.types import Command

from graph.state import ResearchState

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

clarify_parser = PydanticOutputParser(pydantic_object=ClarifyWithUser)
brief_parser = PydanticOutputParser(pydantic_object=ResearchScope)

# ===== PROMPTS =====

CLARIFY_PROMPT = """You are the Scoping Agent for a Business Research multi-agent system.
Your job is to evaluate the user's request. Do not be overly pedantic. If a requested metric falls broadly under company finance, macroeconomics, or consumer trends, assume our pipelines can handle it.

Our capabilities:
1. Financial Intelligence: Public company fundamentals, market data, and corporate news.
2. Macro Economic Intelligence: Country-level economic, demographic, and labor indicators (e.g., GDP, inflation, unemployment, trade, population).
3. Trends Intelligence: Consumer search interest and keyword trends.

Review the Conversation History.
1. Scope Check: Is this request fundamentally related to our capabilities? (e.g., asking for a Python script or a recipe is out of scope).
2. Parameter Check: Does the request contain a target entity (company/country/keyword) and a temporal scope (timeframe/years)?

Decision Logic:
- If the request is IN SCOPE but missing a target or timeframe, ask a concise, direct question to get the missing parameter.
- If the request is entirely OUT OF SCOPE, state our specific capabilities and ask how you can help within those bounds.
- If the request is IN SCOPE and ACTIONABLE, verify the goal in one sentence.

Current Date: {date}
Conversation History:
{messages}

{format_instructions}
Output only the raw JSON. Do not include markdown formatting blocks or conversational filler.
"""

BRIEF_PROMPT = """You are the Scoping Agent for a Business Research multi-agent system.
Our system relies on three parallel capability agents: Financial (public company data), Macro Economic (country-level data), and Consumer Trends (search interest).

Transform the conversation history into a comprehensive, formal research brief. 
The brief MUST explicitly define:
- Target entities (companies, countries, or trend keywords).
- Required metrics.
- Strict temporal scope (dates or years).

Then, select the single most appropriate analytical framework (SWOT, PESTEL, PORTER, THEMATIC, CONCEPTUAL) that fits the requested analysis.

Current Date: {date}
Conversation History:
{messages}

{format_instructions}
Output only the raw JSON. Do not include markdown formatting blocks or conversational filler."""

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

    structured_output_model = model.with_structured_output(ClarifyWithUser, method="json_mode")

    response = structured_output_model.invoke([
        HumanMessage(content=CLARIFY_PROMPT.format(
            messages=get_buffer_string(state.get("messages", [])), 
            date=get_today_str(),
            format_instructions=clarify_parser.get_format_instructions()
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
    
    structured_output_model = model.with_structured_output(ResearchScope, method="json_mode")

    response = structured_output_model.invoke([
        HumanMessage(content=BRIEF_PROMPT.format(
            messages=get_buffer_string(state.get("messages", [])),
            date=get_today_str(),
            format_instructions=brief_parser.get_format_instructions()
        ))
    ])

    # Update global state and advance the phase
    return {
        "research_brief": response.research_brief,
        "selected_framework": response.selected_framework,
        "current_phase": "collection",
        "next_agent": "data_collection_supervisor"
    }