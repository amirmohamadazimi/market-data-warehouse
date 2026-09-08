-- Schema. Must be safe to run more than once.

CREATE TABLE IF NOT EXISTS symbols (
    symbol_id   SERIAL PRIMARY KEY,
    ticker      TEXT NOT NULL,
    name        TEXT,
    market      TEXT NOT NULL CHECK (market IN ('TSE', 'GLOBAL')),
    sector      TEXT,
    currency    TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (ticker, market)
);

CREATE TABLE IF NOT EXISTS daily_bars (
    symbol_id   INTEGER NOT NULL REFERENCES symbols (symbol_id),
    date        DATE    NOT NULL,
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    adj_close   NUMERIC,
    volume      BIGINT,
    value       NUMERIC,
    trade_count INTEGER,
    PRIMARY KEY (symbol_id, date)
);

CREATE INDEX IF NOT EXISTS ix_daily_bars_date ON daily_bars (date);

CREATE TABLE IF NOT EXISTS corporate_actions (
    action_id   SERIAL PRIMARY KEY,
    symbol_id   INTEGER NOT NULL REFERENCES symbols (symbol_id),
    date        DATE NOT NULL,
    action_type TEXT NOT NULL,   -- split | dividend | capital_increase
    ratio       NUMERIC,
    amount      NUMERIC,
    UNIQUE (symbol_id, date, action_type)
);

CREATE TABLE IF NOT EXISTS data_quality_log (
    log_id     SERIAL PRIMARY KEY,
    run_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_name TEXT NOT NULL,
    symbol_id  INTEGER REFERENCES symbols (symbol_id),
    date       DATE,
    detail     TEXT
);
