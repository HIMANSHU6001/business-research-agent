import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

from context.knowledge import KnowledgeManager
import json

async def main():
    km = KnowledgeManager()
    
    research_id = "a09595bc-c112-4862-88e4-b8a6a9447966"
    query = "What is the trend of the unemployment rate in India?"
    
    print(f"Querying: '{query}'")
    results = await km.search_context(research_id, query)
    
    print(f"\nFound {len(results)} results.")
    for i, res in enumerate(results, 1):
        print(f"\n--- Result {i} (Score: {res['relevance_score']:.3f}) ---")
        print(f"Context: {res['task_context']}")
        print(f"Content snippet: {res['content']}...")

if __name__ == "__main__":
    asyncio.run(main())
