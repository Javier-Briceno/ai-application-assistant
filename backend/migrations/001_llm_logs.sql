-- Migration 001: create llm_logs table for tracking all LLM calls
-- Run once: psql -h 127.0.0.1 -U javier -d projects -f backend/migrations/001_llm_logs.sql

CREATE TABLE IF NOT EXISTS job_application_assistant.llm_logs (
    id          SERIAL PRIMARY KEY,
    model       VARCHAR(100)  NOT NULL,
    node_name   VARCHAR(100)  NOT NULL,
    profile_id  INTEGER       REFERENCES job_application_assistant.profiles(id) ON DELETE SET NULL,
    input_tokens  INTEGER     NOT NULL DEFAULT 0,
    output_tokens INTEGER     NOT NULL DEFAULT 0,
    latency_ms    INTEGER     NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(12, 6)       DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS llm_logs_profile_id_idx ON job_application_assistant.llm_logs (profile_id);
CREATE INDEX IF NOT EXISTS llm_logs_created_at_idx ON job_application_assistant.llm_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS llm_logs_node_name_idx  ON job_application_assistant.llm_logs (node_name);
