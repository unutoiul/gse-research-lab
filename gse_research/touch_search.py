"""Study S3: fresh and flipped level touches (GSE v4.1 levels) with inducement, stops, targets and trailing.

FRESH_FLIP_TOUCH_SPEC.md writes the rules down. Every setting below is searched together:

Trade designs (the level engine runs once per design, GSE v4.1 role-reversal rules, 2015-10 .. 2023-01):
- chart 15m / 1H / 4H; swing lookback 3 / 5 / 10;
- level: "fresh" (first touch of a fresh level) or "flipped" (first touch of a confirmed flipped level
  after its confirming retest: the indicator's "Flipped support/resistance touched");
- entry: a limit at the level, or "close_back" (the touch candle closes back on the level's side,
  market at the next open);
- 4H direction: trade with it, against it, or "off" (the nearest enterable level on either side).
Exits, derived from the same entries (`with_fixed_exits`):
- stop 1 / 1.5 / 3 chart ATR from the entry;
- target 1R / 1.5R / 2R / 3R; breakeven at +1R with a 2R target; or no target with a trailing stop
  from +1R: 2 ATR behind the best close ("trail_atr") or behind the latest minor swing ("trail_swing").
Filters on the signal candles:
- inducement: off; "present", "cleared" or "none" for minor swing lookback 2 / 3 / 5; "swept" for
  each lookback within 5 / 10 / 20 candles (strategy.inducement);
- session: London or New York only, or any time.

Every combination is scored at OANDA costs on train (2016-2018) and validation (2019-2022). Train alone
picks the finalists (highest SQN); validation judges them with the interval widened for the number of
finalists, as in S1/S2. The test period (2023+) was spent on X1 and is not used.
"""

from __future__ import annotations

import itertools
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics, resources
from . import msnr_search as ms
from . import strategy as st

WARMUP, DATA_END = ms.WARMUP, ms.DATA_END
PERIODS, YEARS, COSTS = ms.PERIODS, ms.YEARS, ms.COSTS
MIN_TRAIN_TRADES, MIN_VAL_TRADES, FINALISTS = ms.MIN_TRAIN_TRADES, ms.MIN_VAL_TRADES, ms.FINALISTS

DESIGN = {"chart_tf": ["15m", "1H", "4H"], "swing_len": [3, 5, 10], "level_type": ["fresh", "flipped"],
          "entry_mode": ["limit", "close_back"], "h4_mode": ["with", "against", "off"]}
STOPS = [1.0, 1.5, 3.0]
# name: (target in R or NaN for none, stop management)
EXITS = {
    "1R": (1.0, None), "1.5R": (1.5, None), "2R": (2.0, None), "3R": (3.0, None),
    "be_2R": (2.0, st.Manage(be_r=1.0)),
    "trail_atr": (math.nan, st.Manage(trail="atr", trail_start_r=1.0, trail_atr=2.0)),
    "trail_swing": (math.nan, st.Manage(trail="swing", trail_start_r=1.0)),
}
IND_LENS, IND_AGES = (2, 3, 5), (5, 10, 20)
INDUCEMENT = (["off"] + [f"{s}_{k}" for s in ("present", "cleared", "none") for k in IND_LENS]
              + [f"swept_{k}_{a}" for k in IND_LENS for a in IND_AGES])
PARAMS = [*DESIGN, "stop_atr", "exit", "inducement", "session"]
GROUP = ("chart_tf", "swing_len", "entry_mode")
REFERENCE = {"chart_tf": "15m", "swing_len": 10, "level_type": "fresh", "entry_mode": "limit", "h4_mode": "off",
             "stop_atr": 1.0, "exit": "1.5R", "inducement": "off", "session": False}
STUDY = "S3"

_M15: pd.DataFrame | None = None


def _init() -> None:
    global _M15
    _M15 = data.load("M15", start=WARMUP, end=DATA_END)


@lru_cache(maxsize=3)
def _chart(tf: str) -> pd.DataFrame:
    return _M15 if tf == "15m" else data.aggregate(_M15, tf)


@lru_cache(maxsize=3)
def _h4(tf: str):
    return st.h4_inputs(_chart(tf), st.StrategyParams())


def _params(design: dict) -> st.StrategyParams:
    return st.StrategyParams(swing_len=int(design["swing_len"]), level_type=design["level_type"],
                             entry_mode=design["entry_mode"], h4_mode=design["h4_mode"], flip_rules="4.1",
                             htf_check=False, stop_atr=1.0, target_r=1.0)


