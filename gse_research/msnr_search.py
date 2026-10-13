"""Study S1: Malaysian SnR with the owner's confluences, on GSE Strategy v4.0 (research variants).

GSE's levels are already Malaysian SnR levels: A/V body turns, fresh until a wick touches
them, and a body close through turns them around (support becomes resistance). The search
crosses how a level is traded with the confluences the owner trades with.

Trade designs (the level engine runs once per design over 2015-10 .. 2023-01):
- chart 15m / 1H; swing lookback 3 / 5 / 10 (3: nearly every body turn, as Malaysian SnR draws);
- levels: fresh A/V, flip (broken by a body close and untouched since: "fresh again"), or both;
- entry: a limit at the level, or at the next open after the first touch closes back on the
  level's side, with the indicator's rejection wick ("rejection") or without ("close_back");
- with or against the 4H direction; stop structural, or 1.5 / 3 chart ATR from the entry.
Confluences (each on or off, applied to the signal candles):
- d1: the 1D bias (GSE f_bias_score) in the trade direction: the storyline;
- sweep: a liquidity sweep in the trade direction within the last 8 candles (GSE conf_cluster);
- session: London or New York only (GSE session hours);
- zone: buys below the middle of the current swing range (discount), sells above it (premium);
- mtf: the chart bias and the next two timeframes' biases all in the trade direction.
First touch only, always: fresh and flip levels are untouched until the entry.

Study S2 (short target, long stop) runs the same designs and confluences with a fixed stop of
1.5 / 3 / 5 chart ATR and a fixed target of 0.25 / 0.5 / 0.75 / 1 times that risk, in place of
the website's structure target. Entries do not depend on the exits, so each design's signals
are built once and the twelve exit shapes are derived from them (`with_fixed_exits`).

Every combination is scored at OANDA costs on train (2016-2018) and validation (2019-2022).
Train alone picks the finalists (most consistent: highest SQN); validation judges them, with
the interval widened for the number of finalists. The test period stays locked.
"""

from __future__ import annotations

import itertools
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics, resources, structure
from . import strategy as st

WARMUP, D1_WARMUP, DATA_END = "2015-10-01", "2015-01-01", "2023-01-03"
PERIODS = {"train": ("2016-01-01", "2019-01-01"), "val": ("2019-01-01", "2023-01-01")}
YEARS = {"train": (2016, 2017, 2018), "val": (2019, 2020, 2021, 2022)}

DESIGN = {"chart_tf": ["15m", "1H"], "swing_len": [3, 5, 10], "level_type": ["fresh", "flip", "both"],
          "entry_mode": ["limit", "rejection", "close_back"], "h4_mode": ["with", "against"], "stop_atr": [0.0, 1.5, 3.0]}
FILTERS = ["d1", "sweep", "session", "zone", "mtf"]
PARAMS = [*DESIGN, *FILTERS]
SWEEP_BARS = 8                       # structure.ContextParams.conf_cluster
UP = {"15m": ("1H", "4H"), "1H": ("4H", "1D")}
COSTS = {"net": st.Broker(slippage=0.10, spread_scale=1.0), "half": st.Broker(slippage=0.05, spread_scale=0.5),
         "gross": st.Broker(slippage=0.0, spread_scale=0.0)}
MIN_TRAIN_TRADES, MIN_VAL_TRADES, FINALISTS = 100, 100, 20
PINE = {"chart_tf": "15m", "swing_len": 10, "level_type": "fresh", "entry_mode": "limit", "h4_mode": "with", "stop_atr": 0.0,
        **{f: False for f in FILTERS}}
GROUP = ("chart_tf", "swing_len", "entry_mode")   # one worker task: one chart, lookback and entry


@dataclass(frozen=True)
class Study:
    name: str
    kind: str
    title: str
    design: dict
    derived: tuple = ()                 # exit keys derived from the signals (fixed stop and target)
    reference: dict = field(default_factory=dict)
    reference_title: str = ""

    @property
    def params(self) -> list[str]:
        return [*self.design, *FILTERS]


