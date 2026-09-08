# Market Data Warehouse — TSE + Global Equities

An automated pipeline that ingests daily Tehran Stock Exchange and global equity bars
into PostgreSQL, updates incrementally, and exposes a clean SQL analytics layer.

**Status:** 🚧 in progress · started 2026-09-08 · target ~12h of work

| | |
|---|---|
| Rows | _TBD_ |
| Symbols | _TBD_ |
| Date range | _TBD_ |
| Last refresh | _TBD_ |

---

## Problem

Every later project in this series — stylized facts, backtests, factor research —
starts by re-downloading price data and re-inventing adjustments. That is slow,
irreproducible, and the source of silent bugs (a CSV quietly missing three months,
a split not adjusted, a symbol renamed).

This repo solves that once: **one database, one schema, one refresh command.**
Everything downstream reads from SQL, never from a CSV lying around in a folder.

## Data

| Source | Coverage | Library |
|---|---|---|
| Tehran Stock Exchange | daily OHLCV, adjusted + unadjusted | `finpy-tse` or `pytse-client` |
| Global equities / indices | daily OHLCV | `yfinance` |

Both write into the **same** schema, so a TSE symbol and an S&P 500 symbol are
queried identically.

Tables:

- `symbols` — one row per instrument: ticker, name, market (`TSE` / `GLOBAL`), sector, currency, is_active
- `daily_bars` — `(symbol_id, date)` primary key; open, high, low, close, adj_close, volume, value, trade_count
- `corporate_actions` — splits, dividends, capital increases; used to build the adjusted series

Indexes on `(symbol_id, date)` and `(date)`.

## Method

1. **Ingest** — per-source adapter normalises its raw response into the shared schema.
2. **Incremental update** — for each symbol, look up `MAX(date)` already stored and
   request only from the day after. Writes use `INSERT ... ON CONFLICT DO NOTHING`
   (or `DO UPDATE` for restatements), so **rerunning the pipeline is idempotent** —
   run it twice and the row count does not change.
3. **Analytics layer** — SQL views, not pandas:
   - `v_adjusted_prices` — corporate-action-adjusted close
   - `v_returns` — simple and log returns via `LAG(...) OVER (PARTITION BY symbol_id ORDER BY date)`
   - `v_rolling_vol` — 20- and 60-day rolling volatility via window frames
   - `v_correlation_matrix` — pairwise correlation over a parameterised window
4. **Quality checks** — run after every update, results written to `data_quality_log`:
   - missing trading days vs. the exchange calendar
   - zero-volume days (TSE symbols halt often — flag, do not delete)
   - price jumps beyond the TSE daily price limit
   - duplicate `(symbol, date)` rows

## Results

_Fill in when the pipeline runs end to end._

- Row / symbol / year counts: _TBD_
- One chart here (e.g. coverage heatmap, or index level over the full history): `docs/figures/`
- Data-quality summary: _TBD_


## Limitations

- _TBD_ — e.g. TSE adjustment methodology, survivorship of delisted symbols,
  gaps around market closures, `yfinance` rate limits, no intraday data.

## How to run

Prerequisites: Python 3.11+, PostgreSQL 14+.

```bash
git clone https://github.com/amirmohamadazimi/market-data-warehouse.git
cd market-data-warehouse
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # then edit DATABASE_URL
```

Two commands to a populated database:

```bash
python -m warehouse init
```

```bash
python -m warehouse update --since 2020-01-01
```

Other commands:

```bash
python -m warehouse check          # run data-quality checks only
python -m warehouse symbols --add TAPICO --market TSE
pytest
```

## Scope checklist

- [ ] Ingestion module — TSE (`finpy-tse` / `pytse-client`) and global (`yfinance`) into one schema
- [ ] Real schema: `symbols`, `daily_bars`, `corporate_actions`, with PKs and `(symbol, date)` indexes
- [ ] Incremental update — fetches only new rows, idempotent on rerun
- [ ] SQL views: adjusted prices, simple + log returns, 20/60d rolling vol, correlation matrix
- [ ] CLI `python -m warehouse update --since 2020-01-01`
- [ ] Notebook that reads only from SQL, never from CSV
- [ ] Quality checks: missing days, zero-volume days, limit-breaking jumps, duplicates

## Done when

- [ ] A stranger clones the repo, runs two commands, and has a populated database
- [ ] Every return series is computed in SQL with a window function, not in pandas
- [ ] This README shows one chart and states how many rows, symbols, and years it covers

## Stack

Python · pandas · SQLAlchemy · PostgreSQL · parquet · pytest
