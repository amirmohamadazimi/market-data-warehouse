"""Tehran Stock Exchange ingestion (finpy-tse or pytse-client)."""


def fetch_daily_bars(ticker: str, since: str):
    """Fetch daily bars for one TSE ticker from `since` onward.

    Returns a DataFrame normalised to the shared schema:
    date, open, high, low, close, adj_close, volume, value, trade_count.
    """
    raise NotImplementedError


def fetch_corporate_actions(ticker: str):
    """Fetch splits / capital increases / dividends for one TSE ticker."""
    raise NotImplementedError
