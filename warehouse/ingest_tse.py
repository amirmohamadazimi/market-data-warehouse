"""Tehran Stock Exchange ingestion (finpy-tse or pytse-client)."""


def fetch_daily_bars(ticker: str, since: str):
    """Fetch daily bars for one TSE ticker from `since` onward.

    Returns a DataFrame normalised to the shared schema:
    date, open, high, low, close, volume, value, trade_count, final_price, prev_final.
    """
    raise NotImplementedError


def fetch_corporate_actions(ticker: str):
    """Fetch splits / capital increases / dividends for one TSE ticker."""
    raise NotImplementedError
