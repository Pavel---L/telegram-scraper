-- ============================================================================
-- Telegram Scraper Database Schema
-- ============================================================================
-- This schema stores Telegram messages with JSONB for flexible structure
-- and maintains scraper state for incremental updates.
-- ============================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Main messages table with JSONB storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    chat_peer_id BIGINT NOT NULL,
    message_id INTEGER NOT NULL,
    date TIMESTAMPTZ NOT NULL,
    
    -- JSONB column for flexible schema
    -- Contains: sender info, text, reactions, entities, etc.
    data JSONB NOT NULL,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure unique messages per chat
    UNIQUE(chat_peer_id, message_id)
);

-- ============================================================================
-- Performance indexes
-- ============================================================================

-- Composite index for chat filtering with date ordering
CREATE INDEX IF NOT EXISTS idx_messages_chat_date 
    ON messages(chat_peer_id, date DESC);

-- GIN index for JSONB queries (general purpose)
CREATE INDEX IF NOT EXISTS idx_messages_data_gin 
    ON messages USING gin(data);

-- GIN index with jsonb_path_ops for faster specific path queries
CREATE INDEX IF NOT EXISTS idx_messages_data_jsonb_path 
    ON messages USING gin(data jsonb_path_ops);

-- ============================================================================
-- Indexes on specific JSONB fields
-- ============================================================================

-- Index on sender_id for filtering by sender
CREATE INDEX IF NOT EXISTS idx_messages_sender_id 
    ON messages((data->>'sender_id'));

-- Full-text search index on message text (Russian language)
-- Change 'russian' to 'english' or other language if needed
CREATE INDEX IF NOT EXISTS idx_messages_text 
    ON messages USING gin(to_tsvector('russian', data->>'text'));

-- ============================================================================
-- Automatic updated_at trigger
-- ============================================================================

-- Function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before each update
CREATE TRIGGER update_messages_updated_at 
    BEFORE UPDATE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Scraper state table
-- ============================================================================
-- Tracks the last processed message ID for each chat to enable
-- incremental updates and avoid duplicate processing.
-- ============================================================================

CREATE TABLE IF NOT EXISTS scraper_state (
    chat_peer_id BIGINT PRIMARY KEY,
    last_message_id INTEGER NOT NULL,
    last_run_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Useful queries for reference
-- ============================================================================

-- Query messages by chat:
-- SELECT * FROM messages WHERE chat_peer_id = 123456 ORDER BY date DESC;

-- Query messages by sender:
-- SELECT * FROM messages WHERE data->>'sender_id' = '789012';

-- Full-text search in message text:
-- SELECT * FROM messages 
-- WHERE to_tsvector('russian', data->>'text') @@ to_tsquery('russian', 'keyword');

-- Query messages with specific reaction:
-- SELECT * FROM messages 
-- WHERE data @> '{"reactions": [{"emoji": "👍"}]}';

-- Get scraper state:
-- SELECT * FROM scraper_state WHERE chat_peer_id = 123456;
