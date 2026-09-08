"""Global equity ingestion via yfinance, normalised to the same schema as TSE."""


def fetch_daily_bars(ticker: str, since: str):
    """Fetch daily bars for one global ticker. Same output columns as ingest_tse."""
    raise NotImplementedError
