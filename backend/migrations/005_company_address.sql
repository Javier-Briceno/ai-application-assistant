-- Migration 005: add company_address column to job_applications
-- Run once: python3 backend/migrations/run_migration.py 005_company_address.sql

ALTER TABLE job_application_assistant.job_applications
ADD COLUMN IF NOT EXISTS company_address TEXT DEFAULT '';
