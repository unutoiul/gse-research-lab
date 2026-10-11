"""Study T1: the Golden Zone entry on 15m, 1H and 4H charts.

On 15m the spread costs about 0.2 R per trade (R001, O1-O3). If the entry has
an edge, it should show where costs are a smaller share of the risk. The same
code runs on every timeframe: the structure port on that chart's candles
(built from M15 with TradingView's session anchors), Golden Zone candidates
(GSE v4.0 defaults), RXM-1 execution with 16 candles of that timeframe as the
time limit. Train 2016-2018 and validation 2019-2022; the test period is untouched.

Strata use the two higher timeframes' bias on closed candles: 15m -> 4H and 1H,
1H -> 1D and 4H, 4H -> 1W and 1D. The weekly bias has no EMA during its first
50 weeks (warm-up from 2015-10), so 4H strata early in train lean on swings only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, data, experiments, metrics, signals, structure

TFS = ("15m", "1H", "4H")
HIGHER = {"15m": ("4H", "1H"), "1H": ("1D", "4H"), "4H": ("1W", "1D")}
COSTS = {"net": (1.0, 0.10), "half": (0.5, 0.05), "gross": (0.0, 0.0)}  # spread scale, slippage
PERIODS = {"train": ("2016-01-01", "2019-01-01"), "validate": ("2019-01-01", "2023-01-01")}
WARMUP, DATA_END = "2015-10-01", "2023-01-03"


def with_spread(frame: pd.DataFrame, scale: float) -> pd.DataFrame:
    """Bid/ask moved toward mid by `scale` (1 = as quoted, 0 = mid prices)."""
    out = frame.copy()
    for side in ("bid", "ask"):
        for k in ("open", "high", "low", "close"):
            out[f"{side}_{k}"] = frame[k] + scale * (frame[f"{side}_{k}"] - frame[k])
    return out


def higher_bias(frame: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Bias scores of the two higher timeframes, as each candle of `frame` sees them (closed candles)."""
    a, b = HIGHER[tf]
    cols = {}
    for name, htf_tf in (("h4", a), ("h1", b)):  # column names as signals.golden_zone_candidates expects
        htf = data.aggregate(frame, htf_tf)
        htf = htf.assign(score=structure.bias_scores(htf))
        cols[name] = data.align(frame, htf, ["score"], at="close")["score"].to_numpy(float)
    return pd.DataFrame(cols, index=frame.index)


def run_timeframe(m15: pd.DataFrame, tf: str) -> dict:
    frame = m15 if tf == "15m" else data.aggregate(m15, tf)
    out, _ = structure.run(frame)
    cands = signals.golden_zone_candidates(frame, out, higher_bias(frame, tf))
    result = {"candles": len(frame), "periods": {}}
    for period, (a, b) in PERIODS.items():
        lo, hi = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        c = cands[cands["time"].between(lo, hi, inclusive="left")].reset_index(drop=True)
        weeks = (hi - lo).days / 7
        per = {}
        for cost, (scale, slip) in COSTS.items():
            trades = backtest.simulate(with_spread(frame, scale), c, backtest.Execution(slippage=slip))
            per[cost] = {"summary": metrics.summarize(trades, weeks), "trades": trades}
        net = metrics.closed(per["net"]["trades"])
        per["risk_atr_median"] = float((net["risk"] / net["atr"]).median()) if len(net) else np.nan
        result["periods"][period] = per
    return result


