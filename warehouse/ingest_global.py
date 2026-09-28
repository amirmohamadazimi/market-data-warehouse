"""Global fetcher (yfinance). Goes through the VPN like any foreign site."""

import pandas as pd


def fetch_yfinance(ticker: str) -> pd.DataFrame:
    """Full daily history for one Yahoo ticker, unadjusted, with dividends and splits (F1, F2).

    Form may change (flat lowercase snake_case columns, date as a column); meaning
    may not: close must be Yahoo's raw close, not auto-adjusted. Must match the
    columns of the files already in data/raw/yfinance/, plus the action columns.
    """
    import yfinance as yf

    # auto_adjust=False keeps Close as Yahoo's raw close (Adj Close comes separately).
    raw = yf.download(
        ticker, period="max", auto_adjust=False, actions=True,
        progress=False, multi_level_index=False,
    )
    raw = raw.reset_index()
    raw.columns = [c.lower().replace(" ", "_") for c in raw.columns]
    return raw
