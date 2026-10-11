"""Study O2: GSE Strategy v4.0 settings (Chart and H4 swing lookback), searched on train, checked on validation.

A full grid over the strategy's two analytical TradingView inputs. Everything
else is the strategy as written (strategy-targets.pine constants). Each
setting is scored under three cost levels, so a poor result can be read as
"wrong settings" or "costs too high for this design":
- net:  OANDA bid/ask + 0.10 slippage on stop fills (the headline),
- half: half the spread + 0.05 slippage (roughly a raw-spread account),
- gross: mid prices, no slippage.
Intrabar order: conservative (adverse first). The test period is untouched.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics
from . import strategy as st

GRID = list(range(4, 21))
WARMUP, TRAIN, VALIDATE, DATA_END = "2015-10-01", ("2016-01-01", "2019-01-01"), ("2019-01-01", "2023-01-01"), "2023-01-03"
COSTS = {"net": st.Broker(slippage=0.10, spread_scale=1.0), "half": st.Broker(slippage=0.05, spread_scale=0.5),
         "gross": st.Broker(slippage=0.0, spread_scale=0.0)}
MIN_TRAIN_TRADES, MIN_VAL_TRADES = 150, 200
KEYS = ("trades", "trades_per_week", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R", "median_planned_rr")

_M15: pd.DataFrame | None = None


def _init() -> None:
    global _M15
    _M15 = data.load("M15", start=WARMUP, end=DATA_END)


@lru_cache(maxsize=2)
def _h1(swing_len: int):
    return st.h1_inputs(_M15, st.StrategyParams(swing_len=swing_len))


@lru_cache(maxsize=len(GRID))
def _h4(h4_len: int):
    return st.h4_inputs(_M15, st.StrategyParams(h4_swing_len=h4_len))


def evaluate(cfg: dict) -> dict:
    p = st.StrategyParams(**cfg)
    sig = st.signals(_M15, p, _h1(p.swing_len), _h4(p.h4_swing_len))
    row = dict(cfg)
    for period, (a, b) in (("train", TRAIN), ("val", VALIDATE)):
        weeks = (pd.Timestamp(b) - pd.Timestamp(a)).days / 7
        for cost, broker in COSTS.items():
            trades, counts = st.simulate(_M15, sig, a, b, broker)
            s = metrics.summarize(trades, weeks)
            for k in KEYS if cost == "net" else ("trades", "expectancy_R", "profit_factor"):
                row[f"{period}_{cost}_{k}"] = s.get(k, np.nan)
            if cost == "net":
                row[f"{period}_orders"] = counts["submitted"]
    return row


def _evaluate_all(configs: list[dict], workers: int | None, progress=None) -> pd.DataFrame:
    workers = workers or max(1, min(16, (os.cpu_count() or 2) - 2))
    configs = sorted(configs, key=lambda c: c["swing_len"])
    rows = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as pool:
        for row in pool.map(evaluate, configs, chunksize=2):  # small chunks: no worker is left with a long tail
            rows.append(row)
            if progress and len(rows) % 5 == 0:
                progress(len(rows) / len(configs), f"{len(rows)} / {len(configs)} settings")
    return pd.DataFrame(rows)


def run_study(workers: int | None = None, extra: list[dict] | None = None, name: str = "O2",
              out_dir: Path | None = None, progress=None) -> Path:
    configs = extra or [{"swing_len": a, "h4_swing_len": b} for a in GRID for b in GRID]
    df = _evaluate_all(configs, workers, progress)
    out_dir = out_dir or data.ROOT / "results" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "trials.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "grid": GRID, "costs": {k: vars(v) for k, v in COSTS.items()},
            "min_train_trades": MIN_TRAIN_TRADES, "min_val_trades": MIN_VAL_TRADES, "status": experiments.PROVISIONAL}
    (out_dir / "report.md").write_text(_report(df, prov), encoding="utf-8")
    return out_dir


def _pivot(df: pd.DataFrame, col: str) -> pd.DataFrame:
    t = df.pivot(index="swing_len", columns="h4_swing_len", values=col).round(2)
    t.index.name = "chart \\ H4"
    return t


def _report(df: pd.DataFrame, prov: dict) -> str:
    md, fmt = experiments._md, experiments._fmt
    eligible = df[(df["train_net_trades"] >= MIN_TRAIN_TRADES)]
    top = eligible.sort_values("train_net_expectancy_R", ascending=False).head(10)
    pool = top[top["val_net_trades"] >= MIN_VAL_TRADES]
    chosen = pool.sort_values("val_net_expectancy_R", ascending=False).iloc[0] if len(pool) else None
    rho = eligible[["train_net_expectancy_R", "val_net_expectancy_R"]].corr(method="spearman").iloc[0, 1] if len(eligible) > 2 else np.nan
    default = df[(df["swing_len"] == 10) & (df["h4_swing_len"] == 10)]
    cols = ["swing_len", "h4_swing_len", "train_net_trades", "train_net_win_rate", "train_net_expectancy_R", "train_net_profit_factor",
            "train_net_max_drawdown_R", "train_gross_expectancy_R", "val_net_trades", "val_net_expectancy_R", "val_net_profit_factor",
            "val_net_max_drawdown_R", "val_half_expectancy_R", "val_gross_expectancy_R"]
    count = lambda c, p: int((eligible[c] > 0).sum())
    lines = [
        "# O2 — GSE Strategy v4.0 settings (fresh touch + H4 + website targets)", "",
        f"> {prov['status']}", "",
        f"Full grid: Chart swing lookback × H4 swing lookback, each {GRID[0]}–{GRID[-1]} ({len(df)} settings). Train 2016–2018, "
        "validation 2019–2022, test untouched. Fills: limit at the level when the ask (long) / bid (short) reaches it; "
        "stop and TP2 frozen at submission; conservative intrabar order. Costs: **net** = OANDA bid/ask + 0.10 slippage on stops "
        "(headline); **half** = half spread + 0.05; **gross** = mid, no slippage.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset `{prov['dataset_sha256'][:12]}…`", "",
        "## Summary", "",
        f"- Settings with ≥ {MIN_TRAIN_TRADES} training trades: {len(eligible)} of {len(df)}.",
        f"- Positive expectancy, net: train {count('train_net_expectancy_R', 0)}, validation {count('val_net_expectancy_R', 0)}, "
        f"both {int(((eligible['train_net_expectancy_R'] > 0) & (eligible['val_net_expectancy_R'] > 0)).sum())}.",
        f"- Positive, half spread: validation {count('val_half_expectancy_R', 0)}. Positive, gross: train {count('train_gross_expectancy_R', 0)}, "
        f"validation {count('val_gross_expectancy_R', 0)}, both {int(((eligible['train_gross_expectancy_R'] > 0) & (eligible['val_gross_expectancy_R'] > 0)).sum())}.",
        f"- Rank correlation of train and validation net expectancy: {fmt(rho)}.", "",
        "## Defaults (10 / 10)", "", md(default[cols].set_index("swing_len")), "",
        "## Top 10 on train (net), with validation", "", md(top[cols].set_index("swing_len")), "",
    ]
    if chosen is not None:
        lines += [f"**Selected** (best validation net expectancy among the top 10 on train): Chart swing lookback **{int(chosen['swing_len'])}**, "
                  f"H4 swing lookback **{int(chosen['h4_swing_len'])}**. Train net {fmt(chosen['train_net_expectancy_R'])} R on "
                  f"{int(chosen['train_net_trades'])} trades; validation net {fmt(chosen['val_net_expectancy_R'])} R on {int(chosen['val_net_trades'])} trades "
                  f"(half spread {fmt(chosen['val_half_expectancy_R'])} R, gross {fmt(chosen['val_gross_expectancy_R'])} R). "
                  "Its validation figure is optimistic: validation picked it from 10.", ""]
    for title, col in (("Validation net expectancy (R)", "val_net_expectancy_R"), ("Validation gross expectancy (R)", "val_gross_expectancy_R"),
                       ("Train net expectancy (R)", "train_net_expectancy_R"), ("Validation trades", "val_net_trades")):
        lines += [f"## {title}: rows chart lookback, columns H4 lookback", "", md(_pivot(df, col)), ""]
    best_val = eligible["val_net_expectancy_R"].max() if len(eligible) else np.nan
    best_half = eligible["val_half_expectancy_R"].max() if len(eligible) else np.nan
    verdict = (f"**No setting is profitable on validation after OANDA costs** (best {fmt(best_val)} R; best with half the spread {fmt(best_half)} R). "
               "The two inputs do not fix the strategy under realistic costs, so no setting is recommended."
               if not best_val > 0 else
               "Some settings are positive on validation after costs. The selected one is a candidate only: it must pass the locked test "
               "period (owner approval) and the parity gate before any use.")
    lines += ["## Conclusion", "", verdict, "",
              "## Limitations", "",
              f"- {len(df)} settings were tried; the best training result is optimistic by construction.",
              "- OANDA spreads may be wider than the broker the strategy is traded with; the half-spread column shows the sensitivity.",
              "- The stop buffer (0.2 ATR), minimum 1.5R and maximum 8 ATR are fixed strategy constants and were not searched.",
              "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)


# ── Study O3: the stop and target constants (strategy-targets.pine, website target engine) ──
# Not TradingView inputs: adopting a result means changing the Pine strategy and the
# website's target engine together. Lookbacks stay at the defaults (10 / 10), so only
# these rules change.
STOP_BUFFERS = [0.20, 0.35, 0.50, 0.75, 1.00]
MIN_RS = [1.0, 1.5, 2.0]
MAX_ATRS = [4.0, 8.0]
CURRENT = {"stop_buffer_atr": 0.20, "min_r": 1.5, "max_atr": 8.0}


def run_targets_study(workers: int | None = None, out_dir: Path | None = None, progress=None) -> Path:
    configs = [{"swing_len": 10, "h4_swing_len": 10, "stop_buffer_atr": b, "min_r": r, "max_atr": m}
               for b in STOP_BUFFERS for r in MIN_RS for m in MAX_ATRS]
    df = _evaluate_all(configs, workers, progress)
    out_dir = out_dir or data.ROOT / "results" / "O3"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "trials.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "status": experiments.PROVISIONAL,
            "stop_buffers": STOP_BUFFERS, "min_rs": MIN_RS, "max_atrs": MAX_ATRS}
    (out_dir / "report.md").write_text(_targets_report(df, prov), encoding="utf-8")
    return out_dir


def _targets_report(df: pd.DataFrame, prov: dict) -> str:
    md, fmt = experiments._md, experiments._fmt
    key = ["stop_buffer_atr", "min_r", "max_atr"]
    eligible = df[df["train_net_trades"] >= MIN_TRAIN_TRADES]
    top = eligible.sort_values("train_net_expectancy_R", ascending=False).head(5)
    pool = top[top["val_net_trades"] >= MIN_VAL_TRADES]
    chosen = pool.sort_values("val_net_expectancy_R", ascending=False).iloc[0] if len(pool) else None
    is_current = np.logical_and.reduce([df[k] == v for k, v in CURRENT.items()])
    cols = [*key, "train_net_trades", "train_net_win_rate", "train_net_expectancy_R", "train_gross_expectancy_R",
            "val_net_trades", "val_net_win_rate", "val_net_expectancy_R", "val_net_profit_factor", "val_net_max_drawdown_R",
            "val_half_expectancy_R", "val_gross_expectancy_R", "val_net_median_planned_rr"]

    def pos(col: str) -> int:
        return int((eligible[col] > 0).sum())

    def both(cost: str) -> int:
        return int(((eligible[f"train_{cost}_expectancy_R"] > 0) & (eligible[f"val_{cost}_expectancy_R"] > 0)).sum())

    def pivot(col: str, m: float) -> pd.DataFrame:
        t = df[df["max_atr"] == m].pivot(index="stop_buffer_atr", columns="min_r", values=col).round(3)
        t.index.name = "stop buffer \\ min R"
        return t

    lines = [
        "# O3 — GSE Strategy v4.0 stop and target rules", "",
        f"> {prov['status']}", "",
        "The strategy's constants, not TradingView inputs: the stop buffer beyond the level wick (ATR), the target's minimum "
        "reward (R) and maximum distance (ATR). Lookbacks fixed at 10 / 10. Train 2016–2018, validation 2019–2022, test "
        "untouched. Costs: **net** = OANDA bid/ask + 0.10 slippage on stops; **half** = half spread + 0.05; **gross** = mid, "
        "no slippage. Conservative intrabar order.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset `{prov['dataset_sha256'][:12]}…`", "",
        "## Summary", "",
        f"- Settings with ≥ {MIN_TRAIN_TRADES} training trades: {len(eligible)} of {len(df)}.",
        f"- Positive, net: train {pos('train_net_expectancy_R')}, validation {pos('val_net_expectancy_R')}, both {both('net')}.",
        f"- Positive, half spread: train {pos('train_half_expectancy_R')}, validation {pos('val_half_expectancy_R')}, both {both('half')}.",
        f"- Positive, gross: train {pos('train_gross_expectancy_R')}, validation {pos('val_gross_expectancy_R')}, both {both('gross')}.", "",
        "## Current constants (0.20 / 1.5 / 8)", "", md(df[is_current][cols].set_index("stop_buffer_atr")), "",
        "## All settings, best training result first", "",
        md(eligible.sort_values("train_net_expectancy_R", ascending=False)[cols].set_index("stop_buffer_atr")), "",
    ]
    if chosen is not None:
        lines += [f"**Selected** (best validation net among the top 5 on train): stop buffer **{chosen['stop_buffer_atr']} ATR**, "
                  f"min **{chosen['min_r']} R**, max **{chosen['max_atr']} ATR**. Validation net {fmt(chosen['val_net_expectancy_R'])} R "
                  f"on {int(chosen['val_net_trades'])} trades (half spread {fmt(chosen['val_half_expectancy_R'])} R, gross "
                  f"{fmt(chosen['val_gross_expectancy_R'])} R). Optimistic: validation picked it from 5.", ""]
    for m in MAX_ATRS:
        lines += [f"## Validation net expectancy (R), max {m:g} ATR: rows stop buffer, columns min R", "",
                  md(pivot("val_net_expectancy_R", m)), "",
                  f"## Validation gross expectancy (R), max {m:g} ATR", "", md(pivot("val_gross_expectancy_R", m)), ""]
    best_net = eligible["val_net_expectancy_R"].max() if len(eligible) else np.nan
    if best_net > 0:
        verdict = ("Some settings are positive on validation after costs. The selected one is a candidate only: it needs the "
                   "locked test period (owner approval) and the parity gate before any change to the strategy or the website.")
    elif both("gross"):
        verdict = (f"**No stop/target setting is profitable on validation after OANDA costs** (best {fmt(best_net)} R). Some are "
                   "positive gross in both periods: the signal has some value that costs remove, so execution cost is the "
                   "question, not these constants.")
    else:
        verdict = (f"**No stop/target setting is profitable on validation after OANDA costs** (best {fmt(best_net)} R), and none "
                   "is positive gross in both periods: wider stops do not rescue the entry signal.")
    lines += ["## Conclusion", "", verdict, "",
              "## Limitations", "",
              f"- {len(df)} settings were tried; the best training result is optimistic by construction.",
              "- Lookbacks fixed at 10 / 10 (O2 found them nearly irrelevant).",
              "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)
