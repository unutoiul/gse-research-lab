"""GSE research command line.

    python -m gse_research download [--granularity M15] [--from 2006-01-01]
        fetch or update OANDA XAU_USD candles and data/manifest.json
    python -m gse_research quality
        per-year data quality report, written to results/data_quality/
    python -m gse_research r001 --period train|validate|test [--allow-test]
        R001 (Require Sweep off vs on), written to results/R001/<period>/
    python -m gse_research optimize [--trials 400] [--workers N]
        study O1: TradingView settings for the 15m Golden Zone, written to results/O1/
    python -m gse_research strategy-study [--workers N]
        study O2: GSE Strategy v4.0 swing lookbacks, written to results/O2/
    python -m gse_research targets-study [--workers N]
        study O3: GSE Strategy v4.0 stop and target constants, written to results/O3/
    python -m gse_research v41-study [--workers N]
        study O4: GSE Strategy v4.1, 15m/H1 lookback 8/10/12 x H4 lookback 6/8/10, written to results/O4/
    python -m gse_research event-study [--workers N]
        study E1: first touches of fresh and flipped levels against random levels, before costs, results/E1/
    python -m gse_research forward-test [--out DIR]
        forward test F1: flipped-level touches since 2026-10-13 against random levels, results/F1/
    python -m gse_research edge-search --shard I --of N --out DIR | --merge DIR --out DIR
        study G1: a broad rule search on 2016-2022, finalists judged once on the 2012-2015 holdout
        (GitHub Actions: edge-search.yml)
    python -m gse_research msnr-search [--study S1|S2] [--workers N]
        study S1: Malaysian SnR with confluences (10,368 combinations), written to results/S1/;
        study S2: the same with short fixed targets and long fixed stops (41,472), results/S2/
    python -m gse_research touch-search [--workers N] [--shard I --of N --out DIR] [--merge DIR]
        study S3: fresh and flipped level touches with inducement, stops, targets and trailing
        (86,184 combinations), written to results/S3/; --shard runs every N-th design into DIR,
        --merge joins the parts in DIR and judges them (GitHub Actions: s3-search.yml)
    python -m gse_research locked-test results/<name>/rule.json --allow-test
        one-shot test of a frozen rule on the locked test period (owner approval)
    python -m gse_research worker [--once] [--poll 60]
        run jobs queued from the website admin (Research tab)
    python -m gse_research run-job <job id>
        run one queued job and exit (GitHub Actions)
    python -m gse_research run-queue
        run every queued job, then exit
    python -m gse_research abandon-job <job id> <reason>
        mark a job failed when its GitHub run stopped early (GitHub Actions)
    python -m gse_research publish
        one-off: store the committed results/ as runs for the admin
"""

from __future__ import annotations

import argparse
from pathlib import Path
import json

import pandas as pd