S1 = Study("S1", "search_s1", "Malaysian SnR with confluences (GSE Strategy v4.0 research variants)", DESIGN,
           reference=PINE, reference_title="The Pine strategy as written (15m, lookback 10, fresh, limit, with 4H, no filters)")
S2 = Study("S2", "search_s2", "Short target, long stop (Malaysian SnR designs with confluences)",
           {**{k: v for k, v in DESIGN.items() if k != "stop_atr"}, "stop_atr": [1.5, 3.0, 5.0],
            "target_r": [0.25, 0.5, 0.75, 1.0]}, derived=("stop_atr", "target_r"))
STUDIES = {"S1": S1, "S2": S2}


def _study(study) -> Study:
    return study if isinstance(study, Study) else STUDIES[study]

_HIST: pd.DataFrame | None = None    # M15 from D1_WARMUP: daily and higher biases settle before 2016
_M15: pd.DataFrame | None = None


def _init() -> None:
    global _HIST, _M15
    _HIST = data.load("M15", start=D1_WARMUP, end=DATA_END)
    _M15 = _HIST[_HIST["time"] >= pd.Timestamp(WARMUP, tz="UTC")].reset_index(drop=True)


@lru_cache(maxsize=1)
def _chart(tf: str) -> pd.DataFrame:
    return _M15 if tf == "15m" else data.aggregate(_M15, tf)


@lru_cache(maxsize=1)
def _h4(tf: str):
    return st.h4_inputs(_chart(tf), st.StrategyParams())


@lru_cache(maxsize=1)
def _inputs(tf: str, swing: int) -> tuple:
    """1H target packets, the 1D bias, the next two timeframes' biases and the swing-range middle."""
    chart, p = _chart(tf), st.StrategyParams(swing_len=swing)
    return st.h1_inputs(chart, p), st.d1_inputs(chart, p, _HIST), higher_bias(chart, tf, p, _HIST), range_mid(chart, swing)


def higher_bias(chart: pd.DataFrame, tf: str, p: st.StrategyParams, history: pd.DataFrame) -> np.ndarray:
    """GSE bias scores of the next two timeframes up, as each chart candle sees them at its close."""
    rows = []
    for up in UP[tf]:
        htf = data.aggregate(history, up)
        htf = htf.assign(score=structure.bias_scores(htf, p.core(p.swing_len)))
        rows.append(data.align(chart, htf, ["score"], at="close")["score"].to_numpy(float))
    return np.vstack(rows)


def range_mid(chart: pd.DataFrame, swing: int) -> np.ndarray:
    """Middle of the current swing range: the last confirmed swing high and low (no look-ahead)."""
    hi = structure.pivots(chart["high"].to_numpy(float), swing, swing, True)
    lo = structure.pivots(chart["low"].to_numpy(float), swing, swing, False)
    return ((pd.Series(hi).ffill() + pd.Series(lo).ffill()) / 2).to_numpy()


def filter_masks(sig: pd.DataFrame, d1: np.ndarray, up: np.ndarray, mid: np.ndarray) -> dict[str, np.ndarray]:
    """For each confluence, the candles where it agrees with the signal's trade direction."""
    d = sig["dir"].to_numpy(float)
    age = np.where(d == 1, sig["bull_sweep_age"].to_numpy(float), sig["bear_sweep_age"].to_numpy(float))
    entry = sig["entry"].to_numpy(float)
    trade = d != 0  # no direction, no confluence (a neutral reading never agrees)
    with np.errstate(invalid="ignore"):
        masks = {
            "d1": np.sign(d1) == d,
            "sweep": (age >= 0) & (age <= SWEEP_BARS),
            "session": sig["in_london"].to_numpy(bool) | sig["in_ny"].to_numpy(bool),
            "zone": np.where(d == 1, entry < mid, entry > mid),
            "mtf": (np.sign(sig["trend_score"].to_numpy(float)) == d) & (np.sign(up[0]) == d) & (np.sign(up[1]) == d),
        }
    return {k: v & trade for k, v in masks.items()}


