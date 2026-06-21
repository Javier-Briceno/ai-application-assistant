-- Migration 003: add tailored_cv column to job_applications
-- Run once: python3 backend/migrations/run_migration.py 003_tailored_cv.sql

ALTER TABLE job_application_assistant.job_applications
ADD COLUMN IF NOT EXISTS tailored_cv TEXT;
