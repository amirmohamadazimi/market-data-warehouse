-- Analytics layer. Returns and volatility are computed HERE, with window
-- functions -- not in pandas.
--
-- Dropped and recreated on every run: CREATE OR REPLACE VIEW cannot rename or
-- reorder a view's columns, so it would fail once a view's shape changes.
DROP VIEW IF EXISTS v_rolling_vol, v_returns, v_adjusted_prices, v_adjustment_events CASCADE;

-- One row per price-reset event. k multiplies every price BEFORE the event date.
CREATE VIEW v_adjustment_events AS
-- TSE: the base price (prev_final) differs from yesterday's final price, i.e. a
-- capital increase, a dividend, or a reopen after a halt. k = new base / old final.
SELECT symbol_id, date, k, 'tse_reset' AS kind
FROM (
    SELECT
        b.symbol_id,
        b.date,
        b.prev_final / NULLIF(LAG(b.final_price) OVER w, 0) AS k
    FROM daily_bars b
    JOIN symbols s USING (symbol_id)
    WHERE s.market = 'TSE'
    WINDOW w AS (PARTITION BY b.symbol_id ORDER BY b.date)
) t
WHERE k <> 1
UNION ALL
-- GLOBAL dividends (Yahoo's rule): k = 1 - dividend / last raw close before the
-- ex-date. No split factor: yfinance's close is already split-adjusted.
SELECT a.symbol_id, a.date, 1 - a.amount / p.close, 'dividend'
FROM corporate_actions a
JOIN LATERAL (
    SELECT close FROM daily_bars b
    WHERE b.symbol_id = a.symbol_id AND b.date < a.date
    ORDER BY b.date DESC
    LIMIT 1
) p ON TRUE
WHERE a.action_type = 'dividend';

-- Backward adjustment: price(d) x product of k for every event AFTER d.
-- SQL has no PRODUCT(), so EXP(SUM(LN(k))). Newest prices keep factor 1.
--
-- Rows before symbols.analysis_from are left out here (D19), so every view
-- built on this one (returns, vol, correlation) starts at the trusted period.
-- The filter sits outside the window, so the factors still see every event.
CREATE VIEW v_adjusted_prices AS
SELECT
    t.symbol_id,
    t.date,
    t.raw_price,
    t.adj_factor,
    t.raw_price * t.adj_factor AS price
FROM (
    SELECT
        b.symbol_id,
        b.date,
        COALESCE(b.final_price, b.close) AS raw_price,
        EXP(COALESCE(SUM(e.ln_k) OVER w, 0)) AS adj_factor
    FROM daily_bars b
    -- Combine same-day events first (sum of LNs = LN of the product), so two
    -- events on one day (e.g. dividend + split) can't duplicate the price row.
    LEFT JOIN (
        SELECT symbol_id, date, SUM(LN(k)) AS ln_k
        FROM v_adjustment_events
        GROUP BY symbol_id, date
    ) e USING (symbol_id, date)
    -- Newest first; "1 PRECEDING" stops before the row itself, so an event
    -- adjusts only the days before it, not its own day.
    WINDOW w AS (
        PARTITION BY b.symbol_id ORDER BY b.date DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    )
) t
JOIN symbols s ON s.symbol_id = t.symbol_id
WHERE s.analysis_from IS NULL OR t.date >= s.analysis_from;

-- Simple and log returns on adjusted prices, from one trading day to the next.
-- Across a trading halt this is one return over the whole gap.
CREATE VIEW v_returns AS
SELECT
    symbol_id,
    date,
    price / NULLIF(LAG(price) OVER w, 0) - 1        AS simple_return,
    LN(price / NULLIF(LAG(price) OVER w, 0))        AS log_return
FROM v_adjusted_prices
WINDOW w AS (PARTITION BY symbol_id ORDER BY date);

-- 20- and 60-day rolling volatility of log returns, annualised: 252 trading days
-- a year for GLOBAL, almost 240 for TSE (unverified it changes based on the nowruz, Sat-Wed week, more holidays). NULL until a
-- full window of returns exists.
CREATE VIEW v_rolling_vol AS
SELECT
    r.symbol_id,
    r.date,
    CASE WHEN COUNT(r.log_return) OVER w20 = 20
         THEN STDDEV_SAMP(r.log_return) OVER w20
              * SQRT(CASE s.market WHEN 'TSE' THEN 240 ELSE 252 END)
    END AS vol_20d,
    CASE WHEN COUNT(r.log_return) OVER w60 = 60
         THEN STDDEV_SAMP(r.log_return) OVER w60
              * SQRT(CASE s.market WHEN 'TSE' THEN 240 ELSE 252 END)
    END AS vol_60d
FROM v_returns r
JOIN symbols s USING (symbol_id)
WINDOW
    w20 AS (PARTITION BY r.symbol_id ORDER BY r.date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
    w60 AS (PARTITION BY r.symbol_id ORDER BY r.date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW);

-- Pairwise correlation of daily log returns over a chosen window, one row per
-- pair (both orders, plus 1.0 on the diagonal). A function, not a view, because
-- the window is a parameter.
--
-- Only dates where BOTH symbols have a return count (n_days says how many).
-- TSE trades Sat-Wed and the US Mon-Fri, so a TSE/GLOBAL pair shares only
-- Mon-Wed; and Tehran closes hours before New York opens, so same-day TSE/US
-- correlation understates the real link (news reaches Tehran a day later).
CREATE OR REPLACE FUNCTION correlation_matrix(start_date DATE, end_date DATE)
RETURNS TABLE (slug_a TEXT, slug_b TEXT, corr DOUBLE PRECISION, n_days BIGINT)
LANGUAGE sql STABLE AS $$
    SELECT sa.slug, sb.slug,
           CORR(a.log_return, b.log_return),
           COUNT(*)
    FROM v_returns a
    JOIN v_returns b ON b.date = a.date
    JOIN symbols sa ON sa.symbol_id = a.symbol_id
    JOIN symbols sb ON sb.symbol_id = b.symbol_id
    WHERE a.date BETWEEN start_date AND end_date
      AND a.log_return IS NOT NULL AND b.log_return IS NOT NULL
    GROUP BY sa.slug, sb.slug
$$;
