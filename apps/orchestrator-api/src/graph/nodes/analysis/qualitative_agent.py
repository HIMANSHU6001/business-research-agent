from typing import List, cast
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from graph.state import ResearchState
from graph.nodes.collection.collection_utils import create_react_agent
from graph.nodes.analysis.frameworks import get_framework_instructions
from graph.tools.qualitative_tools import search_context, tavily_gap_search

# To restrict the agent from overusing Tavily, we'll wrap tavily_gap_search 
# with state management or rely on system prompt instructions and LLM discipline.
# The TRD requires a max of 2 uses per run, we will enforce this via prompt discipline 
# and potentially a tool wrapper if strict enforcement is needed, but the prompt is a good start.

def _get_qualitative_system_prompt(selected_framework: str) -> str:
    
    # Handle multiple frameworks if selected in Scoping
    frameworks_to_load = []
    if selected_framework:
        if isinstance(selected_framework, list):
            frameworks_to_load = selected_framework
        elif isinstance(selected_framework, str):
            frameworks_to_load = [f.strip() for f in selected_framework.split(',')]
    
    if not frameworks_to_load:
        frameworks_to_load = ["SWOT"] # Default if empty
        
    # Cap to 2 frameworks max
    frameworks_to_load = frameworks_to_load[:2]
    
    framework_instructions = get_framework_instructions(frameworks_to_load)

    return f"""You are the Qualitative Analysis Agent, a business analyst.
Your purpose is to interpret research evidence using established business frameworks.

## Your Selected Framework(s)
You must strictly follow the methodologies outlined below to conduct your analysis.
{framework_instructions}


## CRITICAL TOOL USAGE RULE
When invoking a tool, you MUST provide only the exact tool name in the tool name field. DO NOT include your JSON arguments inside the tool name!
- **CORRECT Tool Name**: `search_context`
- **INCORRECT Tool Name**: `search_context {{"query": "Apple strategy"}}`
If you put JSON in the tool name, the API will immediately crash and your task will fail.

## Workflow (follow this order strictly):
1. **Generate Queries**: Review the Evidence Checklist for your framework(s). Generate specific search queries based on what you need to fulfill the checklist. 
   - CRITICAL WARNING: DO NOT search for exact numerical figures (like "total revenue 2024" or "income_statement_f"). Numerical data is already calculated by the Quantitative Agent and provided in your task instructions. You must use `search_context` for UNSTRUCTURED, qualitative insights (like "strategy", "risks", "management commentary").
2. **Search Context**: Use the `search_context` tool to retrieve unstructured evidence from the Knowledge Manager (pgVector). 
   - **ANTI-LOOPING RULE**: You are limited to a maximum of 3 calls to `search_context`. If you do not find what you need, or if you receive identical/irrelevant results, you MUST stop searching and move to the next step. Do not get stuck in a loop of slight query variations. Do not try to extract numbers that do not exist in the unstructured text.
3. **Evaluate**: Evaluate the retrieved evidence against your framework's checklist.
4. **Tavily Gap Fill (Optional)**: If, and ONLY if, `search_context` fails to provide sufficient evidence for a critical checklist item, you may use `tavily_gap_search` to search the web. 
   - CRITICAL RULE: You are capped at a maximum of 2 calls to `tavily_gap_search` per execution. Do not waste them.
5. **Synthesize Report**: Draft a comprehensive qualitative report structured exactly according to the Expected Output Schema of your framework(s).

## Citation Rules
You must explicitly cite all facts in your report:
- If the fact came from `search_context`, cite the actual `Source/Context` provided in the search result (e.g., `[Artifact: WB_GS...]` or whatever the source text is). DO NOT just say `[Knowledge Manager]`.
- If the fact came from `tavily_gap_search`, cite the actual `URL` or `Source` provided in the web search result. DO NOT just say `[Tavily Web Search]`.
It must be trivially easy for the reader to distinguish gap-fill evidence from primary collected workspace evidence.

If you cannot find enough evidence after exhausting your search limits, generate the final response using the best available evidence and explicitly note any gaps in the report.
"""

qualitative_tools = [
    search_context,
    tavily_gap_search
]

from llm_utils import get_chat_groq, DEFAULT_MODEL

model = get_chat_groq(model=DEFAULT_MODEL, temperature=0.1)

async def run_qualitative_agent(state: ResearchState):
    """
    Qualitative Analysis Agent node.
    Performs reasoning over unstructured data using business frameworks.
    """
    # Create the ReAct agent executor
    agent_executor = create_react_agent(model, qualitative_tools)
    
    selected_framework = state.get("selected_framework", "SWOT")
    research_id = state.get("research_id", "")
    agent_task = state.get("agent_task", "Begin qualitative analysis.")
    
    system_prompt = _get_qualitative_system_prompt(selected_framework)
    
    analysis_reports = state.get("analysis_reports", [])
    reports_text = "\n\n".join(analysis_reports) if analysis_reports else "No prior analysis reports."
    
    task_instructions = f"Supervisor's Assigned Task: {agent_task}\n\nUse the following quantitative findings as your primary evidence to interpret:\n\n{reports_text}\n\nYou may also use search_context to find additional unstructured evidence if needed."
    
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=task_instructions)]
    
    config = {"recursion_limit": 25, "configurable": {"research_id": research_id}}
    response = await agent_executor.ainvoke({"messages": messages}, config=config)
    
    final_response = response["messages"][-1]
    
    # Extract content robustly (sometimes LLMs return a list of dict blocks)
    content = final_response.content
    if isinstance(content, list):
        text_content = "\\n".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
    else:
        text_content = str(content)
        
    new_reports = analysis_reports.copy()
    new_reports.append(f"## Qualitative Findings ({selected_framework})\\n" + text_content)

    return {
        "messages": [final_response],
        "analysis_reports": new_reports,
        "next_agent": "analysis_supervisor"
    }
