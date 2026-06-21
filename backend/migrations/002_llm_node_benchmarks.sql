-- LLM node benchmark results table
-- Used by benchmark.py to store latency/output per run
CREATE TABLE IF NOT EXISTS job_application_assistant.llm_node_benchmarks (
    id          SERIAL PRIMARY KEY,
    node_name   VARCHAR(100) NOT NULL,
    model       VARCHAR(100) NOT NULL,
    prompt_v    VARCHAR(20)  NOT NULL DEFAULT 'v1',
    latency_ms  INTEGER      NOT NULL DEFAULT 0,
    output_raw  TEXT,
    notes       TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
