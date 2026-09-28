"""The symbol universe. symbols.csv (repo root, in git) is the source of truth (D9)."""
import csv
import re

import pandas as pd
from pathlib import Path
from sqlalchemy import text
from .text import normalize_fa

SYMBOLS_CSV = Path(__file__).resolve().parent.parent / "symbols.csv"

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DEFAULT_CURRENCY = {"TSE": "IRR", "GLOBAL": "USD"}


def lookup_tse(ticker: str) -> dict:
    """InsCode and name for a TSE ticker from pytse-client's offline list (no internet).

    The list uses Persian letters, so the ticker is normalised first (D11).
    """
    from pytse_client import symbols_data

    info = symbols_data.symbols_information().get(normalize_fa(ticker))
    if info is None:
        raise ValueError(f"TSE ticker {ticker!r} not found in pytse-client's symbol list")
    return {"vendor_id": info["index"], "name": info["name"]}


def build_row(ticker: str, market: str, slug: str, name: str | None = None,
              sector: str | None = None, currency: str | None = None) -> dict:
    """One symbols.csv row, with the ID looked up for TSE. Raises ValueError on bad input."""
    if market not in DEFAULT_CURRENCY:
        raise ValueError(f"market must be one of {sorted(DEFAULT_CURRENCY)}, got {market!r}")
    if not SLUG_RE.match(slug):
        raise ValueError(f"slug {slug!r} must be lowercase letters, digits or _ (e.g. fameli)")

    ticker = normalize_fa(ticker.strip())
    if market == "TSE":
        found = lookup_tse(ticker)
        vendor_id, name = found["vendor_id"], name or found["name"]
    else:
        ticker = ticker.upper()
        vendor_id, name = ticker, name or ticker  # Yahoo's ticker is its own ID

    return {
        "ticker": ticker, "name": normalize_fa(name), "market": market,
        "sector": normalize_fa(sector), "currency": currency or DEFAULT_CURRENCY[market],
        "slug": slug, "vendor_id": vendor_id, "is_active": "true",
    }


def append_to_csv(csv_path: Path, row: dict) -> None:
    """Add one row to symbols.csv, refusing duplicates. Existing lines are not rewritten."""
    existing = pd.read_csv(csv_path, dtype=str)
    if (existing["slug"] == row["slug"]).any():
        raise ValueError(f"slug {row['slug']!r} is already in {csv_path.name}")
    same = existing[(existing["market"] == row["market"]) & (existing["vendor_id"] == row["vendor_id"])]
    if not same.empty:
        raise ValueError(f"{row['market']} {row['vendor_id']} is already in {csv_path.name} "
                         f"as {same['slug'].iloc[0]!r}")

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=list(existing.columns), lineterminator="\r\n").writerow(
            {c: row.get(c) or "" for c in existing.columns}
        )


def add_symbol(engine, csv_path: Path, **fields) -> dict:
    """`symbols --add`: csv first (the truth), then the database.

    If the program dies between the two steps, the csv already has the row and
    the next `init` puts it in the database. The other order could leave a
    symbol that exists only in the database and vanishes on the next rebuild.
    """
    row = build_row(**fields)
    append_to_csv(csv_path, row)
    seed_symbols(engine, csv_path)
    return row


def seed_symbols(engine, csv_path: Path) -> int:
    """Upsert the symbol universe from symbols.csv into the symbols table.

    Persian text is normalized (Arabic kaf/yeh -> Persian forms) and empty cells
    become NULL. Rows are matched on (market, vendor_id): new ones are inserted,
    existing ones have ticker, name, sector, currency, slug and is_active updated.
    Safe to re-run. Returns the number of CSV rows processed.
    """
    df =pd.read_csv(csv_path, dtype=str, sep=",")
    df = df.map(lambda x: normalize_fa(x) if isinstance(x, str) else x)

    df = df.astype(object).where(df.notna(), None)  # empty cells -> NULL, not NaN

    upsert_sql = text("""
        INSERT INTO symbols (ticker, name, market, sector, currency, slug, vendor_id, is_active)
        VALUES (:ticker, :name, :market, :sector, :currency, :slug, :vendor_id, :is_active)
        ON CONFLICT (market, vendor_id)
        DO UPDATE SET
            ticker    = EXCLUDED.ticker,
            name      = EXCLUDED.name,
            sector    = EXCLUDED.sector,
            currency  = EXCLUDED.currency,
            slug      = EXCLUDED.slug,
            is_active = EXCLUDED.is_active
    """)

    with engine.begin() as conn:
        conn.execute(upsert_sql, df.to_dict("records"))

    return len(df)
