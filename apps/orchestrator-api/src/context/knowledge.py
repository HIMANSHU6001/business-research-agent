import os
import asyncio
from typing import List, Dict, Any, Optional
import cohere
from sqlalchemy import text
from database import AsyncSessionLocal

class KnowledgeManager:
    """
    Manages semantic context (RAG) using pgvector for dense search,
    tsvector for sparse search (Hybrid), and Cohere for Cross-Encoder Reranking.
    """
    
    def __init__(self):
        cohere_api_key = os.getenv("COHERE_API_KEY")
        if not cohere_api_key:
            print("WARNING: COHERE_API_KEY is not set. Embeddings and reranking will fail.")
        self.cohere_client = cohere.AsyncClient(api_key=cohere_api_key)
        
    async def get_embedding(self, text_input: str, input_type: str = "search_query") -> List[float]:
        """
        Retrieves a 1024-dimensional embedding from Cohere.
        input_type should be 'search_document' for ingestion, and 'search_query' for querying.
        """
        response = await self.cohere_client.embed(
            texts=[text_input],
            model="embed-english-v3.0",
            input_type=input_type
        )
        return response.embeddings[0]

    async def store_context(self, research_id: str, agent_namespace: str, task_context: str, content: str):
        """
        Embeds and stores unstructured text into semantic_memory.
        """
        embedding = await self.get_embedding(content, input_type="search_document")
        
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO semantic_memory (research_id, agent_namespace, task_context, content, embedding)
                    VALUES (:research_id, :agent_namespace, :task_context, :content, :embedding)
                """),
                {
                    "research_id": research_id,
                    "agent_namespace": agent_namespace,
                    "task_context": task_context,
                    "content": content,
                    "embedding": str(embedding)
                }
            )
            await session.commit()
            
    async def search_context(self, research_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Performs Hybrid Search + Reranking on semantic_memory.
        """
        query_embedding = await self.get_embedding(query, input_type="search_query")
        
        # Candidate generation (Top 20 from Dense, Top 20 from Sparse, combined via RRF)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    WITH dense_search AS (
                        SELECT id, content, task_context, created_at,
                               embedding <=> :query_embedding::vector AS distance,
                               ROW_NUMBER() OVER(ORDER BY embedding <=> :query_embedding::vector) as dense_rank
                        FROM semantic_memory
                        WHERE research_id = :research_id
                        ORDER BY distance
                        LIMIT 20
                    ),
                    sparse_search AS (
                        SELECT id, content, task_context, created_at,
                               ts_rank_cd(fts, plainto_tsquery('english', :query)) AS rank,
                               ROW_NUMBER() OVER(ORDER BY ts_rank_cd(fts, plainto_tsquery('english', :query)) DESC) as sparse_rank
                        FROM semantic_memory
                        WHERE research_id = :research_id
                          AND fts @@ plainto_tsquery('english', :query)
                        ORDER BY rank DESC
                        LIMIT 20
                    ),
                    combined AS (
                        SELECT id, content, task_context, created_at,
                               COALESCE(1.0 / (60 + dense_rank), 0) + COALESCE(1.0 / (60 + sparse_rank), 0) AS rrf_score
                        FROM (
                            SELECT id, content, task_context, created_at, dense_rank, NULL AS sparse_rank FROM dense_search
                            UNION ALL
                            SELECT id, content, task_context, created_at, NULL AS dense_rank, sparse_rank FROM sparse_search
                        ) all_results
                    )
                    SELECT id, content, task_context, created_at, MAX(rrf_score) as final_score
                    FROM combined
                    GROUP BY id, content, task_context, created_at
                    ORDER BY final_score DESC
                    LIMIT 20;
                """),
                {
                    "query_embedding": str(query_embedding),
                    "research_id": research_id,
                    "query": query
                }
            )
            candidates = result.mappings().all()

        if not candidates:
            return []

        # Cross-Encoder Reranking
        docs_to_rerank = [c["content"] for c in candidates]
        
        try:
            rerank_response = await self.cohere_client.rerank(
                model="rerank-english-v3.0",
                query=query,
                documents=docs_to_rerank,
                top_n=limit
            )
            
            final_results = []
            for r in rerank_response.results:
                candidate = candidates[r.index]
                final_results.append({
                    "id": str(candidate["id"]),
                    "content": candidate["content"],
                    "task_context": candidate["task_context"],
                    "relevance_score": r.relevance_score
                })
            return final_results
        except Exception as e:
            print(f"Cohere reranking failed: {e}")
            # Fallback to pure RRF scores
            return [
                {
                    "id": str(c["id"]),
                    "content": c["content"],
                    "task_context": c["task_context"],
                    "relevance_score": float(c["final_score"])
                }
                for c in candidates[:limit]
            ]
            
    async def search_catalog(self, research_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Performs Hybrid Search + Reranking on semantic_catalog for finding datasets/artifacts.
        """
        query_embedding = await self.get_embedding(query, input_type="search_query")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    WITH dense_search AS (
                        SELECT id, artifact_id, schema_ref, description, db_table_pointer,
                               embedding <=> :query_embedding::vector AS distance,
                               ROW_NUMBER() OVER(ORDER BY embedding <=> :query_embedding::vector) as dense_rank
                        FROM semantic_catalog
                        WHERE research_id = :research_id AND status = 'READY'
                          AND embedding IS NOT NULL
                        ORDER BY distance
                        LIMIT 20
                    ),
                    sparse_search AS (
                        SELECT id, artifact_id, schema_ref, description, db_table_pointer,
                               ts_rank_cd(fts, plainto_tsquery('english', :query)) AS rank,
                               ROW_NUMBER() OVER(ORDER BY ts_rank_cd(fts, plainto_tsquery('english', :query)) DESC) as sparse_rank
                        FROM semantic_catalog
                        WHERE research_id = :research_id AND status = 'READY'
                          AND fts @@ plainto_tsquery('english', :query)
                        ORDER BY rank DESC
                        LIMIT 20
                    ),
                    combined AS (
                        SELECT id, artifact_id, schema_ref, description, db_table_pointer,
                               COALESCE(1.0 / (60 + dense_rank), 0) + COALESCE(1.0 / (60 + sparse_rank), 0) AS rrf_score
                        FROM (
                            SELECT id, artifact_id, schema_ref, description, db_table_pointer, dense_rank, NULL AS sparse_rank FROM dense_search
                            UNION ALL
                            SELECT id, artifact_id, schema_ref, description, db_table_pointer, NULL AS dense_rank, sparse_rank FROM sparse_search
                        ) all_results
                    )
                    SELECT id, artifact_id, schema_ref, description, db_table_pointer, MAX(rrf_score) as final_score
                    FROM combined
                    GROUP BY id, artifact_id, schema_ref, description, db_table_pointer
                    ORDER BY final_score DESC
                    LIMIT 20;
                """),
                {
                    "query_embedding": str(query_embedding),
                    "research_id": research_id,
                    "query": query
                }
            )
            candidates = result.mappings().all()

        if not candidates:
            return []

        # We construct a document string for reranking
        docs_to_rerank = [
            f"Artifact: {c['artifact_id']} | Schema: {c['schema_ref']} | Description: {c['description'] or ''}"
            for c in candidates
        ]
        
        try:
            rerank_response = await self.cohere_client.rerank(
                model="rerank-english-v3.0",
                query=query,
                documents=docs_to_rerank,
                top_n=limit
            )
            
            final_results = []
            for r in rerank_response.results:
                candidate = candidates[r.index]
                final_results.append({
                    "id": str(candidate["id"]),
                    "artifact_id": candidate["artifact_id"],
                    "schema_ref": candidate["schema_ref"],
                    "description": candidate["description"],
                    "db_table_pointer": candidate["db_table_pointer"],
                    "relevance_score": r.relevance_score
                })
            return final_results
        except Exception as e:
            print(f"Cohere catalog reranking failed: {e}")
            return [
                {
                    "id": str(c["id"]),
                    "artifact_id": c["artifact_id"],
                    "schema_ref": c["schema_ref"],
                    "description": c["description"],
                    "db_table_pointer": c["db_table_pointer"],
                    "relevance_score": float(c["final_score"])
                }
                for c in candidates[:limit]
            ]