from . import data, edge_search, event_study, experiments, forward, locked_test, msnr_search, optimize, quality, strategy_study, timeframes, touch_search, worker


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
    op = sub.add_parser("optimize", help="study O1: settings search on train, checked on validation")
    op.add_argument("--trials", type=int, default=400)
    op.add_argument("--seed", type=int, default=20261011)
    op.add_argument("--workers", type=int, default=None)
    ss = sub.add_parser("strategy-study", help="study O2: GSE Strategy v4.0 lookback grid")
    ss.add_argument("--workers", type=int, default=None)
    sub.add_parser("timeframes", help="study T1: the Golden Zone entry on 15m, 1H and 4H")
    ts = sub.add_parser("targets-study", help="study O3: GSE Strategy v4.0 stop and target constants")
    ts.add_argument("--workers", type=int, default=None)
    v4 = sub.add_parser("v41-study", help="study O4: GSE Strategy v4.1 lookbacks (nine settings)")
    v4.add_argument("--workers", type=int, default=None)
    es = sub.add_parser("event-study", help="study E1: do GSE levels have an edge before costs?")
    es.add_argument("--workers", type=int, default=None)
    fw = sub.add_parser("forward-test", help="forward test F1: flipped-level touches on unseen candles")
    fw.add_argument("--out", type=Path, default=None)
    eg = sub.add_parser("edge-search", help="study G1: broad rule search with an untouched holdout")
    eg.add_argument("--shard", type=int, default=None)
    eg.add_argument("--of", type=int, default=1)
    eg.add_argument("--out", type=Path, required=True)
    eg.add_argument("--merge", type=Path, default=None, help="folder with trials_part_*.csv: join, pick finalists, holdout")
    ms = sub.add_parser("msnr-search", help="study S1 / S2: Malaysian SnR with confluences")
    ms.add_argument("--study", choices=sorted(msnr_search.STUDIES), default="S1")
    ms.add_argument("--workers", type=int, default=None)
    tsr = sub.add_parser("touch-search", help="study S3: fresh/flipped touches with inducement and exits")
    tsr.add_argument("--workers", type=int, default=None)
    tsr.add_argument("--shard", type=int, default=None)
    tsr.add_argument("--of", type=int, default=1)
    tsr.add_argument("--out", type=Path, default=None)
    tsr.add_argument("--merge", type=Path, default=None, help="folder with trials_part_*.csv to join and judge")
    lt = sub.add_parser("locked-test", help="one-shot test of a frozen rule on the locked test period")
    lt.add_argument("rule")
    lt.add_argument("--allow-test", action="store_true", help="open the locked test period (owner approval)")
    wk = sub.add_parser("worker", help="run jobs queued from the website admin")
    wk.add_argument("--once", action="store_true", help="exit when the queue is empty")
    wk.add_argument("--poll", type=float, default=60.0, help="seconds between queue checks (Neon sleeps only if > its 5-minute window)")
    rj = sub.add_parser("run-job", help="run one queued job and exit (GitHub Actions)")
    rj.add_argument("job_id")
    sub.add_parser("run-queue", help="run every queued job, then exit")
    aj = sub.add_parser("abandon-job", help="mark a job failed when its GitHub run stopped first")
    aj.add_argument("job_id")
    aj.add_argument("reason")
    sub.add_parser("publish", help="store the committed results/ as runs for the admin")
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
    elif args.command == "optimize":
        out = optimize.run_study(args.trials, args.seed, args.workers)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "strategy-study":
        out = strategy_study.run_study(args.workers)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "timeframes":
        out = timeframes.run_study()
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "targets-study":
        out = strategy_study.run_targets_study(args.workers)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "v41-study":
        out = strategy_study.run_v41_study(args.workers)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "event-study":
        out = event_study.run_study(args.workers)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "forward-test":
        out = forward.run(args.out)
        print(json.loads((out / "summary.json").read_text(encoding="utf-8"))["text"])
        print(f"Report: {out / 'report.md'}")
    elif args.command == "edge-search":
        progress = lambda f, m: print(f"{f:5.0%} {m}", flush=True)
        if args.merge is not None:
            out = edge_search.merge(args.merge, args.out)
        else:
            out = edge_search.run_shard(args.shard or 0, args.of, args.out, progress)
        print(f"Written to {out}")
    elif args.command == "msnr-search":
        out = msnr_search.run_search(args.workers, progress=lambda f, m: print(f"{f:5.0%} {m}", flush=True), study=args.study)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "touch-search":
        progress = lambda f, m: print(f"{f:5.0%} {m}", flush=True)
        if args.merge is not None:
            out = touch_search.merge(args.merge, args.out, progress)
        else:
            out = touch_search.run_search(args.workers, args.out, progress, args.shard, args.of)
        print(f"Written to {out}")
    elif args.command == "locked-test":
        out = locked_test.run(Path(args.rule).resolve(), args.allow_test)
        print(f"Report: {(out / 'report.md').relative_to(data.ROOT)}")
    elif args.command == "worker":
        worker.run_worker(args.once, args.poll)
    elif args.command == "run-job":
        status = worker.Worker().run_one(args.job_id)
        raise SystemExit(1 if status == "failed" else 0)
    elif args.command == "run-queue":
        worker.run_worker(once=True, poll=1)
    elif args.command == "abandon-job":
        print("marked failed" if worker.abandon_job(args.job_id, args.reason) else "job already finished")
    elif args.command == "publish":
        print(worker.publish_committed())


if __name__ == "__main__":
    main()
