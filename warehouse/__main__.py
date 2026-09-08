"""CLI entry point:  python -m warehouse update --since 2020-01-01"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="warehouse")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create schema and views")

    p_update = sub.add_parser("update", help="incrementally fetch new bars")
    p_update.add_argument("--since", default="2020-01-01")
    p_update.add_argument("--market", choices=["TSE", "GLOBAL", "ALL"], default="ALL")

    sub.add_parser("check", help="run data-quality checks")

    p_symbols = sub.add_parser("symbols", help="manage the symbol universe")
    p_symbols.add_argument("--add")
    p_symbols.add_argument("--market", choices=["TSE", "GLOBAL"])

    args = parser.parse_args()
    raise NotImplementedError(f"command: {args.command}")


if __name__ == "__main__":
    main()
