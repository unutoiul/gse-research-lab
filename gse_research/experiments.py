"""Controlled experiments: one rule change per arm, reproducible records.

Every run writes to results/<experiment>/<period>/ with the git commit, the
dataset SHA-256 and each config's SHA-256, so it can be traced and repeated.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import fields
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, data, metrics, signals, structure

ROOT = data.ROOT
CONFIG = ROOT / "config"
PROVISIONAL = ("PROVISIONAL. The Stage 4 parity gate has not passed: TradingView's pivot tie rule is unverified "
               "(`strict` assumed) and the data is OANDA, not the BlackBull feed GSE runs on.")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git() -> dict:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    # Code and config changes make a run dirty; the results being written do not.
    return {"commit": run("rev-parse", "HEAD"),
            "dirty": bool(run("status", "--porcelain", "--untracked-files=no", "--", ".", ":!results"))}


def _params(cls, overrides: dict):
    names = {f.name for f in fields(cls)}
    unknown = set(overrides) - names
    if unknown:
        raise ValueError(f"unknown {cls.__name__} keys: {sorted(unknown)}")
    return cls(**overrides)


def run_r001(period: str, allow_test: bool = False) -> Path:
    study_path = CONFIG / "R001" / "study.json"
    study = json.loads(study_path.read_text())
    if period not in study["periods"]:
        raise SystemExit(f"unknown period {period}")
    if period == "test" and not allow_test:
        raise SystemExit("The test period is opened once, with the owner's approval: pass --allow-test.")
    start, end = study["periods"][period]
    arm_paths = [CONFIG / "R001" / "C0.json", CONFIG / "R001" / "V1.json"]
    arms = {json.loads(p.read_text())["arm"]: json.loads(p.read_text()) for p in arm_paths}

    # Data up to the period end, plus two days so trades opened at the end can close.
    data_end = None if end is None else str((pd.Timestamp(end) + pd.Timedelta(days=2)).date())
    m15 = data.load("M15", start=study["warmup_start"], end=data_end)
    t_start = pd.Timestamp(start, tz="UTC")
    t_end = m15["time"].iloc[-1] if end is None else pd.Timestamp(end, tz="UTC")
    in_period = (m15["time"] >= t_start) & (m15["time"] < t_end)
    weeks = (t_end - t_start).total_seconds() / (7 * 86400)

    core = structure.CoreParams()
    prep = structure.prepare(m15, core)
    htf = structure.htf_context(m15, core)
    results, trades, funnels, cands = {}, {}, {}, {}
    for name, cfg in arms.items():
        core = _params(structure.CoreParams, cfg["core"])
        ctx = _params(structure.ContextParams, cfg["context"])
        out, _ = structure.run(m15, core, ctx, prep=prep)
        c = signals.golden_zone_candidates(m15, out, htf)
        c = c[c["time"].between(t_start, t_end, inclusive="left")].reset_index(drop=True)
        cands[name] = c
        funnels[name] = signals.golden_zone_funnel(out, in_period)
        exec_cfg = {k: v for k, v in cfg["execution"].items() if k != "name"}
        for slip in study["slippage"]:
            ex = backtest.Execution(**exec_cfg, slippage=slip)
            t = backtest.simulate(m15, c, ex).assign(arm=name, slippage=slip)
            trades[(name, slip)] = t
            results[f"{name}@{slip:.2f}"] = metrics.summarize(t, weeks)

    head = study["headline_slippage"]
    c0, v1 = trades[("C0", head)], trades[("V1", head)]
    c0_keys = set(zip(cands["C0"]["bar"], cands["C0"]["side"]))
    extra = v1[[(b, s) not in c0_keys for b, s in zip(v1["bar"], v1["side"])]]
    boot = metrics.bootstrap_mean_diff(c0, v1, **{"n": study["bootstrap"]["resamples"], "seed": study["bootstrap"]["seed"],
                                                  "level": study["bootstrap"]["level"]})

    out_dir = ROOT / "results" / "R001" / period
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(trades.values(), ignore_index=True).to_csv(out_dir / "trades.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    provenance = {
        "experiment": "R001", "period": period, "range": [str(t_start), str(t_end)], "weeks": round(weeks, 1),
        "git": _git(), "dataset": {"file": manifest["file"], "sha256": manifest["sha256"]},
        "configs": {p.name: _sha(p) for p in [study_path, *arm_paths]},
        "structure": structure.params_dict(structure.CoreParams(), structure.ContextParams()),
        "status": PROVISIONAL,
    }
    summary = {"provenance": provenance, "results": results, "bootstrap_V1_minus_C0": boot,
               "C0_split_by_paired_sweep": {
                   "K_kept_by_V1": metrics.summarize(c0[c0["bos_had_sweep"] == True]),  # noqa: E712
                   "R_removed_by_V1": metrics.summarize(c0[c0["bos_had_sweep"] == False]),  # noqa: E712
               },
               "E_V1_only": metrics.summarize(extra)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    report = _report(study, provenance, results, boot, c0, v1, extra, funnels, head)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    return out_dir


def _fmt(x) -> str:
    if isinstance(x, (float, np.floating)):
        return "–" if np.isnan(x) else ("∞" if np.isinf(x) else f"{x:.3f}" if abs(x) < 10 else f"{x:.1f}")
    return str(x)


def _md(frame: pd.DataFrame) -> str:
    cols = [frame.index.name or "", *frame.columns]
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for idx, row in frame.iterrows():
        lines.append("| " + " | ".join(_fmt(v) for v in [idx, *row.tolist()]) + " |")
    return "\n".join(lines)


def _report(study, prov, results, boot, c0, v1, extra, funnels, head) -> str:
    keys = ["trades", "trades_per_week", "win_rate", "avg_win_R", "avg_loss_R", "expectancy_R", "profit_factor",
            "max_drawdown_R", "avg_mfe_R", "avg_mae_R", "median_planned_rr", "avg_spread_R"]
    table = pd.DataFrame({k: {m: results[k].get(m, np.nan) for m in keys} for k in results}).T
    table.index.name = "arm@slippage"
    k = c0[c0["bos_had_sweep"] == True]  # noqa: E712
    r = c0[c0["bos_had_sweep"] == False]  # noqa: E712
    split = pd.DataFrame({"K (paired sweep, kept by V1)": metrics.summarize(k), "R (no paired sweep, removed by V1)": metrics.summarize(r),
                          "E (V1 only)": metrics.summarize(extra)}).T.reindex(columns=["trades", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R"])
    min_n = study["min_trades_per_arm"]
    n_c0, n_v1 = results[f"C0@{head:.2f}"]["trades"], results[f"V1@{head:.2f}"]["trades"]
    verdict = ("**Inconclusive:** an arm has fewer than "
               f"{min_n} trades (C0 {n_c0}, V1 {n_v1}), so the decision rule cannot be applied."
               if min(n_c0, n_v1) < min_n else "Both arms have enough trades for the decision rule (applied on validation only).")
    fun = pd.concat([f.set_index(["side", "stage"])[["rejected", "share_of_candles"]]
                     .rename(columns={"rejected": f"{a} rejected", "share_of_candles": f"{a} share"}) for a, f in funnels.items()], axis=1)
    fun.index = [f"{side} · {stage}" for side, stage in fun.index]
    parts = [
        f"# R001 — {prov['period']} period ({prov['range'][0][:10]} to {prov['range'][1][:10]})",
        "", f"> {prov['status']}", "",
        "Golden Zone turning on at a candle close; control C0 (Require Sweep off) versus V1 (on). Execution RXM-1 "
        "(next open, level-wick stop, first-obstacle target, 16 candles, bid/ask fills). Not GSE behaviour: a labelled research model.",
        "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset SHA-256 `{prov['dataset']['sha256'][:12]}…` · "
        f"{prov['weeks']} weeks",
        "", "## Results by arm and slippage", "",
        f"Headline slippage {head:.2f} (fixed before validation). Expectancy and drawdown in R after spread and slippage.",
        "", _md(table), "",
        "Exit reasons (C0, headline slippage): " + ", ".join(f"{k} {v}" for k, v in metrics.closed(c0)["reason"].value_counts().items()) + ".", "",
        f"**V1 − C0 expectancy (slippage {head:.2f}):** {_fmt(boot['diff'])} R, {int(study['bootstrap']['level']*100)}% weekly bootstrap interval "
        f"[{_fmt(boot['low'])}, {_fmt(boot['high'])}].", "", verdict, "",
        "## What V1 changes inside C0", "",
        "K: C0 candidates whose BOS had a paired qualified sweep (V1 keeps them). R: those without (V1 removes them). "
        "E: candidates only V1 produces (a new swept BOS while C0's zone was already on).", "",
        _md(split), "",
        "## By higher-timeframe stratum (C0)", "", _md(metrics.by_group(c0, "stratum")), "",
        "## By session (C0)", "", _md(metrics.by_group(c0, "session")), "",
        "## By direction (C0)", "", _md(metrics.by_group(c0.assign(direction=c0["side"].map({1: "long", -1: "short"})), "direction")), "",
        "## By sweep source of the paired sweep (C0, K only)", "", _md(metrics.by_group(k, "sweep_source")) if len(metrics.closed(k)) else "None.", "",
        "## Rejection funnel (candles in the period, first failing Golden Zone condition)", "", _md(fun), "",
        "## Limitations", "",
        "- Provisional until the parity gate: pivot tie rule assumed, OANDA mid prices for structure, not BlackBull.",
        "- RXM-1 is a research execution model. A candle that reaches both stop and target counts as a stop.",
        "- Each candidate is scored independently, so overlapping trades are counted separately.",
        "- Costs: OANDA bid/ask on every fill plus the slippage shown; no commission or financing.",
        "",
    ]
    return "\n".join(parts)
