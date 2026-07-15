-- PgVector
CREATE EXTENSION IF NOT EXISTS vector;

-- Catalog
CREATE TABLE semantic_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_id UUID NOT NULL,
    artifact_id VARCHAR(255) NOT NULL,
    source_mcp VARCHAR(100) NOT NULL,
    db_table_pointer VARCHAR(500) NOT NULL, -- e.g., '/shared/workspaces/{research_id}/{artifact_id}.parquet'
    schema_ref VARCHAR(100) NOT NULL,
    row_count INTEGER NOT NULL,
    time_range_start TIMESTAMP,
    time_range_end TIMESTAMP,
    inputs JSONB,
    description TEXT,
    citation TEXT, -- Added for automated traceability
    embedding vector(1024),
    fts tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(description, '') || ' ' || coalesce(schema_ref, ''))) STORED,
    status VARCHAR(50) DEFAULT 'READY', -- Used to prevent agents from reading while background LLM summarization is pending
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for Catalog
CREATE INDEX idx_catalog_research ON semantic_catalog(research_id);
CREATE INDEX idx_catalog_embedding ON semantic_catalog USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_catalog_fts ON semantic_catalog USING GIN (fts);

-- Schema Registry
CREATE TABLE schema_registry (
    schema_ref VARCHAR(100) PRIMARY KEY,
    columns JSONB NOT NULL, -- e.g., [{"name": "net_income", "type": "FLOAT"}, {"name": "fiscal_date", "type": "DATE"}]
    description TEXT
);

CREATE TABLE semantic_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_id UUID NOT NULL,
    agent_namespace VARCHAR(100) NOT NULL, -- e.g., 'financial_intelligence', 'macro_intelligence'
    task_context TEXT,
    content TEXT NOT NULL,
    embedding vector(1024), -- Assuming Cohere embed-english-v3.0 dimensions
    fts tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, '') || ' ' || coalesce(task_context, ''))) STORED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- HNSW index optimized for fast similarity search within a specific research session
CREATE INDEX idx_semantic_memory_research ON semantic_memory(research_id);
CREATE INDEX idx_semantic_embedding ON semantic_memory USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_semantic_fts ON semantic_memory USING GIN (fts);