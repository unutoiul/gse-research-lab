"""Study O1: GSE v4.0 settings for the 15m Golden Zone, searched on train, checked on validation.

Only settings a user can change in TradingView today are searched, so a result
needs no Pine change. Execution stays RXM-1 (research model) with the R001
headline slippage. The test period (2023+) is never touched here.

Overfitting controls: one seeded random search (no adaptive tuning on the
same data), a minimum trade count, every configuration scored on validation
(train-to-validation correlation is reported), and a one-at-a-time
sensitivity check around the selected configuration.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, data, experiments, metrics, signals, structure

SPACE = {
    "swing_len": list(range(4, 21)),
    "zone_count": list(range(4, 17)),
    "flip_on": [True, False],
    "cluster_on": [False, True],
    "cluster_atr": [0.3, 0.5, 0.8, 1.0, 1.5],
    "eq_atr": [0.05, 0.10, 0.15, 0.20, 0.30],
    "break_fallback": [True, False],
    "require_sweep": [False, True],
    "space_mult": [1.0, 1.5, 2.0, 2.5, 3.0, 4.0],
}
DEFAULT = {"swing_len": 10, "zone_count": 8, "flip_on": True, "cluster_on": False, "cluster_atr": 0.5, "eq_atr": 0.15,
           "break_fallback": True, "require_sweep": False, "space_mult": 2.0}
INPUT_NAMES = {"swing_len": "Swing Lookback", "zone_count": "Levels per Side", "flip_on": "Enable Flipped Levels",
               "cluster_on": "Merge Nearby Levels", "cluster_atr": "Zone Width (ATR)", "eq_atr": "Equal H/L Tolerance (ATR)",
               "break_fallback": "Follow Last Structure Break", "require_sweep": "Require Sweep for Golden Zone",
               "space_mult": "Room to Next Obstacle (ATR)"}
CORE_KEYS = {"swing_len", "zone_count", "flip_on", "cluster_on", "cluster_atr", "eq_atr", "break_fallback"}
WARMUP, TRAIN, VALIDATE = "2015-10-01", ("2016-01-01", "2019-01-01"), ("2019-01-01", "2023-01-01")
DATA_END = "2023-01-03"  # validation end + 2 days so its last trades can close
SLIPPAGE = 0.10          # R001 headline slippage
MIN_TRAIN_TRADES = 150   # about one a week over 156 weeks
MIN_VAL_TRADES = 200     # about one a week over 208 weeks
SWEEP_SHARE = 0.10       # Require Sweep leaves ~1% of setups (R001), so it is sampled rarely


def canonical(cfg: dict) -> dict:
    cfg = dict(cfg)
    if not cfg["cluster_on"]:
        cfg["cluster_atr"] = DEFAULT["cluster_atr"]  # unused when merging is off
    return cfg


def sample_configs(n: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    seen, out = set(), []
    for cfg in [DEFAULT]:
        key = json.dumps(canonical(cfg), sort_keys=True)
        seen.add(key)
        out.append(canonical(cfg))
    while len(out) < n + 1:
        cfg = {k: v[rng.integers(len(v))] for k, v in SPACE.items()}
        cfg["require_sweep"] = bool(rng.random() < SWEEP_SHARE)
        cfg = {k: (v.item() if hasattr(v, "item") else v) for k, v in canonical(cfg).items()}
        key = json.dumps(cfg, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(cfg)
    return out


# ── Worker side ─────────────────────────────────────────────────────────
_M15: pd.DataFrame | None = None


def _init() -> None:
    global _M15
    _M15 = data.load("M15", start=WARMUP, end=DATA_END)


@lru_cache(maxsize=2)
def _inputs(swing_len: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    core = structure.CoreParams(swing_len=swing_len)
    return structure.prepare(_M15, core), structure.htf_context(_M15, core)


def evaluate(cfg: dict) -> dict:
    core = structure.CoreParams(**{k: cfg[k] for k in CORE_KEYS})
    ctx = structure.ContextParams(require_sweep=cfg["require_sweep"], space_mult=cfg["space_mult"])
    prep, htf = _inputs(cfg["swing_len"])
    out, _ = structure.run(_M15, core, ctx, prep=prep)
    cands = signals.golden_zone_candidates(_M15, out, htf)
    trades = backtest.simulate(_M15, cands, backtest.Execution(slippage=SLIPPAGE))
    row = dict(cfg)
    for name, (a, b) in (("train", TRAIN), ("val", VALIDATE)):
        lo, hi = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        part = trades[trades["time"].between(lo, hi, inclusive="left")] if len(trades) else trades
        s = metrics.summarize(part, (hi - lo).days / 7)
        for k in ("trades", "trades_per_week", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R", "avg_spread_R"):
            row[f"{name}_{k}"] = s.get(k, np.nan)
    return row


def _run_all(configs: list[dict], workers: int) -> pd.DataFrame:
    order = sorted(range(len(configs)), key=lambda i: configs[i]["swing_len"])  # cache locality per worker
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as pool:
        rows = list(pool.map(evaluate, [configs[i] for i in order], chunksize=4))
    df = pd.DataFrame(rows)
    df["trial"] = [order[i] for i in range(len(order))]
    return df.sort_values("trial", ignore_index=True)


def _neighbours(cfg: dict) -> list[dict]:
    out = []
    for k, values in SPACE.items():
        if k == "cluster_atr" and not cfg["cluster_on"]:
            continue
        for v in values:
            if v != cfg[k]:
                c = canonical({**cfg, k: v})
                out.append({**c, "_varied": k})
    return out


def run_study(trials: int = 400, seed: int = 20261011, workers: int | None = None) -> Path:
    workers = workers or max(1, min(16, (os.cpu_count() or 2) - 2))
    configs = sample_configs(trials, seed)
    df = _run_all(configs, workers)
    df["is_default"] = df["trial"] == 0
    eligible = df[df["train_trades"] >= MIN_TRAIN_TRADES].copy()
    top = eligible.sort_values("train_expectancy_R", ascending=False).head(20)
    pick_pool = top[top["val_trades"] >= MIN_VAL_TRADES]
    chosen = pick_pool.sort_values("val_expectancy_R", ascending=False).iloc[0] if len(pick_pool) else None

    sens = pd.DataFrame()
    if chosen is not None:
        base = {k: (chosen[k].item() if hasattr(chosen[k], "item") else chosen[k]) for k in SPACE}
        neigh = _neighbours(base)
        varied = [n.pop("_varied") for n in neigh]
        sens = _run_all(neigh, workers)
        sens["varied"] = varied

    out_dir = data.ROOT / "results" / "O1"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "trials.csv", index=False)
    if len(sens):
        sens.to_csv(out_dir / "sensitivity.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "seed": seed, "trials": trials,
            "space": SPACE, "sweep_share": SWEEP_SHARE, "slippage": SLIPPAGE, "execution": "RXM-1",
            "min_train_trades": MIN_TRAIN_TRADES, "min_val_trades": MIN_VAL_TRADES, "status": experiments.PROVISIONAL}
    chosen_cfg = None if chosen is None else {k: (chosen[k].item() if hasattr(chosen[k], "item") else chosen[k]) for k in SPACE}
    (out_dir / "chosen.json").write_text(json.dumps({"provenance": prov, "chosen": chosen_cfg}, indent=2, default=str) + "\n")
    (out_dir / "report.md").write_text(_report(df, eligible, top, chosen, sens, prov), encoding="utf-8")
    return out_dir


def _report(df, eligible, top, chosen, sens, prov) -> str:
    md = experiments._md
    cols = ["trial", *SPACE, "train_trades", "train_expectancy_R", "train_profit_factor", "train_max_drawdown_R",
            "val_trades", "val_expectancy_R", "val_profit_factor", "val_max_drawdown_R"]
    base = df[df["is_default"]][cols].set_index("trial")
    rho = eligible[["train_expectancy_R", "val_expectancy_R"]].corr(method="spearman").iloc[0, 1] if len(eligible) > 2 else np.nan
    pos_train = int((eligible["train_expectancy_R"] > 0).sum())
    pos_val = int((eligible["val_expectancy_R"] > 0).sum())
    pos_both = int(((eligible["train_expectancy_R"] > 0) & (eligible["val_expectancy_R"] > 0)).sum())
    best_val = eligible["val_expectancy_R"].max() if len(eligible) else np.nan
    lines = [
        "# O1 — GSE v4.0 settings for the 15m Golden Zone", "",
        f"> {prov['status']}", "",
        f"{prov['trials']} random configurations plus the defaults (seed {prov['seed']}), searched over TradingView inputs only. "
        f"Objective: expectancy in R after spread and {prov['slippage']:.2f} slippage, execution RXM-1, on train (2016–2018) with "
        f"≥ {prov['min_train_trades']} trades. Every configuration is also scored on validation (2019–2022). The test period is untouched.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset `{prov['dataset_sha256'][:12]}…`", "",
        "## Does training performance predict validation?", "",
        f"- Configurations with enough training trades: {len(eligible)} of {len(df)}.",
        f"- Positive expectancy on train: {pos_train}; on validation: {pos_val}; on both: {pos_both}.",
        f"- Rank correlation of train and validation expectancy (Spearman): {experiments._fmt(rho)}.",
        f"- Best validation expectancy of any eligible configuration: {experiments._fmt(best_val)} R.", "",
        "## GSE defaults", "", md(base), "",
        "## Top 20 on train, with their validation results", "", md(top[cols].set_index("trial")), "",
    ]
    if chosen is None:
        lines += ["No top-20 configuration had enough validation trades; nothing is selected.", ""]
    else:
        ch = {k: chosen[k] for k in SPACE}
        lines += ["## Selected (best validation expectancy among the top 20 on train)", "",
                  "| TradingView input | Value | Default |", "|---|---|---|",
                  *[f"| {INPUT_NAMES[k]} | {ch[k]} | {DEFAULT[k]} |" for k in SPACE if not (k == 'cluster_atr' and not ch['cluster_on'])], "",
                  f"Train: {int(chosen['train_trades'])} trades, expectancy {experiments._fmt(chosen['train_expectancy_R'])} R, "
                  f"PF {experiments._fmt(chosen['train_profit_factor'])}, max drawdown {experiments._fmt(chosen['train_max_drawdown_R'])} R. "
                  f"Validation: {int(chosen['val_trades'])} trades, expectancy {experiments._fmt(chosen['val_expectancy_R'])} R, "
                  f"PF {experiments._fmt(chosen['val_profit_factor'])}, max drawdown {experiments._fmt(chosen['val_max_drawdown_R'])} R.", "",
                  "Its validation figure is optimistic: validation was used to pick it from 20. Only the locked test period can confirm it.", ""]
        if len(sens):
            s = sens.copy()
            s["value"] = [s.at[i, s.at[i, "varied"]] for i in s.index]
            s = s[["varied", "value", "train_trades", "train_expectancy_R", "val_trades", "val_expectancy_R"]]
            lines += ["## Sensitivity: one input changed at a time from the selected configuration", "",
                      "A robust choice sits on a plateau: neighbours perform similarly. A spike means luck.", "",
                      md(s.set_index("varied")), ""]
    verdict = ("**No configuration is positive on validation.** The search does not support recommending any setting: "
               "under RXM-1, the Golden Zone has no edge after costs in 2016–2022 at any tested setting."
               if not (best_val > 0) else
               "Some configurations are positive on validation. Treat the selected one as a candidate only: "
               "confirm it on the locked test period (owner approval) before any use.")
    lines += ["## Conclusion", "", verdict, "",
              "## Limitations", "",
              f"- {len(df)} configurations were tried, so the best training result is optimistic by construction.",
              "- Only the Golden Zone signal with RXM-1 execution is searched; stops, targets and holding time are not tuned.",
              "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)


def gross_check(trial_ids: list[int]) -> pd.DataFrame:
    """Signal or costs? The same trades filled at mid prices with no slippage, for chosen trials.

    Appends a section to results/O1/report.md and writes results/O1/gross.csv.
    """
    _init()
    mid = _M15.copy()
    for side in ("bid", "ask"):
        for k in ("open", "high", "low", "close"):
            mid[f"{side}_{k}"] = mid[k]
    out_dir = data.ROOT / "results" / "O1"
    trials = pd.read_csv(out_dir / "trials.csv")
    rows = []
    for tr in trial_ids:
        rec = trials[trials["trial"] == tr].iloc[0]
        cfg = {k: (bool(rec[k]) if isinstance(DEFAULT[k], bool) else rec[k].item()) for k in SPACE}
        core = structure.CoreParams(**{k: cfg[k] for k in CORE_KEYS})
        ctx = structure.ContextParams(require_sweep=cfg["require_sweep"], space_mult=cfg["space_mult"])
        prep, htf = _inputs(cfg["swing_len"])
        out, _ = structure.run(_M15, core, ctx, prep=prep)
        trades = backtest.simulate(mid, signals.golden_zone_candidates(_M15, out, htf), backtest.Execution(slippage=0.0))
        row = {"trial": tr}
        for name, (a, b) in (("train", TRAIN), ("val", VALIDATE)):
            part = trades[trades["time"].between(pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC"), inclusive="left")]
            row[f"{name}_trades"] = metrics.summarize(part)["trades"]
            row[f"{name}_gross_R"] = metrics.summarize(part)["expectancy_R"]
            row[f"{name}_net_R"] = rec[f"{name}_expectancy_R"]
        rows.append(row)
    df = pd.DataFrame(rows).set_index("trial")
    df.to_csv(out_dir / "gross.csv")
    section = ["", "## Signal or costs? Gross expectancy (mid-price fills, no slippage)", "",
               "Trial 0 is the GSE defaults. Net = spread + 0.10 slippage, as above.", "",
               experiments._md(df), ""]
    with open(out_dir / "report.md", "a", encoding="utf-8") as f:
        f.write("\n".join(section))
    return df
