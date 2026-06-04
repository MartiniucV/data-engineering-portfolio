-- MedInsight Analytics Platform - Database Initialization
-- Run once on first startup (Docker entrypoint or manual)

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA raw         TO vlad;
GRANT ALL PRIVILEGES ON SCHEMA staging     TO vlad;
GRANT ALL PRIVILEGES ON SCHEMA intermediate TO vlad;
GRANT ALL PRIVILEGES ON SCHEMA warehouse   TO vlad;
GRANT ALL PRIVILEGES ON SCHEMA analytics   TO vlad;

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