def design_signals(design: dict) -> pd.DataFrame:
    """The design's entries (any fixed exit) with inducement for every tested lookback."""
    tf = design["chart_tf"]
    return st.signals(_chart(tf), _params(design), h4=_h4(tf), ind_lens=IND_LENS)


def inducement_mask(sig: pd.DataFrame, setting: str) -> np.ndarray:
    if setting == "off":
        return np.ones(len(sig), dtype=bool)
    kind, k, *age = setting.split("_")
    if kind == "swept":
        a = sig[f"ind{k}_sweep_age"].to_numpy(int)
        return (a >= 0) & (a <= int(age[0]))
    state = sig[f"ind{k}_state"].to_numpy(int)
    return state == {"none": 0, "present": 1, "cleared": 2}[kind]


def session_mask(sig: pd.DataFrame) -> np.ndarray:
    return sig["in_london"].to_numpy(bool) | sig["in_ny"].to_numpy(bool)


def exit_signals(sig: pd.DataFrame, stop_atr: float, exit_name: str) -> tuple[pd.DataFrame, st.Manage | None]:
    target_r, manage = EXITS[exit_name]
    return ms.with_fixed_exits(sig, stop_atr, target_r), manage


def evaluate_group(tf: str, swing: int, entry_mode: str) -> list[dict]:
    """Every design with this chart, lookback and entry, under every exit, inducement and session filter."""
    chart = _chart(tf)
    inner = [k for k in DESIGN if k not in GROUP]
    rows = []
    for values in itertools.product(*(DESIGN[k] for k in inner)):
        design = {"chart_tf": tf, "swing_len": swing, "entry_mode": entry_mode, **dict(zip(inner, values))}
        sig0 = design_signals(design)
        base = sig0["signal"].to_numpy(bool)
        sess = session_mask(sig0)
        filters = [(ind, s, base & inducement_mask(sig0, ind) & (sess if s else True))
                   for ind in INDUCEMENT for s in (False, True)]
        for stop_atr, exit_name in itertools.product(STOPS, EXITS):
            sig, manage = exit_signals(sig0, stop_atr, exit_name)
            for ind, s, keep in filters:
                row = {**design, "stop_atr": stop_atr, "exit": exit_name, "inducement": ind, "session": s}
                filtered = sig.assign(signal=keep)
                for period, (a, b) in PERIODS.items():
                    trades, _ = st.simulate(chart, filtered, a, b, COSTS["net"], manage)
                    row.update(ms._score(trades, (pd.Timestamp(b) - pd.Timestamp(a)).days / 7, period, period))
                rows.append(row)
    return rows


def _run_group(key: tuple) -> list[dict]:
    return evaluate_group(*key)


def run_search(workers: int | None = None, out_dir: Path | None = None, progress=None) -> Path:
    # 15m groups first: they are the slow ones, so no worker is left with a long tail.
    groups = [(tf, s, e) for tf in DESIGN["chart_tf"] for s in DESIGN["swing_len"] for e in DESIGN["entry_mode"]]
    per_design = len(STOPS) * len(EXITS) * len(INDUCEMENT) * 2
    total = math.prod(len(v) for v in DESIGN.values()) * per_design
    workers = min(workers or resources.default_workers(), len(groups))
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as pool:
        futures = [pool.submit(_run_group, g) for g in groups]
        for i, fut in enumerate(as_completed(futures), 1):
            rows.extend(fut.result())
            if progress:
                progress(0.85 * i / len(groups), f"{len(rows):,} of {total:,} combinations")
    trials = pd.DataFrame(rows)
    if progress:
        progress(0.88, "finalists on validation")
    _init()
    finalists = judge(trials)
    out_dir = out_dir or data.ROOT / "results" / STUDY
    out_dir.mkdir(parents=True, exist_ok=True)
    trials.to_csv(out_dir / "trials.csv", index=False)
    finalists.to_csv(out_dir / "finalists.csv", index=False)
    if len(finalists):
        detail_trades(finalists.iloc[0].to_dict()).to_csv(out_dir / "best_trades.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "study": STUDY, "design": DESIGN,
            "stops": STOPS, "exits": {k: [v[0], None if v[1] is None else vars(v[1])] for k, v in EXITS.items()},
            "inducement": INDUCEMENT, "session": [False, True], "flip_rules": "4.1",
            "costs": {k: vars(v) for k, v in COSTS.items()}, "min_train_trades": MIN_TRAIN_TRADES,
            "min_val_trades": MIN_VAL_TRADES, "finalists": FINALISTS, "status": experiments.PROVISIONAL}
    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(report(trials, finalists, prov), encoding="utf-8")
    return out_dir


