Notebooks here read **only** from SQL (`pd.read_sql`), never from a CSV on disk.
If a notebook needs a new column, add it as a view in `sql/002_views.sql`.

- `01_coverage.ipynb` — rows, symbols, date range, coverage heatmap (the README chart)
- `02_returns_and_vol.ipynb` — sanity-check the SQL return and volatility views
