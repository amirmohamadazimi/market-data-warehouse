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


def refresh_sample() -> list[Path]:
    """Replace data/sample/ with the newest raw snapshot of every symbol file.

    Each file keeps its own fetch_date folder, so a stranger sees how old it is.
    Returns the new sample paths (relative to the repo).
    """
    import shutil

    newest: dict[tuple[str, str], Path] = {}
    for path in sorted(RAW_DIR.glob("*/*/*.parquet")):  # sorted: later dates overwrite
        if path.stem.endswith("_adjusted"):  # the TSE answer key (D7), not a load input
            continue
        newest[(path.parts[-3], path.stem)] = path

    if SAMPLE_DIR.exists():
        shutil.rmtree(SAMPLE_DIR)
    copied = []
    for (source, _slug), src in sorted(newest.items()):
        dst = SAMPLE_DIR / source / src.parent.name / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst.relative_to(DATA_DIR.parent))
    return copied
