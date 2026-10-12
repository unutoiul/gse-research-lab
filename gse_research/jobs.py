"""Jobs the website admin can launch, and how each becomes a stored result.

Every job kind validates its parameters here (the website validates the same
rules before queueing). The locked test period is never accepted: it stays a
command-line decision (`r001 --allow-test`).

A result ("run") is plain JSON:
- summary: headline numbers and the verdict (for lists),
- equity: cumulative R by exit time, one or more series,
- tables: generic tables (also shown by older admin pages),
- detail: the verdict and its reasons, diagnostics ("where it fails"),
  optimization data for searches, and the trade list,
- report_md and provenance (git commit, dataset SHA-256).
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics, optimize, quality, signals, strategy, strategy_study, timeframes

PERIODS = {"train": ("2016-01-01", "2019-01-01"), "validate": ("2019-01-01", "2023-01-01")}
WARMUP = "2015-10-01"
COSTS = {"net": strategy.Broker(slippage=0.10, spread_scale=1.0), "half": strategy.Broker(slippage=0.05, spread_scale=0.5),
         "gross": strategy.Broker(slippage=0.0, spread_scale=0.0)}
COST_LABELS = {"gross": "before costs (mid prices)", "half": "half spread + 0.05", "net": "OANDA spread + 0.10"}
MAX_TRADES_STORED = 1500

# kind -> ({param: rule}, defaults). Rules: tuple = allowed values, [min, max] = integer range,
# {"float": [min, max]} = number range.
SCHEMA = {
    "data_update": ({}, {}),
    "r001": ({"period": ("train", "validate")}, {"period": "train"}),
    "strategy_backtest": (
        {"swing_len": [3, 50], "h4_swing_len": [3, 50], "period": ("train", "validate"), "costs": tuple(COSTS),
         "path": ("conservative", "tradingview"), "stop_buffer_atr": {"float": [0.05, 3.0]},
         "min_r": {"float": [0.5, 5.0]}, "max_atr": {"float": [1.0, 20.0]}},
        {"swing_len": 10, "h4_swing_len": 10, "period": "train", "costs": "net", "path": "conservative",
         "stop_buffer_atr": strategy.STOP_BUFFER_ATR, "min_r": strategy.MIN_R, "max_atr": strategy.MAX_ATR}),
    "search_o1": ({"trials": [20, 400]}, {"trials": 400}),
    "search_o2": ({}, {}),
    "search_o3": ({}, {}),
    "study_t1": ({}, {}),
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
        if isinstance(rule, dict):
            lo, hi = rule["float"]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not lo <= value <= hi:
                raise ValueError(f"{key} must be a number from {lo} to {hi}")
            out[key] = float(value)
        elif isinstance(rule, list):
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


def session_of(times: pd.Series) -> pd.Series:
    """indicator.pine session codes for candle open times."""
    def hour(tz):
        lt = times.dt.tz_convert(tz)
        return lt.dt.hour + lt.dt.minute / 60.0
    tokyo, london, ny = hour("Asia/Tokyo"), hour("Europe/London"), hour("America/New_York")
    return signals.session_code((tokyo >= 9) & (tokyo < 17), (london >= 8) & (london < 17), (ny >= 8) & (ny < 17))


# ── Diagnostics: where a system fails ───────────────────────────────────

def diagnose(trades: pd.DataFrame, cost_levels: dict[str, float] | None = None, funnel: pd.DataFrame | None = None,
             group_cols: tuple[str, ...] = ("session", "direction", "year"), first_is_gross: bool = False) -> dict:
    """Cost attribution, exits, breakdowns, how far losers ran first, and plain-language findings.

    cost_levels runs from the cheapest level to the dearest; first_is_gross says the first one is
    cost-free (mid prices), so a loss there is the signal's, not the costs'.
    """
    t = metrics.closed(trades).copy()
    out: dict = {"notes": []}
    notes = out["notes"]
    if cost_levels:
        out["costs"] = [{"level": k, "expectancy_R": v} for k, v in cost_levels.items()]
        values = [v for v in cost_levels.values() if v is not None and not np.isnan(v)]
        if len(values) >= 2:
            first, last = list(cost_levels.items())[0], list(cost_levels.items())[-1]
            notes.append(f"Costs take {first[1] - last[1]:.2f} R per trade: {first[1]:+.2f} R {first[0]}, "
                         f"{last[1]:+.2f} R {last[0]}.")
            if first_is_gross and not first[1] > 0:
                notes.append("Even before costs the trades lose on average: the entry signal itself shows no edge here.")
    if funnel is not None and len(funnel):
        out["funnel"] = table(funnel, index=False)
    if t.empty:
        notes.append("No closed trades.")
        return clean(out)
    n = len(t)
    exits = t.groupby("reason")["R"].agg(trades="size", avg_R="mean").sort_values("trades", ascending=False)
    exits["share"] = exits["trades"] / n
    out["exits"] = table(exits)
    share = lambda keys: float(t["reason"].isin(keys).mean())
    notes.append(f"{share(['stop', 'stop_gap', 'stop_and_target']):.0%} of trades end at the stop, "
                 f"{share(['target', 'target_gap']):.0%} at the target, {share(['time', 'range_end']):.0%} on time.")
    losers = t[t["R"] <= 0]
    if len(losers):
        buckets = pd.cut(losers["mfe_R"].clip(lower=0), [-0.001, 0.5, 1.0, 2.0, np.inf], labels=["0-0.5R", "0.5-1R", "1-2R", "2R+"])
        mfe = buckets.value_counts().reindex(["0-0.5R", "0.5-1R", "1-2R", "2R+"]).fillna(0).astype(int).rename("losers").to_frame()
        mfe["share"] = mfe["losers"] / len(losers)
        mfe.index.name = "best profit before losing"
        out["loser_mfe"] = table(mfe)
        ran = float((losers["mfe_R"] >= 1.0).mean())
        if ran >= 0.2:
            notes.append(f"{ran:.0%} of losing trades were at least +1R in profit before they lost: exits give that back.")
        else:
            notes.append(f"Only {ran:.0%} of losing trades ever reached +1R: most losers go against the entry from the start.")
    breakdowns = {}
    for col in group_cols:
        if col in t and t[col].notna().any():
            g = metrics.by_group(t, col)
            g.index.name = col
            breakdowns[f"By {col}"] = table(g)
            big = g[g["trades"] >= 20]
            if len(big) >= 2:
                worst, best = big["expectancy_R"].idxmin(), big["expectancy_R"].idxmax()
                notes.append(f"By {col}: weakest {worst} ({big.at[worst, 'expectancy_R']:+.2f} R on {int(big.at[worst, 'trades'])} trades), "
                             f"strongest {best} ({big.at[best, 'expectancy_R']:+.2f} R on {int(big.at[best, 'trades'])}).")
    out["breakdowns"] = breakdowns
    return clean(out)


def trade_table(trades: pd.DataFrame, cols: list[str]) -> dict:
    t = metrics.closed(trades).sort_values("entry_time").tail(MAX_TRADES_STORED)
    return table(t[[c for c in cols if c in t]], index=False)


def _headline(summary: dict) -> dict:
    keys = ("trades", "trades_per_week", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R", "sqn",
            "max_consecutive_losses", "R_per_year", "avg_win_R", "avg_loss_R", "recovery_factor")
    return {k: summary.get(k) for k in keys if k in summary}


# ── Optimization: which parameters matter, and does training predict validation ──

def optimization(trials: pd.DataFrame, params: list[str], train: str, val: str, train_n: str, val_n: str,
                 default_mask: pd.Series, selected: dict | None, heatmaps: list[tuple], min_train: int) -> dict:
    t = trials.copy()
    for p in params:
        if t[p].dtype == bool:
            t[p] = t[p].astype(int)
    eligible = t[t[train_n] >= min_train]
    rho = eligible[[train, val]].corr(method="spearman").iloc[0, 1] if len(eligible) > 2 else np.nan
    importance = []
    for p in params:
        if t[p].nunique() > 1:
            importance.append({"param": p, "spearman_train": t[[p, train]].corr(method="spearman").iloc[0, 1],
                               "spearman_val": t[[p, val]].corr(method="spearman").iloc[0, 1]})
    importance.sort(key=lambda r: -abs(r["spearman_val"] if r["spearman_val"] == r["spearman_val"] else 0))
    marginals = {}
    for p in params:
        if t[p].nunique() > 1:
            m = t.groupby(p).agg(configs=(val, "size"), mean_train=(train, "mean"), mean_val=(val, "mean"), best_val=(val, "max"))
            marginals[p] = table(m)
    maps = []
    for x, y, metric, title, mask in heatmaps:
        sub = t if mask is None else t[mask]
        piv = sub.pivot_table(index=y, columns=x, values=metric, aggfunc="mean")
        maps.append({"title": title, "x": x, "y": y, "metric": metric, "xs": [clean(v) for v in piv.columns],
                     "ys": [clean(v) for v in piv.index], "z": clean(piv.round(4).to_numpy().tolist())})
    cols = [*params, train_n, train, val_n, val]
    ranked = t.sort_values(train, ascending=False)[[c for c in cols if c in t]].head(500)
    return clean({
        "params": params, "objective": {"train": train, "validation": val},
        "overfit": {"spearman_train_val": rho, "configs": len(t), "eligible": len(eligible),
                    "positive_train": int((eligible[train] > 0).sum()), "positive_val": int((eligible[val] > 0).sum()),
                    "positive_both": int(((eligible[train] > 0) & (eligible[val] > 0)).sum())},
        "importance": importance, "marginals": marginals, "heatmaps": maps,
        "default": t[default_mask][cols].to_dict("records")[0] if default_mask.any() else None,
        "selected": selected, "trials": table(ranked, index=False),
    })


def search_verdict(selected: dict | None, rho: float, val: str, val_n: str, val_pf: str | None) -> dict:
    if selected is None:
        return {"status": "inconclusive", "label": "Inconclusive", "reasons": ["no configuration had enough trades"]}
    v = metrics.verdict({"trades": selected.get(val_n, 0), "expectancy_R": selected.get(val, np.nan),
                         "profit_factor": selected.get(val_pf, np.nan) if val_pf else np.nan}, None, False)
    if rho == rho and rho < 0.3:
        v["reasons"].append(f"training rank does not predict validation (Spearman {rho:+.2f}): tuning fits noise")
        if v["status"] == "candidate":
            v.update(status="watch", label="Watch")
    return v


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


STRATEGY_TRADE_COLS = ["signal_time", "fill_time", "side", "entry", "fill", "stop", "tp2", "exit_time", "exit", "reason",
                       "R", "mfe_R", "mae_R", "session"]


def run_strategy_backtest(params: dict, work: Path, progress) -> tuple[dict, None]:
    a, b = PERIODS[params["period"]]
    progress(0.05, "loading candles")
    m15 = data.load("M15", start=WARMUP, end=str((pd.Timestamp(b) + pd.Timedelta(days=2)).date()))
    progress(0.15, "levels, 1H/4H snapshots and signals")
    p = strategy.StrategyParams(swing_len=params["swing_len"], h4_swing_len=params["h4_swing_len"],
                                stop_buffer_atr=params["stop_buffer_atr"], min_r=params["min_r"], max_atr=params["max_atr"])
    sig = strategy.signals(m15, p)
    progress(0.85, "simulating orders at three cost levels")
    weeks = (pd.Timestamp(b) - pd.Timestamp(a)).days / 7
    runs = {}
    for cost, base in COSTS.items():
        trades, counts = strategy.simulate(m15, sig, a, b, strategy.Broker(path=params["path"], slippage=base.slippage,
                                                                            spread_scale=base.spread_scale))
        if len(trades):
            trades["session"] = session_of(trades["fill_time"])
            trades["direction"] = trades["side"].map({1: "long", -1: "short"})
            trades["year"] = trades["entry_time"].dt.year
        runs[cost] = (trades, counts)
    trades, counts = runs[params["costs"]]
    summary = metrics.summarize(trades, weeks)
    ci = metrics.bootstrap_mean(trades)
    v = metrics.verdict(summary, ci["low"], in_sample=params["period"] == "train")
    in_period = m15["close_time"].between(pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC"), inclusive="left")
    reasons = sig.loc[in_period, "reason"].value_counts().rename("candles").to_frame()
    reasons["share"] = reasons["candles"] / reasons["candles"].sum()
    reasons.index.name = "candle state"
    costs = {COST_LABELS[c]: metrics.summarize(runs[c][0]).get("expectancy_R", np.nan) for c in ("gross", "half", "net")}
    detail = {"verdict": v, "ci": ci, "orders": counts,
              "diagnostics": diagnose(trades, costs, reasons.reset_index(), first_is_gross=True),
              "trades": trade_table(trades, STRATEGY_TRADE_COLS)}
    title = (f"Strategy v4.0 · chart {p.swing_len} / H4 {p.h4_swing_len} · stop +{p.stop_buffer_atr:g} ATR, "
             f"≥{p.min_r:g}R, ≤{p.max_atr:g} ATR · {params['period']} · {params['costs']}")
    report = "\n".join([f"# {title}", "", f"> {experiments.PROVISIONAL}", "",
                        f"**{v['label']}**: " + "; ".join(v["reasons"]) + ".", "",
                        *[f"- {n}" for n in detail["diagnostics"]["notes"]], ""])
    return {"kind": "strategy_backtest", "title": title, "params": params,
            "summary": clean({**_headline(summary), "verdict": v["status"]}),
            "equity": {"series": {c: equity(runs[c][0]) for c in ("net", "half", "gross")}},
            "tables": {}, "detail": clean(detail), "report_md": report, "provenance": _provenance()}, None


RXM_TRADE_COLS = ["time", "entry_time", "side", "entry", "stop", "target", "exit_time", "exit", "reason", "R", "mfe_R", "mae_R",
                  "session", "stratum"]


def run_r001(params: dict, work: Path, progress) -> tuple[dict, None]:
    progress(0.1, f"R001 on {params['period']}")
    out = experiments.run_r001(params["period"], out_dir=work)
    return _r001_result(out, params), None


def _r001_result(out: Path, params: dict, source: str | None = None) -> dict:
    summary = json.loads((out / "summary.json").read_text())
    trades = pd.read_csv(out / "trades.csv", parse_dates=["time", "entry_time", "exit_time"])
    trades["direction"] = trades["side"].map({1: "long", -1: "short"})
    trades["year"] = trades["entry_time"].dt.year
    head = 0.10
    arm = lambda a, s: trades[(trades["arm"] == a) & (trades["slippage"] == s)]
    c0, v1 = arm("C0", head), arm("V1", head)
    in_sample = params["period"] == "train"
    s0 = metrics.summarize(c0, float(summary["provenance"]["weeks"]))
    ci = metrics.bootstrap_mean(c0)
    v = metrics.verdict(s0, ci["low"], in_sample)
    s1 = summary["results"].get(f"V1@{head:.2f}", {})
    funnel = pd.read_csv(out / "funnel.csv") if (out / "funnel.csv").exists() else None
    costs = {f"spread + {s:.2f} slippage": metrics.summarize(arm("C0", s)).get("expectancy_R") for s in (0.0, 0.10, 0.30)}
    results = pd.DataFrame(summary["results"]).T
    results.index.name = "arm@slippage"
    keep = [c for c in ("trades", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R", "avg_spread_R") if c in results]
    detail = {"verdict": v, "ci": ci, "arms": {"V1_trades": s1.get("trades"), "V1_expectancy_R": s1.get("expectancy_R"),
                                                "V1_minus_C0": summary["bootstrap_V1_minus_C0"]},
              "diagnostics": diagnose(c0, costs, funnel, ("session", "direction", "year", "stratum")),
              "trades": trade_table(c0, RXM_TRADE_COLS)}
    return {"kind": "r001", "title": f"R001 · Require Sweep off vs on · {params['period']}", "params": params,
            "summary": clean({**_headline(s0), "verdict": v["status"], "V1_trades": s1.get("trades")}),
            "equity": {"series": {"C0": equity(c0), "V1": equity(v1)}},
            "tables": {"Results by arm and slippage": table(results[keep])}, "detail": clean(detail),
            "report_md": (out / "report.md").read_text(encoding="utf-8"),
            "provenance": clean({**summary["provenance"], **({"source": source} if source else {})})}


def run_search_o1(params: dict, work: Path, progress) -> tuple[dict, None]:
    out = optimize.run_study(params["trials"], out_dir=work, progress=progress)
    return _o1_result(out, params), None


def _o1_result(out: Path, params: dict, source: str | None = None) -> dict:
    trials = pd.read_csv(out / "trials.csv")
    chosen = json.loads((out / "chosen.json").read_text())
    names = list(optimize.SPACE)
    eligible = trials[trials["train_trades"] >= optimize.MIN_TRAIN_TRADES]
    top = eligible.sort_values("train_expectancy_R", ascending=False).head(20)
    pool = top[top["val_trades"] >= optimize.MIN_VAL_TRADES]
    sel = pool.sort_values("val_expectancy_R", ascending=False).iloc[0].to_dict() if len(pool) else None
    imp = {p: abs(trials[[p, "val_expectancy_R"]].astype(float).corr(method="spearman").iloc[0, 1]) for p in names if trials[p].nunique() > 1}
    x, y = sorted(imp, key=lambda k: -(imp[k] if imp[k] == imp[k] else 0))[:2]
    opt = optimization(trials, names, "train_expectancy_R", "val_expectancy_R", "train_trades", "val_trades",
                       trials["trial"] == 0, clean(sel), [(x, y, "val_expectancy_R", "Validation expectancy, mean over the other inputs", None)],
                       optimize.MIN_TRAIN_TRADES)
    v = search_verdict(sel, opt["overfit"]["spearman_train_val"], "val_expectancy_R", "val_trades", "val_profit_factor")
    return {"kind": "search_o1", "title": f"O1 · Golden Zone settings search · {len(trials)} configurations", "params": params,
            "summary": clean({"configurations": len(trials), "eligible": len(eligible),
                              "positive_on_validation": int((eligible["val_expectancy_R"] > 0).sum()),
                              "best_validation_expectancy_R": eligible["val_expectancy_R"].max() if len(eligible) else None,
                              "train_val_spearman": opt["overfit"]["spearman_train_val"], "verdict": v["status"]}),
            "equity": None, "tables": {"Top 20 on train, with validation": table(top, index=False)},
            "detail": clean({"verdict": v, "optimization": opt}),
            "report_md": (out / "report.md").read_text(encoding="utf-8"),
            "provenance": clean({**chosen["provenance"], **({"source": source} if source else {})})}


def run_search_o2(params: dict, work: Path, progress) -> tuple[dict, None]:
    out = strategy_study.run_study(out_dir=work, progress=progress)
    return _o2_result(out, params), None


def _strategy_search_selection(trials: pd.DataFrame, top_n: int) -> dict | None:
    eligible = trials[trials["train_net_trades"] >= strategy_study.MIN_TRAIN_TRADES]
    top = eligible.sort_values("train_net_expectancy_R", ascending=False).head(top_n)
    pool = top[top["val_net_trades"] >= strategy_study.MIN_VAL_TRADES]
    return pool.sort_values("val_net_expectancy_R", ascending=False).iloc[0].to_dict() if len(pool) else None


def _o2_result(out: Path, params: dict, source: str | None = None) -> dict:
    trials = pd.read_csv(out / "trials.csv")
    sel = _strategy_search_selection(trials, 10)
    names = ["swing_len", "h4_swing_len"]
    maps = [("h4_swing_len", "swing_len", m, t, None) for m, t in (
        ("val_net_expectancy_R", "Validation expectancy after costs"), ("val_gross_expectancy_R", "Validation expectancy before costs"),
        ("train_net_expectancy_R", "Training expectancy after costs"))]
    opt = optimization(trials, names, "train_net_expectancy_R", "val_net_expectancy_R", "train_net_trades", "val_net_trades",
                       (trials["swing_len"] == 10) & (trials["h4_swing_len"] == 10), clean(sel), maps, strategy_study.MIN_TRAIN_TRADES)
    v = search_verdict(sel, opt["overfit"]["spearman_train_val"], "val_net_expectancy_R", "val_net_trades", "val_net_profit_factor")
    top = trials.sort_values("train_net_expectancy_R", ascending=False).head(10)
    return {"kind": "search_o2", "title": f"O2 · Strategy v4.0 lookback grid · {len(trials)} settings", "params": params,
            "summary": clean({"settings": len(trials), "positive_val_net": int((trials["val_net_expectancy_R"] > 0).sum()),
                              "positive_val_gross": int((trials["val_gross_expectancy_R"] > 0).sum()),
                              "best_val_net_expectancy_R": trials["val_net_expectancy_R"].max(), "verdict": v["status"]}),
            "equity": None, "tables": {"Top 10 on train (net), with validation": table(top, index=False)},
            "detail": clean({"verdict": v, "optimization": opt}),
            "report_md": (out / "report.md").read_text(encoding="utf-8"), "provenance": _provenance({"source": source} if source else None)}


def run_search_o3(params: dict, work: Path, progress) -> tuple[dict, None]:
    out = strategy_study.run_targets_study(out_dir=work, progress=progress)
    return _o3_result(out, params), None


def _o3_result(out: Path, params: dict, source: str | None = None) -> dict:
    trials = pd.read_csv(out / "trials.csv")
    sel = _strategy_search_selection(trials, 5)
    names = ["stop_buffer_atr", "min_r", "max_atr"]
    maps = [("min_r", "stop_buffer_atr", m, f"{t}, max {mx:g} ATR", trials["max_atr"] == mx)
            for mx in sorted(trials["max_atr"].unique())
            for m, t in (("val_net_expectancy_R", "Validation after costs"), ("val_gross_expectancy_R", "Validation before costs"))]
    current = (trials["stop_buffer_atr"] == 0.2) & (trials["min_r"] == 1.5) & (trials["max_atr"] == 8.0)
    opt = optimization(trials, names, "train_net_expectancy_R", "val_net_expectancy_R", "train_net_trades", "val_net_trades",
                       current, clean(sel), maps, strategy_study.MIN_TRAIN_TRADES)
    v = search_verdict(sel, opt["overfit"]["spearman_train_val"], "val_net_expectancy_R", "val_net_trades", "val_net_profit_factor")
    both_gross = int(((trials["train_gross_expectancy_R"] > 0) & (trials["val_gross_expectancy_R"] > 0)).sum())
    return {"kind": "search_o3", "title": f"O3 · Strategy v4.0 stop and target rules · {len(trials)} settings", "params": params,
            "summary": clean({"settings": len(trials), "positive_val_net": int((trials["val_net_expectancy_R"] > 0).sum()),
                              "positive_val_half": int((trials["val_half_expectancy_R"] > 0).sum()),
                              "positive_gross_both_periods": both_gross,
                              "best_val_net_expectancy_R": trials["val_net_expectancy_R"].max(), "verdict": v["status"]}),
            "equity": None, "tables": {}, "detail": clean({"verdict": v, "optimization": opt}),
            "report_md": (out / "report.md").read_text(encoding="utf-8"), "provenance": _provenance({"source": source} if source else None)}


def run_study_t1(params: dict, work: Path, progress) -> tuple[dict, None]:
    out = timeframes.run_study(out_dir=work, progress=progress)
    return _t1_result(out, params), None


def _t1_result(out: Path, params: dict, source: str | None = None) -> dict:
    summary = pd.read_csv(out / "summary.csv")
    trades = pd.read_csv(out / "trades_net.csv", parse_dates=["time", "entry_time", "exit_time"])
    trades["direction"] = trades["side"].map({1: "long", -1: "short"})
    trades["year"] = trades["entry_time"].dt.year
    tfs = ("15m", "1H", "4H")
    series = {f"{tf} {p}": equity(trades[(trades["timeframe"] == tf) & (trades["period"] == p)]) for tf in tfs for p in ("train", "validate")}
    verdicts, best = {}, None
    for tf in tfs:
        tv = trades[(trades["timeframe"] == tf) & (trades["period"] == "validate")]
        verdicts[tf] = metrics.verdict(metrics.summarize(tv), metrics.bootstrap_mean(tv)["low"], False)
    rank = {"candidate": 4, "watch": 3, "in_sample": 2, "inconclusive": 1, "rejected": 0}
    best_tf = max(tfs, key=lambda tf: rank[verdicts[tf]["status"]])
    v = dict(verdicts[best_tf])
    v["reasons"] = [f"{tf}: {verdicts[tf]['label']} — " + "; ".join(verdicts[tf]["reasons"]) for tf in tfs]
    val = summary[summary["period"] == "validate"].set_index("timeframe")
    costs_tbl = val[["gross_expectancy_R", "half_expectancy_R", "net_expectancy_R", "net_avg_spread_R", "net_trades"]]
    tv15 = trades[(trades["timeframe"] == "15m") & (trades["period"] == "validate")]
    diag = diagnose(tv15, {COST_LABELS[c]: val.at["15m", f"{c}_expectancy_R"] for c in ("gross", "half", "net")}, None,
                    ("session", "direction", "year", "stratum"), first_is_gross=True)
    diag["notes"].insert(0, "Diagnostics below are for the 15m chart, validation period.")
    cols = ["timeframe", "period", "net_trades", "net_win_rate", "net_expectancy_R", "net_profit_factor", "net_max_drawdown_R",
            "net_avg_spread_R", "half_expectancy_R", "gross_expectancy_R"]
    return {"kind": "study_t1", "title": "T1 · Golden Zone entry on 15m, 1H and 4H", "params": params,
            "summary": clean({**{f"{tf}_validate_net_R": val.at[tf, "net_expectancy_R"] for tf in val.index},
                              **{f"{tf}_validate_trades": val.at[tf, "net_trades"] for tf in val.index}, "verdict": v["status"]}),
            "equity": {"series": series},
            "tables": {"Results by timeframe and period": table(summary[cols], index=False),
                       "Validation by timeframe and cost level": table(costs_tbl)},
            "detail": clean({"verdict": v, "diagnostics": diag, "trades": trade_table(tv15, RXM_TRADE_COLS)}),
            "report_md": (out / "report.md").read_text(encoding="utf-8"),
            "provenance": _provenance({"source": source} if source else None)}


RUNNERS = {"data_update": run_data_update, "r001": run_r001, "strategy_backtest": run_strategy_backtest,
           "search_o1": run_search_o1, "search_o2": run_search_o2, "search_o3": run_search_o3, "study_t1": run_study_t1}


def committed_results() -> list[dict]:
    """The results already in results/ as runs, for publishing to the admin."""
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
