"""Forward test F2: paper trades of the best S5 settings on candles no study has seen.

Study S5 found no profitable setting on 2019-2022, but three came closest. F2 records how they trade from
FORWARD_START on, with every rule frozen in results/F2/rule.json before any of those candles was read:
- A_pullback, touch (resting limit at the level), stop 5 ATR, target 0.5 R;
- A_pullback, touch, stop 5 ATR, target 1 R (the variant S5's training data picked);
- B_flip, touch, stop 2 ATR, target 0.75 R (the variant S5's training data picked).
Everything else is S4/S5 (gse_research/setups.py): 1D + 4H GSE bias as the trend, GSE v4.1 levels,
OANDA bid/ask with 0.10 slippage, conservative intrabar order, one position at a time per setting.

A verdict waits for MIN_TRADES closed trades per setting (years at S5's rates); until then the report
is a running tally, not evidence. `python -m gse_research forward-setups`; the `forward-test` GitHub
workflow runs it every Monday after F1.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics
from . import setups as s4
from . import strategy as st

WARMUP_DAYS = 200      # the daily bias (EMA 50, 10-candle swings) and the 15m levels settle first
MIN_TRADES = 100
RULE = data.ROOT / "results" / "F2" / "rule.json"
OPEN_END = "2100-01-01"


def collect(history: pd.DataFrame, variants: list[tuple], start: str, end: str = OPEN_END) -> dict:
    """Paper trades per variant, entered from `start` on (net and gross costs), with open positions."""
    p = st.StrategyParams(swing_len=s4.SWING, flip_rules="4.1")
    h1, h4 = st.h1_inputs(history, p), st.h4_inputs(history, p)
    ctx = s4.context(history, history)
    cand, _ = s4.candidates(history, ctx, h1, h4)
    out = {}
    for v in variants:
        sig = s4.variant_signals(cand, len(history), *v)
        net, counts = st.simulate(history, sig, start, end, s4.COSTS["net"])
        gross, _ = st.simulate(history, sig, start, end, s4.COSTS["gross"])
        out[v] = {"net": net, "gross": gross, "open": counts.get("open_at_data_end", 0)}
    return out


def decide(n: int, s: dict, ci_low: float) -> tuple[str, str]:
    if n < MIN_TRADES:
        return "running", f"{n} of {MIN_TRADES} closed trades: a running tally, not evidence yet."
    if not s.get("expectancy_R", -1) > 0:
        return "fail", "Loses after costs on unseen data."
    if s.get("profit_factor", 0) >= 1.2 and ci_low > 0:
        return "pass", "Profitable after costs on unseen data, with a margin."
    return "weak", "Positive after costs, but short of profit factor 1.2 or an interval above zero."


def run(out_dir: Path | None = None, end: str | None = None) -> Path:
    rule = json.loads(RULE.read_text(encoding="utf-8"))
    start = rule["forward_start"]
    variants = [tuple(v) for v in rule["variants"]]
    warm = (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)).strftime("%Y-%m-%d")
    history = data.load("M15", start=warm, end=end)
    res = collect(history, variants, start)
    out_dir = out_dir or data.ROOT / "results" / "F2"
    out_dir.mkdir(parents=True, exist_ok=True)
    weeks = max((history["close_time"].iloc[-1] - pd.Timestamp(start, tz="UTC")).days / 7, 1 / 7)
    rows, logs = [], []
    for v, r in res.items():
        net, gross = r["net"], r["gross"]
        s = metrics.summarize(net, weeks)
        n = int(s["trades"])
        ci = metrics.bootstrap_mean(net)["low"] if n > 1 else np.nan
        call, _ = decide(n, s, ci)
        rows.append({"setup": v[0], "trigger": v[1], "stop": v[2], "target": v[3], "closed_trades": n, "open": r["open"],
                     "win_rate": s["win_rate"], "avg_R": s["expectancy_R"], "total_R": s["total_R"],
                     "profit_factor": s["profit_factor"], "max_drawdown_R": s["max_drawdown_R"],
                     "gross_avg_R": metrics.summarize(gross)["expectancy_R"], "ci_low": ci, "verdict": call})
        if len(net):
            logs.append(net.assign(variant=" / ".join(v))[["variant", "signal_time", "fill_time", "dir", "fill", "stop", "tp2",
                                                             "exit_time", "exit", "reason", "R"]])
    table = pd.DataFrame(rows)
    trades = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame()
    table.to_csv(out_dir / "summary.csv", index=False)
    trades.to_csv(out_dir / "trades.csv", index=False)
    git = experiments._git()
    data_end = history["close_time"].iloc[-1]
    (out_dir / "summary.json").write_text(json.dumps({"data_end": str(data_end), "forward_start": start, "git": git,
                                                       "rows": table.to_dict("records")}, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(report(table, trades, start, data_end, git), encoding="utf-8")
    return out_dir


def report(table: pd.DataFrame, trades: pd.DataFrame, start: str, data_end, git: dict) -> str:
    md = experiments._md
    lines = [
        "# F2 — Forward test: paper trades of the best S5 settings", "",
        f"Candles from **{start}** to **{data_end}** (OANDA M15). Frozen rules: `results/F2/rule.json`. Each setting "
        f"needs {MIN_TRADES} closed trades for a verdict (pass: profit after costs, profit factor ≥ 1.2, 90% interval above zero).", "",
        f"Git `{git['commit'][:10]}`{' (dirty)' if git['dirty'] else ''}", "",
        "## Running tally (after OANDA spread and 0.10 slippage)", "",
        md(table.set_index("setup").round(3)) if len(table) else "No setting yet.", "",
        "## Every paper trade", "",
        md(trades.round(3).set_index("variant")) if len(trades) else "No closed trade yet.", "",
        "## For comparison: S5 on 2019–2022 (validation)", "",
        "A_pullback touch 5 ATR 0.5 R: −0.040 R per trade (64% wins). A_pullback touch 5 ATR 1 R: −0.061 R (47%). "
        "B_flip touch 2 ATR 0.75 R: −0.088 R (53%).", ""]
    return "\n".join(lines)
