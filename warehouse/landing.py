"""The landing zone: data/raw/{source}/{fetch_date}/{slug}.parquet (D6)."""

from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Which source folder each market's files land in.
SOURCE_FOR_MARKET = {"TSE": "tse", "GLOBAL": "yfinance"}


def latest_snapshot(source: str, slug: str) -> Path | None:
    """Path of the newest fetch_date folder's file for this symbol, or None (L1)."""
    source_dir = RAW_DIR / source
    if not source_dir.is_dir():
        return None
    # fetch_date folders are ISO dates, so sorting the names sorts them by time.
    for day in sorted((d for d in source_dir.iterdir() if d.is_dir()), reverse=True):
        path = day / f"{slug}.parquet"
        if path.is_file():
            return path
    return None
