"""GSE research command line.

    python -m gse_research download [--granularity M15] [--from 2006-01-01]
        fetch or update OANDA XAU_USD candles and data/manifest.json
    python -m gse_research quality
        per-year data quality report, written to results/data_quality/
    python -m gse_research r001 --period train|validate|test [--allow-test]
        R001 (Require Sweep off vs on), written to results/R001/<period>/
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from . import data, experiments, quality


def main() -> None:
    parser = argparse.ArgumentParser(prog="gse_research")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="fetch or update OANDA XAU_USD candles")
    dl.add_argument("--granularity", choices=sorted(data.STEP), default="M15")
    dl.add_argument("--from", dest="start", default=data.FIRST_AVAILABLE)
    sub.add_parser("quality", help="per-year M15 data quality report")
    r1 = sub.add_parser("r001", help="run R001 on one period")
    r1.add_argument("--period", choices=["train", "validate", "test"], required=True)
    r1.add_argument("--allow-test", action="store_true", help="open the locked test period (owner approval)")
    args = parser.parse_args()

    if args.command == "download":
        df = data.update(args.granularity, args.start)
        print(f"{len(df):,} {args.granularity} candles, {df['time'].iloc[0]:%Y-%m-%d} to {df['time'].iloc[-1]:%Y-%m-%d %H:%M} UTC")
    elif args.command == "quality":
        manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
        df = data.load("M15", session_only=False)
        if data.file_sha256(data.dataset_path("M15")) != manifest["sha256"]:
            raise SystemExit("data/manifest.json does not match the M15 cache; run download again")
        path, report = quality.write_report(df, manifest, data.ROOT / "results" / "data_quality")
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(report)
        print(f"\nReport: {path.relative_to(data.ROOT)}")
    elif args.command == "r001":
        out = experiments.run_r001(args.period, args.allow_test)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")


if __name__ == "__main__":
    main()
