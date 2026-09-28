-- Per-symbol start of the trusted period for analysis (D19). Rows before it stay
-- in daily_bars and are still quality-checked; the views just skip them.
-- Example: CPER and BNO have months of zero-volume days early on (no trades,
-- Yahoo repeats the last price), which fake zero returns and bias vol/correlation.
ALTER TABLE symbols ADD COLUMN IF NOT EXISTS analysis_from DATE;