def _cfg(row: dict) -> dict:
    return {k: (row[k].item() if hasattr(row[k], "item") else row[k]) for k in PARAMS}


def _trades(cfg: dict, period: str, broker: st.Broker, cache: dict) -> pd.DataFrame:
    design = {k: cfg[k] for k in DESIGN}
    key = tuple(design.values())
    if key not in cache:
        cache.clear()  # finalists are sorted by design: keep one design's signals at a time
        cache[key] = design_signals(design)
    sig0 = cache[key]
    sig, manage = exit_signals(sig0, float(cfg["stop_atr"]), cfg["exit"])
    keep = sig0["signal"].to_numpy(bool) & inducement_mask(sig0, cfg["inducement"])
    if bool(cfg["session"]):
        keep &= session_mask(sig0)
    trades, _ = st.simulate(_chart(cfg["chart_tf"]), sig.assign(signal=keep), *PERIODS[period], broker, manage)
    return trades


def judge(trials: pd.DataFrame) -> pd.DataFrame:
    """Train picks the finalists; validation judges each at three cost levels, year by year."""
    eligible = trials[trials["train_trades"] >= MIN_TRAIN_TRADES]
    top = eligible.sort_values("train_sqn", ascending=False).head(FINALISTS)
    top = top.sort_values(list(DESIGN), kind="stable")
    level = 1 - 0.10 / max(1, len(top))  # one-sided 5% overall across the finalists (Bonferroni)
    rows, cache = [], {}
    for _, r in top.iterrows():
        cfg = _cfg(r.to_dict())
        a, b = PERIODS["val"]
        row = {**cfg, **{k: r[k] for k in r.index if k.startswith("train_")}}
        for cost, broker in COSTS.items():
            trades = _trades(cfg, "val", broker, cache)
            row.update(ms._score(trades, (pd.Timestamp(b) - pd.Timestamp(a)).days / 7, "val", f"val_{cost}"))
            if cost == "net":
                ci = metrics.bootstrap_mean(metrics.closed(trades), level=level)
                row["val_net_ci_low"], row["val_net_ci_high"] = ci["low"], ci["high"]
        row["val_years_positive"] = int(sum((row.get(f"val_net_{y}_R") or 0) > 0 for y in YEARS["val"]))
        row["verdict"] = ms.finalist_verdict(row)
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        rank = {"candidate": 0, "watch": 1, "inconclusive": 2, "rejected": 3}
        out = out.assign(_r=out["verdict"].map(rank)).sort_values(["_r", "val_net_expectancy_R"], ascending=[True, False])
        out = out.drop(columns="_r").reset_index(drop=True)
    return out


def detail_trades(cfg: dict) -> pd.DataFrame:
    return _trades(_cfg(cfg), "val", COSTS["net"], {})


def inducement_effect(trials: pd.DataFrame, min_trades: int = 30) -> pd.DataFrame:
    """Each inducement setting against no inducement, everything else equal: the mean change in R per
    trade, over the pairs where both sides have at least `min_trades` trades in that period."""
    others = [p for p in PARAMS if p != "inducement"]
    off = trials[trials["inducement"] == "off"].set_index(others)
    rows = []
    for ind, g in trials[trials["inducement"] != "off"].groupby("inducement", sort=False):
        g = g.set_index(others)
        row = {"inducement": ind}
        for period in PERIODS:
            both = g.join(off, rsuffix="_off", how="inner")
            ok = (both[f"{period}_trades"] >= min_trades) & (both[f"{period}_trades_off"] >= min_trades)
            diff = (both[f"{period}_expectancy_R"] - both[f"{period}_expectancy_R_off"])[ok]
            row[f"{period}_pairs"] = int(ok.sum())
            row[f"{period}_R_change"] = float(diff.mean()) if len(diff) else np.nan
            row[f"{period}_better_share"] = float((diff > 0).mean()) if len(diff) else np.nan
        rows.append(row)
    return pd.DataFrame(rows).set_index("inducement").round(3)


