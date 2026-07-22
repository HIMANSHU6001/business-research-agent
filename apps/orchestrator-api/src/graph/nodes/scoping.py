import os
from datetime import datetime
from typing_extensions import Literal
from pydantic import BaseModel, Field

from llm_utils import get_chat_groq, DEFAULT_MODEL
from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import END
from langgraph.types import Command

from graph.state import ResearchState

# ===== CONFIGURATION =====

# Initialize model (You can swap this to qwen if you prefer, keeping Llama-3.1 as the established baseline)
model = get_chat_groq(model=DEFAULT_MODEL, temperature=0.1)

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
Our system relies on three parallel capability agents with strict limitations:
1. Financial Intelligence: Collects public company fundamental data (company overview, income statement, balance sheet, cash flow, earnings, IPO calendar). *NOTE: We do NOT collect daily stock prices or historical market capitalization time-series.*
2. Macro Economic Intelligence: Collects country-level macroeconomic and industry evidence (e.g., GDP, inflation, population, trade stats) via World Bank.
3. Consumer Trends: Collects Google Trends search interest over time and by region.

Transform the conversation history into a comprehensive, formal research brief. 
The brief MUST explicitly define:
- Target entities (companies, countries, or trend keywords).
- Required metrics (CRITICAL: ONLY include metrics that our system is actually capable of collecting based on the list above. Do not request unsupported data like daily stock prices).
- Strict temporal scope (dates or years).

Then, select the single most appropriate analytical framework (SWOT, PESTEL, PORTER, THEMATIC, CONCEPTUAL) that fits the requested analysis.

Current Date: {date}
Conversation History:
{messages}

{format_instructions}
Output only the raw JSON. Do not include markdown formatting blocks or conversational filler."""

# ===== WORKFLOW NODES =====

class ReviewBriefOutput(BaseModel):
    decision: Literal["approve", "revise"] = Field(
        description="Whether the user approved the research brief or requested changes."
    )
    feedback: str = Field(
        description="The user's feedback if revise is chosen, or empty if approved.",
        default=""
    )

review_parser = PydanticOutputParser(pydantic_object=ReviewBriefOutput)

REVIEW_PROMPT = """You are the Scoping Agent.
The user was just presented with a Research Brief. Evaluate their response to see if they approved it or if they want changes.

Conversation History:
{messages}

{format_instructions}
Output only the raw JSON.
"""

def clarify_with_user(state: ResearchState) -> Command[Literal["write_research_brief", "__end__"]]:
    """
    Determines if the user's request contains sufficient information.
    Routes to research brief generation or pauses execution to ask the human.
    """
    print(f"--- SCOPING: CLARIFICATION CHECK ({state.get('research_id', '')}) ---")
    
    # 1. Budget check to prevent infinite human-in-the-loop loops
    if len(state.get("messages", [])) > 6:
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

def write_research_brief(state: ResearchState) -> Command[Literal["__end__"]]:
    """
    Transforms the conversation history into the formal TRD specifications:
    a structured research brief and a selected analytical framework.
    """
    print(f"--- SCOPING: GENERATING BRIEF ({state.get('research_id', '')}) ---")
    
    structured_output_model = model.with_structured_output(ResearchScope, method="json_mode")

    response = structured_output_model.invoke([
        HumanMessage(content=BRIEF_PROMPT.format(
            messages=get_buffer_string(state.get("messages", [])),
            date=get_today_str(),
            format_instructions=brief_parser.get_format_instructions()
        ))
    ])

    review_message = f"Here is the generated Research Brief:\n\n{response.research_brief}\n\nSelected Framework: {response.selected_framework}\n\nDo you approve this brief, or would you like to make any changes before we begin data collection?"

    # Output to user and pause for review
    return Command(
        goto=END,
        update={
            "research_brief": response.research_brief,
            "selected_framework": response.selected_framework,
            "current_phase": "scoping_review",
            "messages": [AIMessage(content=review_message, name="scoping_agent")]
        }
    )

def review_research_brief(state: ResearchState) -> Command[Literal["write_research_brief", "data_collection_supervisor"]]:
    """Evaluates the user's feedback on the research brief."""
    print(f"--- SCOPING: REVIEW BRIEF ({state.get('research_id', '')}) ---")
    
    structured_output_model = model.with_structured_output(ReviewBriefOutput, method="json_mode")
    
    response = structured_output_model.invoke([
        HumanMessage(content=REVIEW_PROMPT.format(
            messages=get_buffer_string(state.get("messages", [])[-3:]), # Look at recent context
            format_instructions=review_parser.get_format_instructions()
        ))
    ])
    
    if response.decision == "approve":
        return Command(
            goto="data_collection_supervisor",
            update={
                "current_phase": "collection",
                "next_agent": "data_collection_supervisor",
                "messages": [AIMessage(content="Great, starting data collection now.", name="scoping_agent")]
            }
        )
    else:
        return Command(
            goto="write_research_brief",
            update={
                "current_phase": "scoping",
                "messages": [AIMessage(content=f"Understood. I will revise the brief based on your feedback: {response.feedback}", name="scoping_agent")]
            }
        )