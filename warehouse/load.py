"""Landing zone -> daily_bars (+ corporate_actions). Never touches the internet (D4)."""

import pandas as pd
from sqlalchemy import text

from .db import upsert_actions, upsert_bars
from .landing import SOURCE_FOR_MARKET, latest_snapshot

# The shape every mapper must return (the contract), besides symbol_id and source.
CONTRACT = [
    "date", "open", "high", "low", "close",
    "volume", "value", "trade_count", "final_price", "prev_final",
]


def to_contract_tse(raw: pd.DataFrame) -> pd.DataFrame:
    """pytse-client columns -> CONTRACT columns (L2). Mind the adjClose trap."""
    # adjClose is TSE's official final price, not a split/dividend-adjusted close.
    bars = raw.rename(columns={
        "adjClose": "final_price",
        "yesterday": "prev_final",
        "count": "trade_count",
    })
    # A listing day has no previous price, and pytse sends base 0 (shepna,
    # 2008-06-29). 0 is not a price: store "no base" as NULL, never as 0.
    bars["prev_final"] = bars["prev_final"].where(bars["prev_final"] > 0)
    return bars[CONTRACT]


def to_contract_yfinance(raw: pd.DataFrame) -> pd.DataFrame:
    """yfinance columns -> CONTRACT columns (L2). Missing fields become NULL, never invented."""
    # adj_close is dropped: adjustment happens in the views, not in daily_bars.
    return raw.assign(value=None, trade_count=None, final_price=None, prev_final=None)[CONTRACT]


MAPPERS = {"tse": to_contract_tse, "yfinance": to_contract_yfinance}


def actions_yfinance(raw: pd.DataFrame) -> pd.DataFrame:
    """Yahoo's dividends column -> corporate_actions rows (one per ex-date).

    Splits are not loaded: yfinance's raw close is already split-adjusted, so a
    split factor in the views would adjust those prices twice.
    """
    if "dividends" not in raw.columns:  # snapshots fetched before actions=True
        return pd.DataFrame(columns=["date", "action_type", "ratio", "amount"])
    div = raw.loc[raw["dividends"] > 0, ["date", "dividends"]]
    return pd.DataFrame({
        "date": div["date"], "action_type": "dividend", "ratio": None, "amount": div["dividends"],
    })


# TSE needs no action mapper: its events are read from prev_final in the views.
ACTION_MAPPERS = {"yfinance": actions_yfinance}


def load_all(engine) -> dict[str, int]:
    """Load the latest snapshot of every symbol in `symbols` into daily_bars.

    Returns rows inserted or changed per slug (bars + corporate actions), so a
    second run on the same snapshots must return all zeros.
    """
    with engine.connect() as conn:
        symbols = conn.execute(text("SELECT symbol_id, slug, market FROM symbols")).all()

    changed = {}
    for symbol_id, slug, market in symbols:
        source = SOURCE_FOR_MARKET[market]
        path = latest_snapshot(source, slug)
        if path is None:
            print(f"{slug}: no file in data/raw/{source}/ or data/sample/{source}/, skipped")
            continue

        raw = pd.read_parquet(path)
        bars = MAPPERS[source](raw)
        missing = set(CONTRACT) - set(bars.columns)
        if missing:
            raise ValueError(f"{source} mapper is missing columns: {sorted(missing)}")

        bars = bars[CONTRACT].assign(symbol_id=symbol_id, source=source)
        n = upsert_bars(engine, bars)
        print(f"{slug}: {len(bars)} rows read from {path.parent.name}, {n} inserted or changed")
        changed[slug] = n

        if source in ACTION_MAPPERS:
            actions = ACTION_MAPPERS[source](raw).assign(symbol_id=symbol_id)
            n = upsert_actions(engine, actions)
            print(f"{slug}: {len(actions)} corporate actions read, {n} inserted or changed")
            changed[slug] += n
    return changed
