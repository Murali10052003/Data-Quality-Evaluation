-- Performance indexes for dq_results when running 1M–10M+ rows
-- Run once against your PostgreSQL database

-- Fast lookups by run_id (filter by specific pipeline run)
CREATE INDEX IF NOT EXISTS idx_dq_results_run_id
    ON dq_results (run_id);

-- Fast time-range queries and ORDER BY run_timestamp DESC
CREATE INDEX IF NOT EXISTS idx_dq_results_timestamp
    ON dq_results (run_timestamp DESC);

-- Composite index for summary aggregation with filters
CREATE INDEX IF NOT EXISTS idx_dq_results_status_ts
    ON dq_results (status, run_timestamp);

-- Composite index for trend endpoint (DATE_TRUNC + GROUP BY)
CREATE INDEX IF NOT EXISTS idx_dq_results_ts_status
    ON dq_results (run_timestamp, status);

-- Composite for per-table/method breakdowns
CREATE INDEX IF NOT EXISTS idx_dq_results_table_method
    ON dq_results (table_name, dqmethod, status);
