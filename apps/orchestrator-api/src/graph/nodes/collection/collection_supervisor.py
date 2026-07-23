from typing import Literal
from pydantic import BaseModel, Field
from langgraph.types import Command
from langgraph.graph import END
from graph.state import ResearchState
from llm_utils import get_chat_model, SUPERVISOR_MODEL
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
import json


class SupervisorDecision(BaseModel):
    """Structured output for the supervisor's routing decision."""
    reflection: str = Field(
        description="Your detailed thought process: what evidence has been collected so far, what gaps remain, and why you are choosing this specific agent next (or finishing)."
    )
    next_agent: Literal["financial_agent", "macro_agent", "trends_agent", "ask_human", "FINISH"] = Field(
        description="The next capability agent to invoke, 'ask_human' to clarify ambiguities, or FINISH if enough evidence has been collected."
    )
    agent_task: str = Field(
        description="The specific, detailed atomic task instruction for the chosen capability agent. MUST NOT be 'None' unless next_agent is 'FINISH' or 'ask_human'."
    )
    question: str = Field(
        description="The specific question to ask the user if next_agent is 'ask_human'. Keep it empty otherwise.",
        default=""
    )


llm = get_chat_model(model=SUPERVISOR_MODEL, temperature=0.1)
supervisor_parser = PydanticOutputParser(pydantic_object=SupervisorDecision)



