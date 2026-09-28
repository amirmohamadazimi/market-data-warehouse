"""The headline guarantee: running update twice must not change the row count."""

import pytest


@pytest.mark.skip(reason="not implemented yet")
def test_update_is_idempotent():
    raise NotImplementedError


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