def _params(design: dict) -> st.StrategyParams:
    return st.StrategyParams(swing_len=int(design["swing_len"]), h4_mode=design["h4_mode"], stop_atr=float(design["stop_atr"]),
                             entry_mode=design["entry_mode"], level_type=design["level_type"],
                             target_r=float(design.get("target_r", 0.0)))


def with_fixed_exits(sig: pd.DataFrame, stop_atr: float, target_r: float, tick: float = 0.01) -> pd.DataFrame:
    """A fixed-exit design's signals from the same entries: the stop stop_atr chart ATRs from the
    entry, the target target_r times that risk, rounded exactly as strategy.fixed_plan rounds them."""
    d = sig["dir"].to_numpy(float)
    entry, atr = sig["entry"].to_numpy(float), sig["atr"].to_numpy(float)
    stop = st.side_round(entry - d * (stop_atr * atr), tick, d)
    risk = d * (entry - stop)
    tp = st.side_round(entry + d * target_r * risk, tick, d)
    return sig.assign(stop=stop, tp2=tp)


def _score(trades: pd.DataFrame, weeks: float, period: str, prefix: str) -> dict:
    s = metrics.summarize(trades, weeks)
    row = {f"{prefix}_{k}": s.get(k, np.nan) for k in ("trades", "expectancy_R", "profit_factor", "win_rate", "max_drawdown_R", "sqn")}
    closed = metrics.closed(trades)
    years = closed.groupby(closed["exit_time"].dt.year)["R"].mean() if len(closed) else pd.Series(dtype=float)
    for y in YEARS[period]:
        row[f"{prefix}_{y}_R"] = years.get(y, np.nan)
    return row


def evaluate_group(tf: str, swing: int, entry_mode: str, study: Study | str = S1) -> list[dict]:
    """Every design with this chart, lookback and entry, each under all 32 confluence combinations."""
    study = _study(study)
    chart = _chart(tf)
    h1, d1, up, mid = _inputs(tf, swing)
    inner = [k for k in study.design if k not in GROUP and k not in study.derived]
    rows = []
    for values in itertools.product(*(study.design[k] for k in inner)):
        design = {"chart_tf": tf, "swing_len": swing, "entry_mode": entry_mode, **dict(zip(inner, values))}
        if study.derived:  # entries once (any fixed exit), then each exit shape from them
            sig0 = st.signals(chart, _params({**design, "stop_atr": 1.0, "target_r": 1.0}), h1, _h4(tf))
            shapes = [(dict(zip(study.derived, v)), with_fixed_exits(sig0, *v))
                      for v in itertools.product(*(study.design[k] for k in study.derived))]
        else:
            sig0 = st.signals(chart, _params(design), h1, _h4(tf))
            shapes = [({}, sig0)]
        masks, base = filter_masks(sig0, d1, up, mid), sig0["signal"].to_numpy(bool)
        for exits, sig in shapes:
            for combo in itertools.product([False, True], repeat=len(FILTERS)):
                on = dict(zip(FILTERS, combo))
                keep = base.copy()
                for f, active in on.items():
                    if active:
                        keep &= masks[f]
                filtered = sig.assign(signal=keep)
                row = {**design, **exits, **on}
                for period, (a, b) in PERIODS.items():
                    trades, _ = st.simulate(chart, filtered, a, b, COSTS["net"])
                    row.update(_score(trades, (pd.Timestamp(b) - pd.Timestamp(a)).days / 7, period, period))
                rows.append({k: row[k] for k in study.params} | {k: v for k, v in row.items() if k not in study.params})
    return rows


def _run_group(key: tuple) -> list[dict]:
    return evaluate_group(*key)