def report(trials: pd.DataFrame, finalists: pd.DataFrame, prov: dict) -> str:
    md, fmt = experiments._md, experiments._fmt
    eligible = trials[trials["train_trades"] >= MIN_TRAIN_TRADES]
    rho = eligible[["train_expectancy_R", "val_expectancy_R"]].corr(method="spearman").iloc[0, 1] if len(eligible) > 2 else np.nan
    line = ms.luck_line(len(eligible))
    ref = trials[np.logical_and.reduce([trials[k] == v for k, v in REFERENCE.items()])]
    both = eligible[(eligible["train_expectancy_R"] > 0) & (eligible["val_expectancy_R"] > 0)]
    counts = finalists["verdict"].value_counts().to_dict() if len(finalists) else {}
    cols = [*PARAMS, "train_trades", "train_win_rate", "train_expectancy_R", "train_sqn", "val_net_trades", "val_net_win_rate",
            "val_net_expectancy_R", "val_net_profit_factor", "val_net_ci_low", "val_years_positive", "val_gross_expectancy_R",
            "verdict"]
    cols = [c for c in cols if c in finalists]
    lines = [
        f"# {STUDY} — Fresh and flipped level touches with inducement, stops, targets and trailing (GSE v4.1 levels)", "",
        f"> {prov['status']}", "",
        f"{len(trials):,} combinations: {math.prod(len(v) for v in DESIGN.values())} trade designs × {len(STOPS)} stops × "
        f"{len(EXITS)} exits × {len(INDUCEMENT)} inducement settings × 2 session settings. Train 2016–2018 picks, "
        "validation 2019–2022 judges; the test period was spent on X1 and is not used. OANDA bid/ask + 0.10 slippage; "
        "conservative intrabar order. Rules: FRESH_FLIP_TOUCH_SPEC.md.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset `{prov['dataset_sha256'][:12]}…`", "",
        "## Summary", "",
        f"- Combinations with ≥ {MIN_TRAIN_TRADES} training trades: {len(eligible):,} of {len(trials):,}.",
        f"- Positive after costs: train {int((eligible['train_expectancy_R'] > 0).sum()):,}, validation "
        f"{int((eligible['val_expectancy_R'] > 0).sum()):,}, both {len(both):,}.",
        f"- Training rank vs validation rank (Spearman): {fmt(rho)}. Near zero means training results do not carry over.",
        f"- Luck line: among {len(eligible):,} combinations with no edge, the best training SQN would reach about "
        f"{line:.1f}. Best training SQN found: {fmt(eligible['train_sqn'].max() if len(eligible) else np.nan)}.",
        f"- Finalists (top {FINALISTS} training SQN), judged on validation: "
        + (", ".join(f"{v} {k}" for k, v in counts.items()) or "none") + ".", "",
        "## The spec's base rule (15m, lookback 10, fresh, limit, either side, 1 ATR stop, 1.5R, no filters)", "",
        md(ref[[*PARAMS, "train_trades", "train_expectancy_R", "val_trades", "val_expectancy_R"]].set_index("chart_tf")), "",
        "## Finalists on validation", "",
        md(finalists[cols].set_index("chart_tf")) if len(finalists) else "No combination had enough training trades.", "",
        "## Does inducement help? (each setting against no inducement, everything else equal)", "",
        "R_change is the mean change in R per trade after costs; better_share the share of pairs it improved. "
        "Pairs need 30 trades on both sides in that period.", "",
        md(inducement_effect(trials)), "",
        "## What each choice does on average (combinations with enough training trades)", "",
    ]
    for p in PARAMS:
        m = eligible.groupby(p).agg(combinations=("val_expectancy_R", "size"), train_R=("train_expectancy_R", "mean"),
                                    val_R=("val_expectancy_R", "mean"), best_val_R=("val_expectancy_R", "max"),
                                    val_win_rate=("val_win_rate", "mean")).round(3)
        lines += [f"### {p}", "", md(m), ""]
    cand = finalists[finalists["verdict"] == "candidate"] if len(finalists) else finalists
    if len(cand):
        verdict = (f"**{len(cand)} finalist(s) pass validation** (positive after costs, interval above zero after the "
                   f"{FINALISTS}-finalist correction, profit factor ≥ {metrics.MIN_PROFIT_FACTOR}, ≥ 3 of 4 years positive). "
                   "No unused test period remains: a candidate needs a forward test on data after 2026-10-13 and the "
                   "TradingView parity check before any trading.")
    else:
        verdict = ("**No combination passes validation.** Training picked the most consistent combinations; none of them "
                   "made money after costs on 2019–2022 with enough evidence. Tuning these touch rules, inducement, stops, "
                   "targets and trailing does not produce a reliable edge on XAU/USD.")
    lines += ["## Conclusion", "", verdict, "",
              "## Limitations", "",
              "- Mechanical rules: discretionary judgement is not tested.",
              "- Inducement is one mechanical reading (minor wick swings in front of the level); others exist.",
              "- Trailing stops move at candle closes only; partial exits are not tested.",
              "- 4H charts give few trades; most 4H combinations fall below the training minimum.",
              "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)
