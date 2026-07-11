from typing import Literal
from pydantic import BaseModel, Field
from graph.state import ResearchState
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
import json


class SupervisorDecision(BaseModel):
    """Structured output for the supervisor's routing decision."""
    reflection: str = Field(
        description="Your detailed thought process: what evidence has been collected so far, what gaps remain, and why you are choosing this specific agent next (or finishing)."
    )
    next_agent: Literal["financial_agent", "macro_agent", "trends_agent", "FINISH"] = Field(
        description="The next capability agent to invoke, or FINISH if enough evidence has been collected."
    )
    agent_task: str = Field(
        description="The specific, detailed atomic task instruction for the chosen capability agent. MUST NOT be 'None' unless next_agent is 'FINISH'."
    )


llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)
structured_llm = llm.with_structured_output(SupervisorDecision, method='json_mode')
supervisor_parser = PydanticOutputParser(pydantic_object=SupervisorDecision)



async def run_collection_supervisor(state: ResearchState) -> dict:
    """Single-pass router: reads state, calls LLM once, returns routing decision."""
    print("--- DATA COLLECTION SUPERVISOR ---")
    research_brief = state.get("research_brief", "")
    
    # Collect reports already returned by capability agents
    reports = [
        m.content for m in state.get("messages", []) 
        if getattr(m, "name", None) in ["financial_agent", "macro_agent", "trends_agent"]
    ]
    
    system_prompt = f"""You are the Data Collection Supervisor.
Your goal is to collect comprehensive evidence for the research brief by routing to capability agents one at a time.

Available agents (they already have their own API access — do NOT ask the human about data sources):
1. financial_agent: Connects to Alpha Vantage. Collects public company fundamental data (income statement, balance sheet, cash flow, earnings), stock indicators, and news sentiment.
2. macro_agent: Connects to World Bank Data360. Collects country-level macroeconomic and industry evidence (GDP, inflation, population, trade stats).
3. trends_agent: Connects to Google Trends via SerpAPI. Collects consumer demand and search trend evidence over time and by region.

Research Brief:
{research_brief}

Reports collected so far:
{json.dumps(reports, indent=2)}

Rules:
- MICRO-TASKING IS MANDATORY: You must assign only ONE single atomic metric/task per agent invocation in the `agent_task` field. Do NOT assign collective or multi-part tasks.
  - Example BAD task: "Collect GDP growth and inflation rate for the last 3 years."
  - Example GOOD task: "Collect ONLY GDP growth for the last 3 years."
- If the research brief requires multiple metrics (e.g. GDP and inflation), you must assign one metric, wait for the agent to return the report, and then in the NEXT iteration, route back to the SAME agent to collect the next metric.
- DO NOT set `agent_task` to 'None' or empty if `next_agent` is not 'FINISH'. This is critical. If `next_agent` is one of the capability agents, `agent_task` MUST contain the specific instruction for that agent.
- Set `agent_task` to 'None' ONLY when `next_agent` is 'FINISH'.
- Evaluate the collected reports to determine what single metric/data point is missing next.
- When ALL relevant evidence for ALL required metrics has been gathered, set next_agent to FINISH.
- Your reflection MUST contain concrete reasoning, not vague statements.

{supervisor_parser.get_format_instructions()}
Output ONLY valid JSON."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Evaluate the current state and make your routing decision.")
    ]
    
    # Single LLM call — no loops, no ReAct
    decision = await structured_llm.ainvoke(messages)
    print(f"  Supervisor decision: {decision.next_agent} | Task: {decision.agent_task}")
    
    if decision.next_agent == "FINISH":
        return {
            "messages": [AIMessage(content=f"[Supervisor reflection] {decision.reflection}", name="collection_supervisor")],
            "current_phase": "analysis",
            "next_agent": "analysis_supervisor"
        }
    else:
        return {
            "messages": [AIMessage(content=f"[Supervisor reflection] {decision.reflection}", name="collection_supervisor")],
            "next_agent": decision.next_agent,
            "agent_task": decision.agent_task
        }

async def run_collection_synthesizer(state: ResearchState) -> dict:
    """Synthesizes reports from the capability agents."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are the Data Collection Supervisor. Synthesize the provided capability reports into a unified 'Data Collection Report'."),
        ("human", "{reports}")
    ])
    
    # Filter state["messages"] for reports
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

