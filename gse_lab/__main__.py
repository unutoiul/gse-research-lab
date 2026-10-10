"""GSE research lab command line.

    python -m gse_lab download [--from 2006-01-01]   fetch or update OANDA candles
    python -m gse_lab quality                         per-year data quality report
"""

from __future__ import annotations

import argparse

import pandas as pd

from . import data, quality


def main() -> None:
    parser = argparse.ArgumentParser(prog="gse_lab")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="fetch or update OANDA XAU_USD M15 candles")
    dl.add_argument("--from", dest="start", default=data.FIRST_AVAILABLE)
    sub.add_parser("quality", help="per-year data quality report")
    args = parser.parse_args()

    if args.command == "download":
        df = data.update(args.start)
        print(f"{len(df):,} M15 candles, {df['time'].iloc[0]:%Y-%m-%d} to {df['time'].iloc[-1]:%Y-%m-%d %H:%M} UTC")
    elif args.command == "quality":
        with pd.option_context("display.width", 200, "display.max_columns", 20):
            print(quality.year_report(data.load_m15()))


if __name__ == "__main__":
    main()
