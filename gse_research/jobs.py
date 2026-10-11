"""Jobs the website admin can launch, and how each becomes a stored result.

Every job kind validates its parameters here (the website validates the same
rules before queueing). The locked test period is never accepted: it stays a
command-line decision (`r001 --allow-test`).

A result ("run") is plain JSON: a title, the parameters, summary numbers, an
equity curve (cumulative R by exit time), tables (columns + rows), the
markdown report and the provenance (git commit, dataset SHA-256).
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics, optimize, quality, strategy, strategy_study

PERIODS = {"train": ("2016-01-01", "2019-01-01"), "validate": ("2019-01-01", "2023-01-01")}
WARMUP = "2015-10-01"
COSTS = {"net": strategy.Broker(slippage=0.10, spread_scale=1.0), "half": strategy.Broker(slippage=0.05, spread_scale=0.5),
         "gross": strategy.Broker(slippage=0.0, spread_scale=0.0)}

# kind -> {param: allowed values (tuple) or (min, max) integer range (list)} and defaults.
SCHEMA = {
    "data_update": ({}, {}),
    "r001": ({"period": ("train", "validate")}, {"period": "train"}),
    "strategy_backtest": ({"swing_len": [3, 50], "h4_swing_len": [3, 50], "period": ("train", "validate"),
                           "costs": tuple(COSTS), "path": ("conservative", "tradingview")},
                          {"swing_len": 10, "h4_swing_len": 10, "period": "train", "costs": "net", "path": "conservative"}),
    "search_o1": ({"trials": [20, 400]}, {"trials": 400}),
    "search_o2": ({}, {}),
}


def validate(kind: str, params: dict | None) -> dict:
    """Normalised parameters, or ValueError. Unknown keys are refused."""
    if kind not in SCHEMA:
        raise ValueError(f"unknown job kind {kind!r}")
    allowed, defaults = SCHEMA[kind]
    params = dict(params or {})
    unknown = set(params) - set(allowed)
    if unknown:
        raise ValueError(f"unknown parameters for {kind}: {sorted(unknown)}")
    out = {**defaults, **params}
    for key, rule in allowed.items():
        value = out[key]
        if isinstance(rule, list):
            if not isinstance(value, int) or isinstance(value, bool) or not rule[0] <= value <= rule[1]:
                raise ValueError(f"{key} must be an integer from {rule[0]} to {rule[1]}")
        elif value not in rule:
            raise ValueError(f"{key} must be one of {', '.join(rule)}")
    return out


# ── JSON helpers ────────────────────────────────────────────────────────

def clean(obj):
    """JSON-safe: numpy scalars to Python, NaN/inf to None, timestamps to ISO text."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if obj is pd.NaT or (obj is not None and not isinstance(obj, (str, bool, int)) and pd.isna(obj)):
        return None
    return obj


def table(frame: pd.DataFrame, index: bool = True) -> dict:
    f = frame.reset_index() if index else frame
    return clean({"columns": [str(c) for c in f.columns], "rows": f.to_numpy().tolist()})


def equity(trades: pd.DataFrame, max_points: int = 800) -> list:
    """Cumulative R by exit time, at most max_points points (the last one always kept)."""
    t = metrics.closed(trades)
    if t.empty:
        return []
    t = t.sort_values("exit_time")
    pts = list(zip(t["exit_time"], t["R"].cumsum()))
    if len(pts) > max_points:
        step = math.ceil(len(pts) / max_points)
        pts = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
    return clean([[ts, round(float(v), 4)] for ts, v in pts])


def _provenance(extra: dict | None = None) -> dict:
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    return clean({"git": experiments._git(), "dataset": {"file": manifest["file"], "sha256": manifest["sha256"]},
                  "status": experiments.PROVISIONAL, **(extra or {})})


# ── Job runners ─────────────────────────────────────────────────────────

def run_data_update(params: dict, work: Path, progress) -> tuple[None, dict]:
    """Download new candles, rebuild the quality report; returns the dataset state (no run)."""
    progress(0.05, "downloading OANDA candles")
    data.update("M15")
    progress(0.7, "quality report")
    return None, dataset_state()


