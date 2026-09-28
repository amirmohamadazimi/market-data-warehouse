"""CLI entry point:  python -m warehouse update --since 2020-01-01"""

import argparse
import sys


def run_checks(engine) -> None:
    """Run the quality checks and print the report; exit 1 if any ERROR.

    The data stays saved either way: a failed check reports, it never rolls back.
    Exit code 1 lets scripts and schedulers see the failure without reading logs.
    """
    from .quality import report, run_all

    if report(run_all(engine)):
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="warehouse")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create schema and views, load symbols.csv and tse_price_limits.csv")

    p_update = sub.add_parser("update", help="incrementally fetch new bars")
    p_update.add_argument("--since", default="2020-01-01")
    p_update.add_argument("--market", choices=["TSE", "GLOBAL", "ALL"], default="ALL")

    p_fetch = sub.add_parser("fetch", help="download full histories into today's raw snapshot")
    p_fetch.add_argument("--market", choices=["TSE", "GLOBAL", "ALL"], default="ALL")

    sub.add_parser("load", help="load the latest raw snapshots into daily_bars (offline), then check")

    sub.add_parser("check", help="run data-quality checks")

    p_symbols = sub.add_parser("symbols", help="manage the symbol universe")
    p_symbols.add_argument("--add")
    p_symbols.add_argument("--market", choices=["TSE", "GLOBAL"])

    args = parser.parse_args()

    if args.command == "init":
        from .db import get_engine, init_schema
        from .quality import PRICE_LIMITS_CSV, seed_price_limits
        from .symbols import SYMBOLS_CSV, seed_symbols

        engine = get_engine()
        init_schema(engine)
        n = seed_symbols(engine, SYMBOLS_CSV)
        print(f"schema ready, {n} symbols upserted from {SYMBOLS_CSV.name}")
        n = seed_price_limits(engine, PRICE_LIMITS_CSV)
        print(f"{n} price limits loaded from {PRICE_LIMITS_CSV.name}")
        return

    if args.command == "fetch":
        from .db import get_engine
        from .fetch import fetch_all

        fetch_all(get_engine(), args.market)
        return

    if args.command == "load":
        from .db import get_engine
        from .load import load_all

        engine = get_engine()
        load_all(engine)
        run_checks(engine)
        return

    if args.command == "check":
        from .db import get_engine

        run_checks(get_engine())
        return

    raise NotImplementedError(f"command: {args.command}")


if __name__ == "__main__":
    main()
