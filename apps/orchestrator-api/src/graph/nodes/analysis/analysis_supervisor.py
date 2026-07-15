import json
from typing import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage
from llm_utils import get_chat_groq
from graph.state import ResearchState
import os

from pydantic import BaseModel, Field

class AnalysisSupervisorOutput(BaseModel):
    reasoning: str = Field(..., description="Reasoning for the next step, based on the research brief and completed reports.")
    next_agent: str = Field(..., description="The next agent to route to: 'quantitative_agent', 'qualitative_agent', or 'analysis_synthesizer'.")
    agent_task: str = Field(..., description="Specific instructions for the next agent. If routing to quantitative_agent, MUST include exactly ONE metric and EXACT statistical tool. If routing to qualitative_agent, describe the thematic interpretation task.")

from graph.tools.qualitative_tools import search_context
from graph.tools.analytics_tools import read_catalog
from graph.tools.common_tools import think
from graph.nodes.collection.collection_utils import create_thinking_react_agent
from context.workspace import get_citations_for_research

async def run_analysis_supervisor(state: ResearchState) -> dict:
    print("--- DATA ANALYSIS SUPERVISOR ---")
    
    reports = state.get("analysis_reports", [])
    if reports is None:
        reports = []
    
    agent_model = get_chat_groq(
        model="qwen/qwen3-32b",
        temperature=0.1
    )
    
    tools = [search_context, read_catalog, think]
    supervisor_agent = create_thinking_react_agent(agent_model, tools)
    
    completed_reports_info = f"Completed Analysis Reports: {len(reports)}\n\n"
    for i, report in enumerate(reports):
        completed_reports_info += f"Report {i+1}:\n{report[:3000]}...\n\n"

    system_prompt = """You are the Data Analysis Supervisor.
Your job is to route the analysis process.

Available Agents:
- quantitative_agent: Performs statistical computation on datasets. Route here to start or continue quantitative analysis.
  *CAPABILITIES: Can only run `get_descriptive_stats`, `calculate_correlation`, `execute_t_test`, and `calculate_trendline`.*
  *LIMITATIONS: Cannot perform complex math or arbitrary Pandas operations. Cannot analyze historical market capitalization time-series or daily stock prices (as that data is not collected) or collect any data.*
- qualitative_agent: Interprets evidence using the selected framework. Route here when quantitative analysis is complete.
- analysis_synthesizer: Synthesizes the final report. Route here when both are done.

# CRITICAL RULES:
1. ONE TASK AT A TIME: In `agent_task`, specify exactly ONE abstract metric you want analyzed (e.g. "revenue" or "net income") and the EXACT statistical tool to use (e.g. `get_descriptive_stats`). 
   *DO NOT GUESS EXACT COLUMN NAMES.* Instruct the `quantitative_agent` to find the dataset via `read_catalog`, check the schema via `get_schema`, and then apply the statistical tool to the appropriately matching column.
2. DO NOT BUNDLE: Never ask the agent to analyze multiple variables or do multiple tests in one task.
3. NO TOOL CALLS: DO NOT attempt to output tool calls for agents (e.g. `quantitative_agent`). Just state your routing decision in plain text.

5. DO NOT ASSIGN STATISTICAL TOOLS TO QUALITATIVE AGENT: Only the quantitative_agent can run correlation, t-tests, etc.

In your final response, you MUST provide a brief summary of reasoning, the next agent, and the EXACT task instruction. If routing to quantitative_agent, be highly specific (metric + tool).
"""

    user_prompt = f"""
Research Brief: {state.get('research_brief', 'N/A')}
Selected Framework: {state.get('selected_framework', 'N/A')}

{completed_reports_info}

Based on the completed reports, who should run next?
If no reports exist, route to quantitative_agent.
If quantitative analysis is completed but needs more depth, you can route to quantitative_agent again.
If quantitative analysis is sufficient but qualitative is missing, route to qualitative_agent.
If BOTH quantitative and qualitative analyses have been adequately addressed (e.g. you see at least one quantitative report and one qualitative thematic report), you MUST route to analysis_synthesizer to finish the research. Do not loop back.
"""

    inputs = {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
    }
    
    config = {"recursion_limit": 15, "configurable": {"research_id": state.get("research_id", "")}}
    
    response = await supervisor_agent.ainvoke(inputs, config=config)
    agent_final_text = response["messages"][-1].content

    struct_model = get_chat_groq(
        model="qwen/qwen3-32b",
        temperature=0.0
    ).with_structured_output(AnalysisSupervisorOutput)
    
    extraction_prompt = f"""Extract the routing decision from the supervisor's output.
CRITICAL RULES for agent_task:
- If next_agent is 'quantitative_agent': The task MUST specify exactly ONE abstract metric (e.g. 'revenue') and the EXACT statistical tool to use (e.g. `get_descriptive_stats`). Do not use vague summaries like 'apply statistical tools'. Be highly specific.
- If next_agent is 'qualitative_agent': The task MUST outline what thematic or framework-based interpretation to do. DO NOT assign statistical correlation or math tasks to the qualitative agent.
- If next_agent is 'analysis_synthesizer': The task should just be to synthesize the reports.

Supervisor Output:
{agent_final_text}
"""
    
    decision_obj = struct_model.invoke(extraction_prompt)
    
    if hasattr(decision_obj, "model_dump"):
        decision = decision_obj.model_dump()
    elif hasattr(decision_obj, "dict"):
        decision = decision_obj.dict()
    else:
        decision = decision_obj
        
    print(f"Supervisor Decision: {decision['next_agent']}")
    print(f"Task: {decision['agent_task']}")
    
    return {
        "current_phase": "analysis",
        "next_agent": decision["next_agent"],
        "agent_task": decision["agent_task"]
    }

async def run_analysis_synthesizer(state: ResearchState) -> dict:
    print("--- ANALYSIS SYNTHESIZER ---")
    
    reports = state.get("analysis_reports", [])
    if reports is None:
        reports = []
        
    research_id = state.get("research_id", "")
    citations_list = await get_citations_for_research(research_id)
    
    llm = get_chat_groq(
        model="qwen/qwen3-32b",
        temperature=0.2
    )
    
    system_prompt = """You are the Lead Data Analyst. 
Synthesize the provided quantitative and qualitative reports into a Final Analysis Report.
Format:
- Executive summary (3-5 sentences)
- Qualitative findings
- Quantitative findings
- Synthesis (how they support/complicate each other)
- Citations (You MUST list the provided database citations at the end, exactly as formatted in the "Automated Citations" section, and use the In-Text portions when citing data).
"""

    reports_text = "\n\n".join(reports)
    
    citations_text = "No automated citations found in the database."
    if citations_list:
        citations_text = "\n\n".join(citations_list)
        
    user_prompt = f"Here are the analysis reports to synthesize:\n\n{reports_text}\n\nAutomated Citations (Must be included at the end of your report):\n{citations_text}"
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        content = response.content
        if isinstance(content, list):
            final_report = "\\n".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
        else:
            final_report = str(content)
    except Exception as e:
        print(f"Error in analysis synthesizer: {e}")
        final_report = "Error generating final report."
        
    print("Synthesis complete.")
    
    new_reports = reports.copy()
    new_reports.append(final_report)
    
    return {
        "current_phase": "complete",
        "next_agent": "complete",
        "analysis_reports": new_reports
    }