def run_study(out_dir: Path | None = None, progress=None) -> Path:
    m15 = data.load("M15", start=WARMUP, end=DATA_END)
    results = {}
    for i, tf in enumerate(TFS):
        if progress:
            progress(i / len(TFS), f"{tf} chart")
        results[tf] = run_timeframe(m15, tf)
    out_dir = out_dir or data.ROOT / "results" / "T1"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, trades = [], []
    for tf, r in results.items():
        for period, per in r["periods"].items():
            row = {"timeframe": tf, "period": period, "risk_atr_median": per["risk_atr_median"]}
            for cost in COSTS:
                s = per[cost]["summary"]
                for k in ("trades", "trades_per_week", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R", "avg_spread_R"):
                    row[f"{cost}_{k}"] = s.get(k, np.nan)
            rows.append(row)
            trades.append(per["net"]["trades"].assign(timeframe=tf, period=period))
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "summary.csv", index=False)
    pd.concat(trades, ignore_index=True).to_csv(out_dir / "trades_net.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "status": experiments.PROVISIONAL}
    (out_dir / "report.md").write_text(_report(table, results, prov), encoding="utf-8")
    return out_dir


def _report(table: pd.DataFrame, results: dict, prov: dict) -> str:
    md, fmt = experiments._md, experiments._fmt
    show = table.set_index(["timeframe", "period"])[
        ["net_trades", "net_trades_per_week", "net_win_rate", "net_expectancy_R", "net_profit_factor", "net_max_drawdown_R",
         "net_avg_spread_R", "risk_atr_median", "half_expectancy_R", "gross_expectancy_R"]]
    show.index = [f"{tf} · {p}" for tf, p in show.index]
    lines = [
        "# T1 — The Golden Zone entry by chart timeframe (15m, 1H, 4H)", "",
        f"> {prov['status']}", "",
        "GSE v4.0 defaults on each chart's own candles; a candidate is the Golden Zone turning on at a close. Execution RXM-1 "
        "(next open at bid/ask, level-wick stop, first-obstacle target, 16 candles of that timeframe). Costs: **net** = OANDA "
        "bid/ask + 0.10 slippage; **half** = half spread + 0.05; **gross** = mid, no slippage. Train 2016–2018, validation "
        "2019–2022; test untouched.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset `{prov['dataset_sha256'][:12]}…`", "",
        "## Results", "",
        "`net_avg_spread_R` is the spread each trade pays, in R; `risk_atr_median` the stop distance in ATR of that timeframe.", "",
        md(show), "",
    ]
    for tf in TFS:
        net = results[tf]["periods"]["validate"]["net"]["trades"]
        if len(metrics.closed(net)):
            a, b = HIGHER[tf]
            g = metrics.by_group(net, "stratum")
            g.index.name = f"{a} & {b} bias vs trade"
            lines += [f"## {tf} validation (net) by higher-timeframe stratum ({a}, {b})", "", md(g), ""]
    val = table[table["period"] == "validate"].set_index("timeframe")
    trn = table[table["period"] == "train"].set_index("timeframe")
    positive = [tf for tf in TFS if val.at[tf, "net_expectancy_R"] > 0 and trn.at[tf, "net_expectancy_R"] > 0]
    gross_both = [tf for tf in TFS if val.at[tf, "gross_expectancy_R"] > 0 and trn.at[tf, "gross_expectancy_R"] > 0]
    small = [tf for tf in TFS if min(val.at[tf, "net_trades"], trn.at[tf, "net_trades"]) < 100]
    if positive:
        verdict = (f"Positive after costs in both periods on: {', '.join(positive)}. A candidate only: it needs the strata "
                   "checked, the parity gate and the locked test period (owner approval) before any conclusion.")
    elif gross_both:
        verdict = (f"Not profitable after costs on any timeframe, but positive before costs in both periods on: "
                   f"{', '.join(gross_both)}. The entry has some value there that costs remove.")
    else:
        verdict = "Not profitable on any timeframe, after or before costs: the higher timeframes do not rescue the entry."
    lines += ["## Conclusion", "", verdict, ""]
    if small:
        lines += [f"Fewer than 100 trades in a period on: {', '.join(small)}, so those results are weak evidence.", ""]
    lines += ["## Limitations", "",
              "- One entry rule (Golden Zone on), one execution model (RXM-1), GSE defaults: no setting was tuned here.",
              "- Higher-timeframe candles are built from OANDA M15 with TradingView's session anchors.",
              "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)
