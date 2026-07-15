import os
import aiohttp
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from context.knowledge import KnowledgeManager

knowledge_manager = KnowledgeManager()

@tool
async def search_context(query: str, config: RunnableConfig) -> str:
    """
    Searches the workspace knowledge base (PostgreSQL vector database) for unstructured evidence 
    collected during this research session. Uses Hybrid Search (Dense + Sparse) + Reranking.
    
    Args:
        query: The search query (e.g. "competitor market share", "regulatory threats")
    """
    try:
        research_id = config.get("configurable", {}).get("research_id", "")
        results = await knowledge_manager.search_context(research_id=research_id, query=query, limit=10)
        
        if not results:
            return "No relevant evidence found in the workspace knowledge base for this query."
            
        output = f"Knowledge Search Results for '{query}':\n\n"
        for i, res in enumerate(results, 1):
            score = res.get('relevance_score', 0)
            source = res.get('task_context', 'Unknown Source')
            output += f"--- Result {i} (Relevance: {score:.2f}) ---\n"
            output += f"Source/Context: {source}\n"
            output += f"Content: {res['content']}\n\n"
            
        return output
    except Exception as e:
        return f"Error executing knowledge search: {str(e)}"

@tool
async def tavily_gap_search(query: str) -> str:
    """
    Performs a web search using the Tavily API to fill specific gaps in evidence.
    CRITICAL RULE: This tool MUST ONLY be used if search_context() fails to provide sufficient 
    evidence. Do not use this as a primary research tool.
    
    Args:
        query: The specific question or topic to search the web for.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY is not set in the environment. Web search is unavailable."
        
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "max_results": 5
            }
            async with session.post("https://api.tavily.com/search", json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    return f"Tavily API Error ({response.status}): {text}"
                    
                data = await response.json()
                
                output = f"Tavily Web Search Results for '{query}':\n\n"
                if "answer" in data and data["answer"]:
                    output += f"AI Summary: {data['answer']}\n\n"
                    
                if "results" in data:
                    for i, res in enumerate(data["results"], 1):
                        output += f"--- Source {i}: {res.get('title', 'Untitled')} ---\n"
                        output += f"URL: {res.get('url', 'Unknown')}\n"
                        output += f"Snippet: {res.get('content', '')}\n\n"
                        
                return output
    except Exception as e:
        return f"Error executing Tavily search: {str(e)}"