async def run_collection_supervisor(state: ResearchState):
    """Single-pass router: reads state, calls LLM once, returns routing decision."""
    print("--- DATA COLLECTION SUPERVISOR ---")
    research_brief = state.get("research_brief", "")
    
    # Collect previous supervisor assignments, capability agent reports, and human responses
    history_logs = []
    for m in state.get("messages", []):
        name = getattr(m, "name", None)
        m_type = getattr(m, "type", None)
        if name in ["collection_supervisor", "financial_agent", "macro_agent", "trends_agent"]:
            history_logs.append(f"[{name}]: {m.content}")
        elif m_type == "human" or name == "human":
            history_logs.append(f"[HUMAN]: {m.content}")
            
    print(f"DEBUG HISTORY LOGS: {history_logs}")
    
    system_prompt = f"""You are the Data Collection Supervisor.
Your goal is to collect comprehensive evidence for the research brief by routing to capability agents one at a time.

Available agents (they already have their own API access — do NOT ask the human about data sources):
1. financial_agent: Connects to Alpha Vantage. Collects public company fundamental data (company overview, income statement, balance sheet, cash flow, earnings, earnings calendar, IPO calendar). 
2. macro_agent: Connects to World Bank Data360. Collects country-level macroeconomic and industry evidence (GDP, inflation, population, trade stats, etc...).
3. trends_agent: Connects to Google Trends via SerpAPI. Collects consumer demand and search trend evidence over time and by region.

**LIMITATION**: If the agents reports a gap once, do not assign the same task to the agent, just mention the gap in your report

Research Brief:
{research_brief}

History of Supervisor Assignments & Agent Reports:
{json.dumps(history_logs, indent=2)}

Rules:
- DO NOT set `agent_task` to 'None' or empty if `next_agent` is not 'FINISH' or 'ask_human'. This is critical. If `next_agent` is one of the capability agents, `agent_task` MUST contain the specific instruction for that agent.
- Set `agent_task` to 'None' ONLY when `next_agent` is 'FINISH' or 'ask_human'.
- Do NOT expect agents to return the actual raw data values in their reports. If an agent report confirms that an Artifact ID was created for a specific metric, consider that data successfully collected and do NOT assign the same task again.
- Do NOT pass date constraints or date filters to the financial_agent in `agent_task`. The financial tools pull the full historical dataset automatically, and date filtering is handled later during analysis.
- ONLY assign tasks that are EXPLICITLY required to fulfill the Research Brief. Do NOT assign agents to collect data (e.g., macro GDP/inflation) just because the agent is available, unless the brief specifically asks for it.
- Evaluate the collected reports to determine what single metric/data point is missing next.
- When ALL relevant evidence for ALL required metrics has been gathered, set next_agent to FINISH.
- **CRITICAL LOOP PREVENTION**: Look closely at the "History of Supervisor Assignments & Agent Reports". If you (the collection_supervisor) have already assigned a set of metrics to an agent, you MUST NOT assign those exact same metrics to that agent again.
- **ASKING HUMAN FOR MISSING DATA**: If an agent's report explicitly states that data is unavailable, missing, or failed to be collected, you MUST set `next_agent` to 'ask_human' and ask the user how they want to proceed (e.g., "The financial agent reported that income statement data is unavailable for Reliance. Should I skip this metric or look for an alternative?"). 
- **HANDLING HUMAN FEEDBACK**: If you have already asked the human a question and they replied (e.g. "Skip it", "Yes", "Proceed without it"), you MUST respect their instruction. If they told you to skip the missing metric, accept that the data will remain missing, DO NOT ask them again, and proceed to collect the remaining metrics. If all other metrics are already collected, set `next_agent` to `FINISH`.
- Your reflection MUST contain concrete reasoning, noting exactly which metrics you have already asked for, what the agents returned, which metrics are still missing, and why you are choosing the next step.
- **BATCHING LIMIT**: NEVER assign more than 3 data points/metrics to fetch in a single turn. If the Research Brief requires many datasets, you MUST assign the most important 1 to 3 items now, wait for the agent to report back, and then assign the rest in subsequent turns.

{supervisor_parser.get_format_instructions()}
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="What is your routing decision?")
    ]
    
    try:
        response = await llm.ainvoke(messages)
        decision_obj = supervisor_parser.parse(response.content)
    except Exception as e:
        print(f"Failed to parse structured output, falling back. Error: {e}")
        decision_obj = SupervisorDecision(
            reflection="Failed to parse structured output.",
            next_agent="FINISH",
            agent_task="None"
        )
        
    class DecisionWrapper:
        def __init__(self, obj):
            for k, v in obj.model_dump().items():
                setattr(self, k, v)
    
    decision = DecisionWrapper(decision_obj)
    
    # Cap agent calls to a maximum of 2
    agent_counts = {}
    for m in state.get("messages", []):
        name = getattr(m, "name", None)
        if name in ["financial_agent", "macro_agent", "trends_agent"]:
            agent_counts[name] = agent_counts.get(name, 0) + 1
            
    if decision.next_agent in agent_counts and agent_counts[decision.next_agent] >= 2:
        print(f"  [CAP ENFORCED] {decision.next_agent} called {agent_counts[decision.next_agent]} times already. Forcing FINISH.")
        decision.next_agent = "FINISH"
        
    print(f"  Supervisor decision: {decision.next_agent} | Task: {decision.agent_task}")
    
    if decision.next_agent == "FINISH":
        return {
            "messages": [AIMessage(content=f"[Supervisor reflection] {decision.reflection}", name="collection_supervisor")],
            "current_phase": "analysis",
            "next_agent": "analysis_supervisor"
        }
    elif decision.next_agent == "ask_human":
        # Pause execution to ask the human a question via state routing
        return {
            "messages": [
                AIMessage(content=f"[Supervisor reflection] {decision.reflection}", name="collection_supervisor"),
                AIMessage(content=decision.question, name="collection_supervisor")
            ],
            "next_agent": "ask_human",
            "agent_task": "None"
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
        ("system", "You are the Data Collection Supervisor. Synthesize the provided capability reports into a unified 'Data Collection Report'.\n\nCRITICAL RULES:\n1. Your synthesized report MUST explicitly list any gaps, failures, or missing data that the agents reported. Do not gloss over or omit the failures, as the user needs to know exactly what could not be found.\n2. DO NOT include any Recommendations, Next Steps, or Verification sections. Stop writing immediately after summarizing the collected data and gaps."),
        ("human", "{reports}")
    ])
    
    # Filter state["messages"] for reports
    def _extract_text(content):
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return "\n".join(
                c.get("text", "") if isinstance(c, dict) else str(c)
                for c in content
            )
        return str(content)
        
    reports = [
        _extract_text(m.content) for m in state.get("messages", []) 
        if getattr(m, "name", None) in ["financial_agent", "macro_agent", "trends_agent"]
    ]
    
    chain = prompt | llm
    result = await chain.ainvoke({"reports": "\n\n".join(reports)})
    
    try:
        from context.knowledge import KnowledgeManager
        km = KnowledgeManager()
        await km.store_context(
            research_id=state.get("research_id", ""),
            agent_namespace="collection_supervisor",
            task_context="Synthesized Data Collection Report",
            content=result.content
        )
    except Exception as e:
        print(f"Failed to store context in pgVector for collection_supervisor: {e}")
    
    return {
        "messages": [AIMessage(content=result.content, name="collection_supervisor")],
        "current_phase": "analysis",
        "next_agent": "analysis_supervisor"
    }

