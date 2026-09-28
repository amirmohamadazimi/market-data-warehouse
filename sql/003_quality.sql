-- Quality layer. First migration: daily_bars already holds real data, so this
-- file only ADDS things and must be safe to run more than once.

-- TSE daily price limit history. tse_price_limits.csv (repo root, in git) is the
-- source of truth; `init` loads it. A limit applies from start_date until the
-- next row's start_date. NULL = unknown era, the limit check skips it.
CREATE TABLE IF NOT EXISTS tse_price_limits (
    start_date  DATE PRIMARY KEY,
    price_limit NUMERIC CHECK (price_limit > 0 AND price_limit < 1),
    evidence    TEXT NOT NULL
);

-- ERROR = impossible data, WARN = suspicious but possibly real.
-- IF NOT EXISTS skips the whole clause (CHECK included) on a rerun.
ALTER TABLE data_quality_log
    ADD COLUMN IF NOT EXISTS severity TEXT CHECK (severity IN ('ERROR', 'WARN'));
