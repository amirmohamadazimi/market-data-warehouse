-- Analytics layer. Returns and volatility are computed HERE, with window
-- functions -- not in pandas.

-- TODO: adjusted close built from corporate_actions.
CREATE OR REPLACE VIEW v_adjusted_prices AS
SELECT symbol_id, date, adj_close AS price
FROM daily_bars;

-- TODO: simple and log returns via LAG().
CREATE OR REPLACE VIEW v_returns AS
SELECT
    symbol_id,
    date,
    price / NULLIF(LAG(price) OVER w, 0) - 1        AS simple_return,
    LN(price / NULLIF(LAG(price) OVER w, 0))        AS log_return
FROM v_adjusted_prices
WINDOW w AS (PARTITION BY symbol_id ORDER BY date);

-- TODO: 20- and 60-day rolling volatility, annualised.
CREATE OR REPLACE VIEW v_rolling_vol AS
SELECT
    symbol_id,
    date,
    STDDEV_SAMP(log_return) OVER (
        PARTITION BY symbol_id ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS vol_20d,
    STDDEV_SAMP(log_return) OVER (
        PARTITION BY symbol_id ORDER BY date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
    ) AS vol_60d
FROM v_returns;

-- TODO: pairwise correlation matrix over a chosen window.
