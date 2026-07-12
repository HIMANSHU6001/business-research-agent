from graph.state import ResearchState

def run_qualitative_agent(state: ResearchState) -> dict:
    print("--- QUALITATIVE ANALYSIS AGENT (SKELETON) ---")
    
    agent_task = state.get("agent_task", "No task assigned")
    framework = state.get("selected_framework", "NONE")
    reports = state.get("analysis_reports", [])
    if reports is None:
        reports = []
        
    print(f"Task: {agent_task}")
    print(f"Framework: {framework}")
    
    # Skeleton: We will just return a dummy report
    dummy_report = f"""## Qualitative Findings ({framework} - Skeleton)

- Strength/Opportunity: Favorable market conditions based on RAG context.
- Threat: Emerging competitors.
"""

    new_reports = reports.copy()
    new_reports.append(dummy_report)

    return {
        "analysis_reports": new_reports,
        "next_agent": "analysis_supervisor"
    }
