"""Data-quality checks run after every update."""


def missing_trading_days(engine, symbol_id: int):
    """Days on the exchange calendar with no bar stored."""
    raise NotImplementedError


def zero_volume_days(engine, symbol_id: int):
    """Days with volume == 0. Common on the TSE (halts) — flag, do not delete."""
    raise NotImplementedError


def limit_breaking_jumps(engine, symbol_id: int):
    """Close-to-close moves larger than the TSE daily price limit."""
    raise NotImplementedError


def duplicate_rows(engine):
    """Duplicate (symbol_id, date) rows. Should always be empty if the PK holds."""
    raise NotImplementedError


def run_all(engine) -> dict:
    """Run every check and write results to data_quality_log. Return a summary dict."""
    raise NotImplementedError
