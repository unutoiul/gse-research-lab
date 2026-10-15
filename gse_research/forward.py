"""Forward test F1: do flipped-level touches beat random levels on data no study has seen?

E1 found one hint: on 15m, first touches of confirmed flipped levels turned away from the level slightly
more often than random levels did (+2 to +6.5 points) in both 2016-2018 and 2019-2022, but within the
intervals. F1 measures exactly the same thing on candles after FORWARD_START, with the rule frozen in
results/F1/rule.json before any of those candles was looked at:
- primary: 15m, swing lookback 10 (GSE's default), flipped levels, GSE v4.1 levels;
- secondary (reported, not decided on): 15m lookbacks 3 and 5, 1H and 4H at lookback 10, and fresh
  levels for comparison.
Each touch is measured as in E1 (event_study): 1 ATR away from the level before 1 ATR through it, within
32 candles, against 3 random levels per touch on the same side and distance. Touches from the last 32
candles are pending until their outcome is known.

The verdict waits for MIN_TOUCHES resolved primary touches (about three years at E1's rate); until then
the report is a running tally, not evidence. Run it any time: `python -m gse_research forward-test`; the
`forward-test` GitHub workflow runs it every Monday on fresh OANDA data.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, event_study as es, experiments

FORWARD_START = "2026-10-13"
WARMUP_DAYS = 180       # levels, ATR and 4H swings settle before the first forward candle
CELLS = [("15m", 10), ("15m", 3), ("15m", 5), ("1H", 10), ("4H", 10)]
PRIMARY = ("15m", 10, "flipped")
MIN_TOUCHES = 400
LEVEL = 0.90            # two-sided interval for the difference (95% one-sided lower bound)
RULE = data.ROOT / "results" / "F1" / "rule.json"


def collect(m15: pd.DataFrame, start: str = FORWARD_START, end: str | None = None) -> pd.DataFrame:
    """Real and random touches with outcomes, for every cell, touched in [start, end)."""
    periods = {"forward": (start, end or "2100-01-01")}
    parts = []
    for tf, swing in CELLS:
        chart = m15 if tf == "15m" else data.aggregate(m15, tf)
        part = es.evaluate_cell((tf, swing), periods, chart)
        if len(part):
            parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def decide(row: pd.Series | None) -> tuple[str, str]:
    """The frozen decision for the primary cell (results/F1/rule.json)."""
    if row is None or not row["resolved"] >= MIN_TOUCHES:
        n = 0 if row is None else int(row["resolved"])
        return "running", f"{n} of {MIN_TOUCHES} resolved primary touches: a running tally, not evidence yet."
    if not row["win_diff_low"] > 0:
        return "no edge", ("Flipped-level touches do not beat random levels on unseen data (the interval of the "
                           "difference reaches zero).")
    if row["win_real"] < 0.5 + row["cost_atr"] / 2:
        return "edge, not tradeable", ("Flipped levels beat random levels, but a 1:1 trade with a 1 ATR stop would not "
                                       "cover one spread plus slippage.")
    return "edge", "Flipped levels beat random levels on unseen data by more than the costs of a 1:1 trade."


def run(out_dir: Path | None = None, end: str | None = None) -> Path:
    rule = json.loads(RULE.read_text(encoding="utf-8"))
    start = rule["forward_start"]
    warm = (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)).strftime("%Y-%m-%d")
    m15 = data.load("M15", start=warm, end=end)
    events = collect(m15, start, end)
    out_dir = out_dir or data.ROOT / "results" / "F1"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    if len(events):
        s = es.summarize(events, LEVEL)
        resolved = events[events["group"] == "real"].groupby(["chart_tf", "swing_len", "type"])["win"].count()
        s["resolved"] = [int(resolved.get((r.chart_tf, r.swing_len, r.type), 0)) for r in s.itertuples()]
        s["pending"] = s["touches"] - s["resolved"]
        rows = s
        events.to_csv(out_dir / "events.csv", index=False)
    s = pd.DataFrame(rows)
    prim = None
    if len(s):
        hit = s[(s["chart_tf"] == PRIMARY[0]) & (s["swing_len"] == PRIMARY[1]) & (s["type"] == PRIMARY[2])]
        prim = hit.iloc[0] if len(hit) else None
    call, text = decide(prim)
    data_end = m15["close_time"].iloc[-1] if len(m15) else None
    summary = {"data_end": str(data_end), "forward_start": start, "verdict": call, "text": text,
               "primary": None if prim is None else {k: (v.item() if hasattr(v, "item") else v) for k, v in prim.items()},
               "git": experiments._git()}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(report(s, call, text, start, data_end, summary["git"]), encoding="utf-8")
    return out_dir


def report(s: pd.DataFrame, call: str, text: str, start: str, data_end, git: dict) -> str:
    md = experiments._md
    cols = ["chart_tf", "swing_len", "type", "touches", "resolved", "pending", "win_real", "win_random", "win_diff",
            "win_diff_low", "win_diff_high", "ret16_diff", "cost_atr"]
    lines = [
        "# F1 — Forward test: flipped-level touches against random levels", "",
        f"Candles from **{start}** to **{data_end}** (OANDA M15). Frozen rule: `results/F1/rule.json`. Primary: "
        f"{PRIMARY[0]}, lookback {PRIMARY[1]}, {PRIMARY[2]} levels; the verdict waits for {MIN_TOUCHES} resolved touches.", "",
        f"Git `{git['commit'][:10]}`{' (dirty)' if git['dirty'] else ''}", "",
        f"## Verdict: {call}", "", text, "",
        "## Running tally", "",
        "win = 1 ATR away from the level before 1 ATR through it, within 32 candles; random = 3 random levels per touch on "
        "the same side and distance. diff = real − random with a 90% weekly-block bootstrap interval. cost_atr = one "
        "spread plus slippage in ATR (median); a 1:1 trade with a 1 ATR stop breaks even at win = 0.5 + cost_atr / 2.", "",
        md(s[cols].set_index("chart_tf").round(3)) if len(s) else "No touches yet.", "",
        "## For comparison: E1 (2016–2022), 15m lookback 10 flipped", "",
        "Train: win 0.533 against 0.469 random (+0.065). Validation: 0.492 against 0.463 (+0.028).", ""]
    return "\n".join(lines)