def dataset_state() -> dict:
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    report = quality.year_report(data.load("M15", session_only=False))
    return clean({"manifest": manifest, "years": table(report)})


def run_strategy_backtest(params: dict, work: Path, progress) -> tuple[dict, None]:
    a, b = PERIODS[params["period"]]
    progress(0.05, "loading candles")
    m15 = data.load("M15", start=WARMUP, end=str((pd.Timestamp(b) + pd.Timedelta(days=2)).date()))
    progress(0.15, "levels, 1H/4H snapshots and signals")
    p = strategy.StrategyParams(swing_len=params["swing_len"], h4_swing_len=params["h4_swing_len"])
    sig = strategy.signals(m15, p)
    progress(0.85, "simulating orders")
    broker = strategy.Broker(path=params["path"], slippage=COSTS[params["costs"]].slippage, spread_scale=COSTS[params["costs"]].spread_scale)
    trades, counts = strategy.simulate(m15, sig, a, b, broker)
    weeks = (pd.Timestamp(b) - pd.Timestamp(a)).days / 7
    summary = {**metrics.summarize(trades, weeks), **{f"orders_{k}": v for k, v in counts.items()}}
    in_period = m15["close_time"].between(pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC"), inclusive="left")
    reasons = sig.loc[in_period, "reason"].value_counts().rename("candles").to_frame()
    reasons["share"] = reasons["candles"] / reasons["candles"].sum()
    reasons.index.name = "candle state"
    closed = metrics.closed(trades)
    tables = {"Why a candle had no order (signal funnel)": table(reasons)}
    if len(closed):
        by_year = metrics.by_group(closed.assign(year=closed["entry_time"].dt.year), "year")
        by_year.index.name = "year"
        by_dir = metrics.by_group(closed.assign(direction=closed["dir"].map({1: "long", -1: "short"})), "direction")
        by_dir.index.name = "direction"
        exits = closed["reason"].value_counts().rename("trades").to_frame()
        exits.index.name = "exit"
        recent = closed.sort_values("fill_time").tail(200)[["signal_time", "fill_time", "dir", "entry", "fill", "stop", "tp2", "exit_time", "exit", "reason", "R"]]
        tables.update({"By year": table(by_year), "By direction": table(by_dir), "Exit reasons": table(exits),
                       "Last 200 trades": table(recent, index=False)})
    title = f"Strategy v4.0 · chart {p.swing_len} / H4 {p.h4_swing_len} · {params['period']} · {params['costs']} costs"
    report = "\n".join([
        f"# {title}", "", f"> {experiments.PROVISIONAL}", "",
        "GSE Strategy v4.0 as written (fresh-level limit, 4H direction, website target engine), ported to Python and checked "
        "against the Pine source. Fills use OANDA bid/ask (costs: "
        f"{params['costs']}), intrabar order: {params['path']}.", "",
        f"Trades {summary['trades']}, win rate {experiments._fmt(summary['win_rate'])}, expectancy {experiments._fmt(summary['expectancy_R'])} R, "
        f"profit factor {experiments._fmt(summary['profit_factor'])}, max drawdown {experiments._fmt(summary['max_drawdown_R'])} R.", ""])
    return {"kind": "strategy_backtest", "title": title, "params": params, "summary": clean(summary),
            "equity": {"series": {params["costs"]: equity(trades)}}, "tables": tables, "report_md": report,
            "provenance": _provenance()}, None


def run_r001(params: dict, work: Path, progress) -> tuple[dict, None]:
    progress(0.1, f"R001 on {params['period']}")
    out = experiments.run_r001(params["period"], out_dir=work)
    return _r001_result(out, params), None


def _r001_result(out: Path, params: dict, source: str | None = None) -> dict:
    summary = json.loads((out / "summary.json").read_text())
    trades = pd.read_csv(out / "trades.csv", parse_dates=["time", "entry_time", "exit_time"])
    head = 0.10
    series = {arm: equity(trades[(trades["arm"] == arm) & (trades["slippage"] == head)]) for arm in ("C0", "V1")}
    results = pd.DataFrame(summary["results"]).T
    results.index.name = "arm@slippage"
    keep = [c for c in ("trades", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R", "avg_spread_R") if c in results]
    c0 = summary["results"].get(f"C0@{head:.2f}", {})
    v1 = summary["results"].get(f"V1@{head:.2f}", {})
    return {"kind": "r001", "title": f"R001 · Require Sweep off vs on · {params['period']}", "params": params,
            "summary": clean({"C0_trades": c0.get("trades"), "C0_expectancy_R": c0.get("expectancy_R"),
                              "V1_trades": v1.get("trades"), "V1_expectancy_R": v1.get("expectancy_R"),
                              "V1_minus_C0": summary["bootstrap_V1_minus_C0"]}),
            "equity": {"series": series}, "tables": {"Results by arm and slippage": table(results[keep])},
            "report_md": (out / "report.md").read_text(encoding="utf-8"),
            "provenance": clean({**summary["provenance"], **({"source": source} if source else {})})}


def run_search_o1(params: dict, work: Path, progress) -> tuple[dict, None]:
    out = optimize.run_study(params["trials"], out_dir=work, progress=progress)
    return _o1_result(out, params), None


def _o1_result(out: Path, params: dict, source: str | None = None) -> dict:
    trials = pd.read_csv(out / "trials.csv")
    eligible = trials[trials["train_trades"] >= optimize.MIN_TRAIN_TRADES]
    top = eligible.sort_values("train_expectancy_R", ascending=False).head(20)
    chosen = json.loads((out / "chosen.json").read_text())
    return {"kind": "search_o1", "title": f"O1 · Golden Zone settings search · {len(trials)} configurations", "params": params,
            "summary": clean({"configurations": len(trials), "eligible": len(eligible),
                              "positive_on_validation": int((eligible["val_expectancy_R"] > 0).sum()),
                              "best_validation_expectancy_R": eligible["val_expectancy_R"].max() if len(eligible) else None,
                              "train_val_spearman": eligible[["train_expectancy_R", "val_expectancy_R"]].corr(method="spearman").iloc[0, 1] if len(eligible) > 2 else None}),
            "equity": None, "tables": {"Top 20 on train, with validation": table(top, index=False)},
            "report_md": (out / "report.md").read_text(encoding="utf-8"),
            "provenance": clean({**chosen["provenance"], **({"source": source} if source else {})})}


def run_search_o2(params: dict, work: Path, progress) -> tuple[dict, None]:
    out = strategy_study.run_study(out_dir=work, progress=progress)
    return _o2_result(out, params), None


def _o2_result(out: Path, params: dict, source: str | None = None) -> dict:
    trials = pd.read_csv(out / "trials.csv")
    top = trials.sort_values("train_net_expectancy_R", ascending=False).head(10)
    pivot = trials.pivot(index="swing_len", columns="h4_swing_len", values="val_net_expectancy_R").round(3)
    pivot.index.name = "chart \\ H4"
    return {"kind": "search_o2", "title": f"O2 · Strategy v4.0 lookback grid · {len(trials)} settings", "params": params,
            "summary": clean({"settings": len(trials), "positive_val_net": int((trials["val_net_expectancy_R"] > 0).sum()),
                              "positive_val_gross": int((trials["val_gross_expectancy_R"] > 0).sum()),
                              "best_val_net_expectancy_R": trials["val_net_expectancy_R"].max(),
                              "best_val_half_expectancy_R": trials["val_half_expectancy_R"].max()}),
            "equity": None, "tables": {"Top 10 on train (net), with validation": table(top, index=False),
                                       "Validation net expectancy (rows chart lookback, columns H4 lookback)": table(pivot)},
            "report_md": (out / "report.md").read_text(encoding="utf-8"), "provenance": _provenance({"source": source} if source else None)}


def _o3_result(out: Path, params: dict, source: str | None = None) -> dict:
    trials = pd.read_csv(out / "trials.csv")
    cols = ["stop_buffer_atr", "min_r", "max_atr", "train_net_trades", "train_net_expectancy_R", "train_gross_expectancy_R",
            "val_net_trades", "val_net_expectancy_R", "val_half_expectancy_R", "val_gross_expectancy_R", "val_net_max_drawdown_R"]
    ranked = trials.sort_values("train_net_expectancy_R", ascending=False)[cols]
    tables = {"All settings, best training result first": table(ranked, index=False)}
    for m in sorted(trials["max_atr"].unique()):
        pivot = trials[trials["max_atr"] == m].pivot(index="stop_buffer_atr", columns="min_r", values="val_net_expectancy_R").round(3)
        pivot.index.name = "stop buffer \\ min R"
        tables[f"Validation net expectancy, max {m:g} ATR"] = table(pivot)
    both_gross = int(((trials["train_gross_expectancy_R"] > 0) & (trials["val_gross_expectancy_R"] > 0)).sum())
    return {"kind": "search_o3", "title": f"O3 · Strategy v4.0 stop and target rules · {len(trials)} settings", "params": params,
            "summary": clean({"settings": len(trials), "positive_val_net": int((trials["val_net_expectancy_R"] > 0).sum()),
                              "positive_val_half": int((trials["val_half_expectancy_R"] > 0).sum()),
                              "positive_gross_both_periods": both_gross,
                              "best_val_net_expectancy_R": trials["val_net_expectancy_R"].max()}),
            "equity": None, "tables": tables, "report_md": (out / "report.md").read_text(encoding="utf-8"),
            "provenance": _provenance({"source": source} if source else None)}


def _t1_result(out: Path, params: dict, source: str | None = None) -> dict:
    summary = pd.read_csv(out / "summary.csv")
    trades = pd.read_csv(out / "trades_net.csv", parse_dates=["time", "entry_time", "exit_time"])
    series = {f"{tf} {p}": equity(trades[(trades["timeframe"] == tf) & (trades["period"] == p)])
              for tf in ("15m", "1H", "4H") for p in ("train", "validate")}
    val = summary[summary["period"] == "validate"].set_index("timeframe")
    cols = ["timeframe", "period", "net_trades", "net_win_rate", "net_expectancy_R", "net_profit_factor", "net_max_drawdown_R",
            "net_avg_spread_R", "half_expectancy_R", "gross_expectancy_R"]
    return {"kind": "study_t1", "title": "T1 · Golden Zone entry on 15m, 1H and 4H", "params": params,
            "summary": clean({f"{tf}_validate_net_R": val.at[tf, "net_expectancy_R"] for tf in val.index}
                             | {f"{tf}_validate_trades": val.at[tf, "net_trades"] for tf in val.index}),
            "equity": {"series": series}, "tables": {"Results by timeframe and period": table(summary[cols], index=False)},
            "report_md": (out / "report.md").read_text(encoding="utf-8"),
            "provenance": _provenance({"source": source} if source else None)}


RUNNERS = {"data_update": run_data_update, "r001": run_r001, "strategy_backtest": run_strategy_backtest,
           "search_o1": run_search_o1, "search_o2": run_search_o2}


def committed_results() -> list[dict]:
    """The results already in results/ (R001 train, O1, O2) as runs, for a one-off publish."""
    root = data.ROOT / "results"
    out = []
    if (root / "R001" / "train" / "summary.json").exists():
        out.append(_r001_result(root / "R001" / "train", {"period": "train"}, "results/R001/train"))
    if (root / "O1" / "trials.csv").exists():
        out.append(_o1_result(root / "O1", {"trials": 400}, "results/O1"))
    if (root / "O2" / "trials.csv").exists():
        out.append(_o2_result(root / "O2", {}, "results/O2"))
    if (root / "O3" / "trials.csv").exists():
        out.append(_o3_result(root / "O3", {}, "results/O3"))
    if (root / "T1" / "summary.csv").exists():
        out.append(_t1_result(root / "T1", {}, "results/T1"))
    return out
