"""Tehran Stock Exchange fetcher (pytse-client). Needs a route to tsetmc.com (split tunneling)."""

import pandas as pd


def fetch_tse(ticker: str) -> pd.DataFrame:
    """Full unadjusted daily history for one TSE ticker, as pytse-client returns it (F1, F2).

    Form may change (date as a column); meaning may not: keep every column, keep
    pytse's own names (adjClose stays adjClose). Must match the files already in
    data/raw/tse/, so `load` reads old and new snapshots the same way.
    """
    import pytse_client

    # adjust=False: raw prices; adjusting happens in the views, never at fetch time.
    return pytse_client.download(symbols=ticker, adjust=False)[ticker]
