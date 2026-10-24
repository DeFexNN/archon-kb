-- Archon-KB: PostgreSQL Knowledge Base Schema with pgvector & Hybrid Search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Try to load pgvector extension if available
DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS "vector";
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'pgvector extension not found, will use float8[] fallback';
    END;
END $$;

-- 1. Documents table (Full document retention for zero data loss)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    title TEXT,
    category TEXT,
    content TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    line_count INT NOT NULL,
    byte_size INT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_docs_category ON documents(category);

-- 2. Structural Chunks (Headings, Code blocks, Tables, Paragraphs)
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    heading_path TEXT[] NOT NULL,
    chunk_type TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    start_line INT,
    end_line INT,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    embedding float8[], -- Supports both native pgvector and array fallback
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING GIN(tsv);

-- 3. Extensible Technical Entities
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name TEXT UNIQUE NOT NULL,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    subsystem TEXT,
    description TEXT,
    aliases TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}'::jsonb,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', canonical_name || ' ' || name || ' ' || COALESCE(description, ''))) STORED,
    embedding float8[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_name_lower ON entities(LOWER(name));
CREATE INDEX IF NOT EXISTS idx_entities_aliases ON entities USING GIN(aliases);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_tsv ON entities USING GIN(tsv);

-- 4. Entity Properties
CREATE TABLE IF NOT EXISTS entity_properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value TEXT,
    value_type TEXT,
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_props_entity_id ON entity_properties(entity_id);
CREATE INDEX IF NOT EXISTS idx_props_name ON entity_properties(name);

-- 5. Methods and Commands
CREATE TABLE IF NOT EXISTS methods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    language TEXT,
    implementation TEXT,
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_methods_entity_id ON methods(entity_id);

-- 6. Evidence and Provenance (Verbatim Quotes & Line Numbers)
CREATE TABLE IF NOT EXISTS evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    target_canonical TEXT NOT NULL,
    source_file TEXT NOT NULL,
    heading_path TEXT,
    location_line INT,
    source_text TEXT NOT NULL,
    confidence NUMERIC(3, 2) DEFAULT 1.0,
    extraction_rule TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evidence_doc ON evidence(document_id);
CREATE INDEX IF NOT EXISTS idx_evidence_target ON evidence(target_canonical);

-- 7. Relationships Graph
CREATE TABLE IF NOT EXISTS relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    confidence NUMERIC(3, 2) DEFAULT 1.0,
    evidence_id UUID REFERENCES evidence(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_entity_id, relationship_type, target_entity_id)
);
CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(relationship_type);
