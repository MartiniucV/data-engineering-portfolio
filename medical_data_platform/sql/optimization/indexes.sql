-- MedInsight: Performance Optimization Indexes
-- Run after initial data load to improve query performance

-- Composite index for date-range + status queries (most common filter pattern)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_appt_date_status
    ON raw.appointments (scheduled_at DESC, status)
    WHERE status = 'completed';

-- Partial index for billing analytics (paid invoices only)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_billing_paid
    ON raw.billing (invoice_date DESC, total_amount)
    WHERE payment_status = 'paid';

-- BRIN index on appointments for time-series scans (low maintenance overhead)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_appt_scheduled_brin
    ON raw.appointments USING BRIN (scheduled_at)
    WITH (pages_per_range = 128);

-- GIN index for text search on chronic conditions
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_conditions_gin
    ON raw.patients USING GIN (to_tsvector('romanian', coalesce(chronic_conditions, '')));

-- Stats update (run after index creation)
ANALYZE raw.appointments;
ANALYZE raw.billing;
ANALYZE raw.patients;
ANALYZE raw.doctors;
