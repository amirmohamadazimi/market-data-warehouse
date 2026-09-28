"""CLI entry point. A fresh clone needs two commands:

    python -m warehouse init
    python -m warehouse update
"""

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

    p_update = sub.add_parser("update", help="fetch, then load, then check (the daily command)")
    p_update.add_argument("--market", choices=["TSE", "GLOBAL", "ALL"], default="ALL")

    p_fetch = sub.add_parser("fetch", help="download full histories into today's raw snapshot")
    p_fetch.add_argument("--market", choices=["TSE", "GLOBAL", "ALL"], default="ALL")

    sub.add_parser("load", help="load the latest raw snapshots into daily_bars (offline), then check")

    sub.add_parser("check", help="run data-quality checks")

    p_symbols = sub.add_parser(
        "symbols", help="list the symbols, or add one: symbols --add فملی --market TSE --slug fameli")
    p_symbols.add_argument("--add", metavar="TICKER", help="TSE ticker (Persian) or Yahoo ticker")
    p_symbols.add_argument("--market", choices=["TSE", "GLOBAL"])
    p_symbols.add_argument("--slug", help="short Finglish name for files and the CLI, e.g. fameli")
    p_symbols.add_argument("--name", help="full name (TSE: looked up if omitted)")
    p_symbols.add_argument("--sector")
    p_symbols.add_argument("--currency", help="default IRR for TSE, USD for GLOBAL")

    sub.add_parser("sample", help="copy the newest raw snapshot of every symbol into data/sample/")

    sub.add_parser("readme", help="refresh the README's numbers and chart from the database")

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

    if args.command == "update":
        from .db import get_engine
        from .fetch import fetch_all
        from .load import load_all

        # A blocked source (TSE without an Iranian IP) only prints a failure;
        # load then falls back to the newest snapshot it has, or the sample.
        engine = get_engine()
        fetch_all(engine, args.market)
        load_all(engine)
        run_checks(engine)
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

    if args.command == "symbols":
        import pandas as pd
        from sqlalchemy import text

        from .db import get_engine
        from .symbols import SYMBOLS_CSV, add_symbol

        engine = get_engine()
        if args.add:
            if not (args.market and args.slug):
                parser.error("symbols --add needs --market and --slug")
            try:
                row = add_symbol(engine, SYMBOLS_CSV, ticker=args.add, market=args.market,
                                 slug=args.slug, name=args.name, sector=args.sector,
                                 currency=args.currency)
            except ValueError as exc:
                sys.exit(f"error: {exc}")
            print(f"added {row['slug']} ({row['market']} {row['vendor_id']}, {row['name']}) "
                  f"to {SYMBOLS_CSV.name} and the database; run `update` to fetch its data")
            return
        with engine.connect() as conn:
            print(pd.read_sql(text("SELECT slug, ticker, market, vendor_id, name, is_active "
                                   "FROM symbols ORDER BY market, slug"), conn).to_string(index=False))
        return

    if args.command == "sample":
        from .landing import refresh_sample

        for path in refresh_sample():
            print(f"sample: {path}")
        return

    if args.command == "readme":
        from .db import get_engine
        from .report import refresh_readme

        print(f"README.md numbers refreshed, chart saved to {refresh_readme(get_engine())}")
        return

    raise NotImplementedError(f"command: {args.command}")


if __name__ == "__main__":
    main()