def run_search(workers: int | None = None, out_dir: Path | None = None, progress=None, study: Study | str = "S1") -> Path:
    study = _study(study)
    design = study.design
    # 15m groups first: they are the slow ones, so no worker is left with a long tail.
    groups = [(tf, s, e, study.name) for tf in design["chart_tf"] for s in design["swing_len"] for e in design["entry_mode"]]
    total = math.prod(len(v) for v in design.values()) * 2 ** len(FILTERS)
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
    finalists = judge(trials, study)
    out_dir = out_dir or data.ROOT / "results" / study.name
    out_dir.mkdir(parents=True, exist_ok=True)
    trials.to_csv(out_dir / "trials.csv", index=False)
    finalists.to_csv(out_dir / "finalists.csv", index=False)
    best = finalists.iloc[0].to_dict() if len(finalists) else None
    if best is not None:
        detail_trades(best).to_csv(out_dir / "best_trades.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "study": study.name, "design": design,
            "filters": FILTERS,
            "costs": {k: vars(v) for k, v in COSTS.items()}, "min_train_trades": MIN_TRAIN_TRADES,
            "min_val_trades": MIN_VAL_TRADES, "finalists": FINALISTS, "status": experiments.PROVISIONAL}
    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(report(trials, finalists, prov, study), encoding="utf-8")
    return out_dir


def luck_line(n: int) -> float:
    """The best SQN to expect from n strategies with no edge at all: about sqrt(2 ln n).
    (An upper guide: the combinations share trades, so the true figure is somewhat lower.)"""
    return math.sqrt(2 * math.log(n)) if n > 1 else 0.0


def _design(row: dict, study: Study) -> dict:
    return {k: (row[k].item() if hasattr(row[k], "item") else row[k]) for k in study.params}


