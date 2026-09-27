"""The symbol universe. symbols.csv (repo root, in git) is the source of truth (D9)."""
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from .text import normalize_fa

SYMBOLS_CSV = Path(__file__).resolve().parent.parent / "symbols.csv"


def seed_symbols(engine, csv_path: Path) -> int:
    df = pd.read_csv(csv_path, dtype=str, sep=",")
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
