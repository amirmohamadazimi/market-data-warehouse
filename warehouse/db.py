"""Engine, session and schema helpers."""

from pathlib import Path

from sqlalchemy import create_engine, text

from .config import DATABASE_URL

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def get_engine():
    """Return a SQLAlchemy engine for the warehouse database."""
    return create_engine(DATABASE_URL, future=True)


def init_schema(engine) -> None:
    """Execute sql/001_schema.sql then sql/002_views.sql. Must be re-runnable."""
    with engine.begin() as conn:
        for name in ("001_schema.sql", "002_views.sql"):
            conn.exec_driver_sql((SQL_DIR / name).read_text(encoding="utf-8"))


def last_date_for(engine, symbol_id: int):
    """Return MAX(date) already stored for a symbol, or None. Drives incremental update."""
    raise NotImplementedError


def _upsert(engine, table: str, key: tuple, rows, extra_set: str = "") -> int:
    """INSERT rows; on a key conflict UPDATE only when a non-key value differs.

    Column names come from our own code (never from data); values go in as :params.
    """
    if rows.empty:
        return 0
    cols = list(rows.columns)
    values = [c for c in cols if c not in key]
    stmt = text(f"""
        INSERT INTO {table} ({", ".join(cols)})
        VALUES ({", ".join(f":{c}" for c in cols)})
        ON CONFLICT ({", ".join(key)}) DO UPDATE SET
            {", ".join(f"{c} = EXCLUDED.{c}" for c in values)}{extra_set}
        WHERE ({", ".join(f"{table}.{c}" for c in values)})
            IS DISTINCT FROM ({", ".join(f"EXCLUDED.{c}" for c in values)})
    """)
    rows = rows.astype(object).where(rows.notna(), None)  # NaN -> NULL, not NUMERIC 'NaN'
    with engine.begin() as conn:
        result = conn.execute(stmt, rows.to_dict("records"))
    return result.rowcount


def upsert_bars(engine, rows) -> int:
    """Upsert a DataFrame of bars into daily_bars (L3).

    ON CONFLICT (symbol_id, date) DO UPDATE only when a value actually differs,
    so a rerun on identical data touches nothing. Return rows inserted or changed.
    """
    return _upsert(engine, "daily_bars", ("symbol_id", "date"), rows,
                   extra_set=", ingested_at = NOW()")


def upsert_actions(engine, rows) -> int:
    """Upsert corporate actions, same rule as upsert_bars. Return rows inserted or changed."""
    return _upsert(engine, "corporate_actions", ("symbol_id", "date", "action_type"), rows)
