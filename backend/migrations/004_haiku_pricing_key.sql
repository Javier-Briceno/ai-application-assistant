-- Migration 004: add claude-haiku-4-5-20251001 to model_pricing
--
-- Root cause: llm.py logs model as 'claude-haiku-4-5-20251001' (the versioned key
-- returned by the Anthropic SDK), but model_pricing only had 'claude-haiku-4-5'.
-- _compute_cost() returned 0.0 for every Haiku call, making 47% of log rows useless.
--
-- Idempotent: WHERE NOT EXISTS guard makes it safe to run multiple times.
-- Run: psql -h 127.0.0.1 -U javier -d projects -f backend/migrations/004_haiku_pricing_key.sql

INSERT INTO job_application_assistant.model_pricing (model, input_price, output_price)
SELECT 'claude-haiku-4-5-20251001', 1.0, 5.0
WHERE NOT EXISTS (
    SELECT 1 FROM job_application_assistant.model_pricing
    WHERE model = 'claude-haiku-4-5-20251001'
);
