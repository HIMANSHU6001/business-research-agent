import json
from typing import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from graph.state import ResearchState
import os

class AnalysisSupervisorOutput(TypedDict):
    reasoning: str
    next_agent: str
    agent_task: str

def run_analysis_supervisor(state: ResearchState) -> dict:
    print("--- DATA ANALYSIS SUPERVISOR ---")
    
    reports = state.get("analysis_reports", [])
    if reports is None:
        reports = []
    
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.1-8b-instant",
        temperature=0.0
    ).with_structured_output(AnalysisSupervisorOutput)

    system_prompt = """You are the Data Analysis Supervisor.
Your job is to route the analysis process. The sequence must be:
1. quantitative_agent
2. qualitative_agent
3. analysis_synthesizer

Available Agents:
- quantitative_agent: Performs statistical computation on datasets.
- qualitative_agent: Interprets evidence using the selected framework.
- analysis_synthesizer: Synthesizes the final report.

Review the research brief and the currently completed analysis reports.
Output the next_agent and the specific task for them.
"""

    completed_reports_info = f"Completed Analysis Reports: {len(reports)}\n\n"
    for i, report in enumerate(reports):
        completed_reports_info += f"Report {i+1}:\n{report[:500]}...\n\n"

    user_prompt = f"""
Research Brief: {state.get('research_brief', 'N/A')}
Selected Framework: {state.get('selected_framework', 'N/A')}

{completed_reports_info}

Based on the completed reports, who should run next?
If no reports exist, route to quantitative_agent.
If 1 report exists, route to qualitative_agent.
If 2 reports exist, route to analysis_synthesizer.
"""

    try:
        decision = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        print(f"Supervisor Decision: {decision['next_agent']}")
        print(f"Task: {decision['agent_task']}")
        
        return {
            "current_phase": "analysis",
            "next_agent": decision["next_agent"],
            "agent_task": decision["agent_task"]
        }
    except Exception as e:
        print(f"Error in analysis supervisor: {e}")
        if len(reports) == 0:
            next_agent = "quantitative_agent"
        elif len(reports) == 1:
            next_agent = "qualitative_agent"
        else:
            next_agent = "analysis_synthesizer"
            
        return {
            "current_phase": "analysis",
            "next_agent": next_agent,
            "agent_task": "Continue analysis."
        }

def run_analysis_synthesizer(state: ResearchState) -> dict:
    print("--- ANALYSIS SYNTHESIZER ---")
    
    reports = state.get("analysis_reports", [])
    if reports is None:
        reports = []
    
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.2
    )
    
    system_prompt = """You are the Lead Data Analyst. 
Synthesize the provided quantitative and qualitative reports into a Final Analysis Report.
Format:
- Executive summary (3-5 sentences)
- Qualitative findings
- Quantitative findings
- Synthesis (how they support/complicate each other)
- Citations
"""

    reports_text = "\n\n".join(reports)
    user_prompt = f"Here are the analysis reports to synthesize:\n\n{reports_text}"
    
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        final_report = response.content
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
