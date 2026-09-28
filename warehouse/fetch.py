"""Internet -> landing zone. Never touches daily_bars (D4)."""

from datetime import date

from sqlalchemy import text

from .ingest_global import fetch_yfinance
from .ingest_tse import fetch_tse
from .landing import SOURCE_FOR_MARKET, snapshot_path

# TSE is asked by ticker (pytse-client's key), Yahoo by vendor_id (its ticker).
FETCHERS = {
    "tse": lambda ticker, vendor_id: fetch_tse(ticker),
    "yfinance": lambda ticker, vendor_id: fetch_yfinance(vendor_id),
}


def fetch_all(engine, market: str = "ALL") -> None:
    """Download every active symbol's full history into today's snapshot folder."""
    with engine.connect() as conn:
        symbols = conn.execute(
            text("SELECT slug, ticker, vendor_id, market FROM symbols WHERE is_active")
        ).all()

    today = date.today().isoformat()
    for slug, ticker, vendor_id, sym_market in symbols:
        if market != "ALL" and sym_market != market:
            continue
        source = SOURCE_FOR_MARKET[sym_market]
        try:
            raw = FETCHERS[source](ticker, vendor_id)
        except Exception as exc:  # one blocked source must not stop the others
            print(f"{slug}: fetch failed ({type(exc).__name__}: {exc})")
            continue
        if raw is None or raw.empty:
            print(f"{slug}: source returned no rows, nothing written")
            continue

        path = snapshot_path(source, slug, today)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(path, index=False)
        print(f"{slug}: {len(raw)} rows -> {path.relative_to(path.parents[3])}")
