"""Landing zone -> daily_bars. Never touches the internet (D4)."""

import pandas as pd
from sqlalchemy import text

from .db import upsert_bars
from .landing import SOURCE_FOR_MARKET, latest_snapshot

# The shape every mapper must return (the contract), besides symbol_id and source.
CONTRACT = [
    "date", "open", "high", "low", "close",
    "volume", "value", "trade_count", "final_price", "prev_final",
]


def to_contract_tse(raw: pd.DataFrame) -> pd.DataFrame:
    """pytse-client columns -> CONTRACT columns (L2). Mind the adjClose trap."""
    # adjClose is TSE's official final price, not a split/dividend-adjusted close.
    return raw.rename(columns={
        "adjClose": "final_price",
        "yesterday": "prev_final",
        "count": "trade_count",
    })[CONTRACT]


def to_contract_yfinance(raw: pd.DataFrame) -> pd.DataFrame:
    """yfinance columns -> CONTRACT columns (L2). Missing fields become NULL, never invented."""
    # adj_close is dropped: adjustment happens in the views, not in daily_bars.
    return raw.assign(value=None, trade_count=None, final_price=None, prev_final=None)[CONTRACT]


MAPPERS = {"tse": to_contract_tse, "yfinance": to_contract_yfinance}


def load_all(engine) -> None:
    """Load the latest snapshot of every symbol in `symbols` into daily_bars."""
    with engine.connect() as conn:
        symbols = conn.execute(text("SELECT symbol_id, slug, market FROM symbols")).all()

    for symbol_id, slug, market in symbols:
        source = SOURCE_FOR_MARKET[market]
        path = latest_snapshot(source, slug)
        if path is None:
            print(f"{slug}: no file in data/raw/{source}/, skipped")
            continue

        bars = MAPPERS[source](pd.read_parquet(path))
        missing = set(CONTRACT) - set(bars.columns)
        if missing:
            raise ValueError(f"{source} mapper is missing columns: {sorted(missing)}")

        bars = bars[CONTRACT].assign(symbol_id=symbol_id, source=source)
        n = upsert_bars(engine, bars)
        print(f"{slug}: {len(bars)} rows read from {path.parent.name}, {n} inserted or changed")
