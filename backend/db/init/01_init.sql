-- =============================================================================
-- Zep Chat Database Schema
-- =============================================================================
-- This script runs automatically on first PostgreSQL container startup.
-- For subsequent changes, use Alembic migrations.
-- =============================================================================

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search optimization

-- =============================================================================
-- Users Table
-- =============================================================================
-- Stores user information, mirrors Zep user for local caching
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL DEFAULT 'User',
    last_name VARCHAR(255) NOT NULL DEFAULT '',
    email VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for email lookups
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email) WHERE email IS NOT NULL;

-- =============================================================================
-- Sessions Table
-- =============================================================================
-- Chat sessions linked to users, with Zep session reference
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    zep_session_id VARCHAR(64),
    title VARCHAR(512),
    metadata JSONB NOT NULL DEFAULT '{}',
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for session queries
CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_sessions_created_at ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_sessions_user_created ON sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_sessions_zep_id ON sessions(zep_session_id) WHERE zep_session_id IS NOT NULL;

-- =============================================================================
-- Messages Table
-- =============================================================================
-- Chat messages with proper ordering and LLM metadata
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    llm_params JSONB,
    usage JSONB,
    sequence_order INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Ensure unique ordering per session
    UNIQUE (session_id, sequence_order)
);

-- Indexes for message queries
CREATE INDEX IF NOT EXISTS ix_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS ix_messages_session_order ON messages(session_id, sequence_order);
CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages(created_at DESC);

-- =============================================================================
-- Graph Cache Table
-- =============================================================================
-- Caches Zep knowledge graph nodes for faster visualization
CREATE TABLE IF NOT EXISTS graph_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    node_uuid VARCHAR(64) NOT NULL,
    node_name VARCHAR(512) NOT NULL,
    summary TEXT,
    node_type VARCHAR(64) NOT NULL DEFAULT 'unknown',
    edges JSONB,
    synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for graph queries
CREATE INDEX IF NOT EXISTS ix_graph_cache_user_id ON graph_cache(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_graph_cache_node_uuid ON graph_cache(node_uuid);
CREATE INDEX IF NOT EXISTS ix_graph_cache_synced_at ON graph_cache(synced_at);

-- =============================================================================
-- LLM Interactions Table
-- =============================================================================
-- Tracks LLM usage for analytics and cost management
CREATE TABLE IF NOT EXISTS llm_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    model_name VARCHAR(256) NOT NULL,
    provider VARCHAR(64) DEFAULT 'openrouter',
    temperature FLOAT,
    max_tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost FLOAT,
    duration_seconds FLOAT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for LLM interaction queries
CREATE INDEX IF NOT EXISTS ix_llm_interactions_session_id ON llm_interactions(session_id);
CREATE INDEX IF NOT EXISTS ix_llm_interactions_created_at ON llm_interactions(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_llm_interactions_model ON llm_interactions(model_name);

-- =============================================================================
-- RAG Documents Table (Optional - for tracking uploaded documents)
-- =============================================================================
CREATE TABLE IF NOT EXISTS rag_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(512) NOT NULL,
    file_type VARCHAR(32) NOT NULL,
    file_size_bytes INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    pinecone_namespace VARCHAR(256) DEFAULT 'default',
    metadata JSONB NOT NULL DEFAULT '{}',
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for document queries
CREATE INDEX IF NOT EXISTS ix_rag_documents_user_id ON rag_documents(user_id);
CREATE INDEX IF NOT EXISTS ix_rag_documents_uploaded_at ON rag_documents(uploaded_at DESC);

-- =============================================================================
-- Auto-update updated_at trigger
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Helper Views
-- =============================================================================

-- View: Session summary with message count and last activity
CREATE OR REPLACE VIEW session_summaries AS
SELECT 
    s.id as session_id,
    s.user_id,
    s.title,
    s.created_at,
    s.updated_at,
    s.is_archived,
    u.first_name,
    u.last_name,
    COUNT(m.id) as message_count,
    MAX(m.created_at) as last_message_at
FROM sessions s
JOIN users u ON s.user_id = u.id
LEFT JOIN messages m ON s.id = m.session_id
GROUP BY s.id, s.user_id, s.title, s.created_at, s.updated_at, s.is_archived, u.first_name, u.last_name;

-- View: User statistics
CREATE OR REPLACE VIEW user_statistics AS
SELECT 
    u.id as user_id,
    u.first_name,
    u.last_name,
    u.created_at as user_created_at,
    COUNT(DISTINCT s.id) as session_count,
    COUNT(DISTINCT m.id) as total_messages,
    COALESCE(SUM(li.total_tokens), 0) as total_tokens_used,
    COALESCE(SUM(li.cost), 0) as total_cost
FROM users u
LEFT JOIN sessions s ON u.id = s.user_id
LEFT JOIN messages m ON s.id = m.session_id
LEFT JOIN llm_interactions li ON s.id = li.session_id
GROUP BY u.id, u.first_name, u.last_name, u.created_at;

-- =============================================================================
-- Grant permissions (for security in production)
-- =============================================================================
-- In production, create a limited role:
-- CREATE ROLE app_user WITH LOGIN PASSWORD 'secure_password';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- =============================================================================
-- Done
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE 'Zep Chat database schema initialized successfully!';
END $$;
