"""Engine, session and schema helpers."""

from sqlalchemy import create_engine

from .config import DATABASE_URL


def get_engine():
    """Return a SQLAlchemy engine for the warehouse database."""
    return create_engine(DATABASE_URL, future=True)


def init_schema(engine) -> None:
    """Execute sql/001_schema.sql then sql/002_views.sql. Must be re-runnable."""
    raise NotImplementedError


def last_date_for(engine, symbol_id: int):
    """Return MAX(date) already stored for a symbol, or None. Drives incremental update."""
    raise NotImplementedError


def upsert_bars(engine, rows) -> int:
    """INSERT ... ON CONFLICT DO NOTHING. Return the number of rows actually inserted."""
    raise NotImplementedError