def _signals_for(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    chart = _chart(cfg["chart_tf"])
    h1, d1, up, mid = _inputs(cfg["chart_tf"], int(cfg["swing_len"]))
    sig = st.signals(chart, _params(cfg), h1, _h4(cfg["chart_tf"]))
    keep = sig["signal"].to_numpy(bool).copy()
    masks = filter_masks(sig, d1, up, mid)
    for f in FILTERS:
        if bool(cfg[f]):
            keep &= masks[f]
    return chart, sig.assign(signal=keep)


def judge(trials: pd.DataFrame, study: Study | str = S1) -> pd.DataFrame:
    """Train picks the finalists; validation judges each at three cost levels, year by year."""
    eligible = trials[trials["train_trades"] >= MIN_TRAIN_TRADES]
    top = eligible.sort_values("train_sqn", ascending=False).head(FINALISTS)
    top = top.sort_values(["chart_tf", "swing_len"], kind="stable")  # reuse the level inputs between finalists
    level = 1 - 0.10 / max(1, len(top))  # one-sided 5% overall across the finalists (Bonferroni)
    study = _study(study)
    rows = []
    for _, r in top.iterrows():
        cfg = _design(r.to_dict(), study)
        chart, sig = _signals_for(cfg)
        a, b = PERIODS["val"]
        row = {**cfg, **{k: r[k] for k in r.index if k.startswith("train_")}}
        for cost, broker in COSTS.items():
            trades, _ = st.simulate(chart, sig, a, b, broker)
            s = _score(trades, (pd.Timestamp(b) - pd.Timestamp(a)).days / 7, "val", f"val_{cost}")
            row.update(s)
            if cost == "net":
                ci = metrics.bootstrap_mean(metrics.closed(trades), level=level)
                row["val_net_ci_low"], row["val_net_ci_high"] = ci["low"], ci["high"]
        row["val_years_positive"] = int(sum((row.get(f"val_net_{y}_R") or 0) > 0 for y in YEARS["val"]))
        row["verdict"] = finalist_verdict(row)
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        rank = {"candidate": 0, "watch": 1, "inconclusive": 2, "rejected": 3}
        out = out.assign(_r=out["verdict"].map(rank)).sort_values(["_r", "val_net_expectancy_R"], ascending=[True, False])
        out = out.drop(columns="_r").reset_index(drop=True)
    return out


def finalist_verdict(row: dict) -> str:
    n, e = row.get("val_net_trades") or 0, row.get("val_net_expectancy_R")
    if n < MIN_VAL_TRADES:
        return "inconclusive"
    if not (e is not None and e > 0):
        return "rejected"
    pf, low = row.get("val_net_profit_factor") or 0, row.get("val_net_ci_low")
    if low is not None and low > 0 and pf >= metrics.MIN_PROFIT_FACTOR and row["val_years_positive"] >= 3:
        return "candidate"
    return "watch"


def detail_trades(cfg: dict) -> pd.DataFrame:
    chart, sig = _signals_for(cfg)
    trades, _ = st.simulate(chart, sig, *PERIODS["val"], COSTS["net"])
    return trades


def report(trials: pd.DataFrame, finalists: pd.DataFrame, prov: dict, study: Study | str = S1) -> str:
    study = _study(study)
    params = study.params
    md, fmt = experiments._md, experiments._fmt
    eligible = trials[trials["train_trades"] >= MIN_TRAIN_TRADES]
    rho = eligible[["train_expectancy_R", "val_expectancy_R"]].corr(method="spearman").iloc[0, 1] if len(eligible) > 2 else np.nan
    line = luck_line(len(eligible))
    ref = trials[np.logical_and.reduce([trials[k] == v for k, v in study.reference.items()])] if study.reference else trials.iloc[:0]
    both = eligible[(eligible["train_expectancy_R"] > 0) & (eligible["val_expectancy_R"] > 0)]
    counts = finalists["verdict"].value_counts().to_dict() if len(finalists) else {}
    cols = [*params, "train_trades", "train_win_rate", "train_expectancy_R", "train_sqn", "val_net_trades", "val_net_win_rate",
            "val_net_expectancy_R", "val_net_profit_factor", "val_net_ci_low", "val_years_positive", "val_gross_expectancy_R",
            "verdict"]
    cols = [c for c in cols if c in finalists]
    lines = [
        f"# {study.name} — {study.title}", "",
        f"> {prov['status']}", "",
        f"{len(trials):,} combinations: {math.prod(len(v) for v in study.design.values())} trade designs × "
        f"{2 ** len(FILTERS)} confluence combinations ({', '.join(FILTERS)}). Train 2016–2018 picks, validation "
        "2019–2022 judges, test untouched. OANDA bid/ask + 0.10 slippage; conservative intrabar order.", "",
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
    ]
    if study.reference:
        lines += [f"## {study.reference_title}", "",
                  md(ref[[*params, "train_trades", "train_expectancy_R", "val_trades", "val_expectancy_R"]].set_index("chart_tf")), ""]
    lines += [
        "## Finalists on validation", "",
        md(finalists[cols].set_index("chart_tf")) if len(finalists) else "No combination had enough training trades.", "",
        "## What each choice does on average (combinations with enough training trades)", "",
    ]
    for p in params:
        agg = {"combinations": ("val_expectancy_R", "size"), "train_R": ("train_expectancy_R", "mean"),
               "val_R": ("val_expectancy_R", "mean"), "best_val_R": ("val_expectancy_R", "max")}
        if "val_win_rate" in eligible:
            agg["val_win_rate"] = ("val_win_rate", "mean")
        m = eligible.groupby(p).agg(**agg).round(3)
        lines += [f"### {p}", "", md(m), ""]
    cand = finalists[finalists["verdict"] == "candidate"] if len(finalists) else finalists
    if len(cand):
        verdict = (f"**{len(cand)} finalist(s) pass validation** (positive after costs, interval above zero after the "
                   f"{FINALISTS}-finalist correction, profit factor ≥ {metrics.MIN_PROFIT_FACTOR}, ≥ 3 of 4 years positive). "
                   "Candidates only: next are the locked test period (owner approval) and the TradingView parity check.")
    else:
        verdict = ("**No combination passes validation.** Training picked the most consistent combinations; none of them "
                   "made money after costs on 2019–2022 with enough evidence. Tuning these rules and confluences does not "
                   "produce a reliable edge on XAU/USD.")
    lines += ["## Conclusion", "", verdict, "",
              "## Limitations", "",
              "- Mechanical rules: discretionary judgement is not tested.",
              "- No gap levels (GSE does not draw them; on gold intraday they are rare and tiny).",
              "- Discount/premium uses the middle of the last swing range, not GSE's Golden Zone gate (tested in O1/T1).",
              "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)
