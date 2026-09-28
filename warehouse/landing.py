"""The landing zone: data/raw/{source}/{fetch_date}/{slug}.parquet (D6).

data/sample/ has the same layout and is in git (D15): a replay snapshot so a
fresh clone can load data with no internet and no Iranian IP.
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
SAMPLE_DIR = DATA_DIR / "sample"

# Which source folder each market's files land in.
SOURCE_FOR_MARKET = {"TSE": "tse", "GLOBAL": "yfinance"}


def snapshot_path(source: str, slug: str, fetch_date: str) -> Path:
    """Where fetch writes one symbol's file for one day (F3)."""
    return RAW_DIR / source / fetch_date / f"{slug}.parquet"


def _newest_in(base: Path, source: str, slug: str) -> Path | None:
    source_dir = base / source
    if not source_dir.is_dir():
        return None
    # fetch_date folders are ISO dates, so sorting the names sorts them by time.
    for day in sorted((d for d in source_dir.iterdir() if d.is_dir()), reverse=True):
        path = day / f"{slug}.parquet"
        if path.is_file():
            return path
    return None


def latest_snapshot(source: str, slug: str) -> Path | None:
    """Newest fetched file for this symbol (L1); the sample only if nothing was fetched."""
    return _newest_in(RAW_DIR, source, slug) or _newest_in(SAMPLE_DIR, source, slug)
