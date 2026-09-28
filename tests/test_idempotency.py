"""The headline guarantee: running update twice must not change the row count."""

import pytest


def test_update_is_idempotent():
    """Loading the same snapshots a second time writes nothing at all.

    The first load brings the database up to the newest snapshots (what `update`
    does after fetching); the second must report 0 inserted or changed for every
    symbol and leave the row count exactly the same.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from warehouse.db import get_engine
    from warehouse.load import load_all

    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM symbols LIMIT 1"))
    except OperationalError:
        pytest.skip("database not reachable")

    def row_count():
        with engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM daily_bars")).scalar_one()

    first = load_all(engine)
    if not first:
        pytest.skip("no snapshots to load; run init and update first")
    rows = row_count()
    second = load_all(engine)

    assert second == {slug: 0 for slug in first}
    assert row_count() == rows


def test_no_duplicate_symbol_date_rows():
    """The primary key refuses a second row for the same (symbol_id, date).

    This is why the quality checks have no duplicate check. Runs in a
    transaction that is always rolled back, so the database is left unchanged.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError, OperationalError

    from warehouse.db import get_engine

    try:
        conn = get_engine().connect()
    except OperationalError:
        pytest.skip("database not reachable")

    with conn:
        trans = conn.begin()
        try:
            row = conn.execute(text("SELECT symbol_id, date FROM daily_bars LIMIT 1")).first()
            if row is None:
                pytest.skip("daily_bars is empty; run init and load first")
            with pytest.raises(IntegrityError, match="daily_bars_pkey"):
                conn.execute(
                    text("INSERT INTO daily_bars (symbol_id, date, source) "
                         "VALUES (:symbol_id, :date, 'duplicate-test')"),
                    {"symbol_id": row.symbol_id, "date": row.date},
                )
        finally:
            trans.rollback()
