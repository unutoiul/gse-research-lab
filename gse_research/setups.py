"""Study S4: GSE's two setups, tested separately, the way the owner trades them.

Trend engine: GSE's bias (f_bias_score, lookback 10) on closed 1D and 4H candles, as each 15m candle sees
them at its close. Bullish when both are above zero, bearish when both are below, mixed otherwise (no trade).

Setup A, pullback: price pulls back against the trend into a fresh 15m level on the trend side (support in
an uptrend, resistance in a downtrend); its first touch.
Setup B, flip: trend continuation at a 15m support/resistance flip; the first touch of a confirmed flipped
level (GSE v4.1 role-reversal rules) after its confirming retest, on the trend side.

15m entry triggers:
- touch: a limit order resting at the level, filled on the touch;
- rejection: the touch candle closes back on the level's side, in the trade direction, with a wick of at
  least half its range;
- sweep_reclaim: within 8 candles of the touch, a candle trades through the level and closes back;
- bos: from the 2nd to the 16th candle after the touch, a close beyond the most extreme price since the
  touch in the trade direction (above the highest high for a long).
A close through the level cancels the setup. Market triggers enter at the next open; the trend must
still agree at the trigger close.

Risk: the stop goes beyond the structural invalidation (the level's wick and every extreme since the
touch) by the website's buffer max(tick, 0.2 ATR) ("structural"), or at least 1 ATR from the entry
("structural_floor"). Target: GSE's website TP2 (the best target >= 1.5R within 8 ATR, not past the first
major obstacle, from 15m, 1H and 4H structure) or a fixed 2R.
Execution: strategy.simulate (OANDA bid/ask, 0.10 slippage, conservative intrabar order, one position).

Monte Carlo, for the variant chosen per setup: (1) random entries: the same number of market entries at
random 15m closes with a trend, in the trend's direction, with stop and target sizes drawn from the real
trades (risk in ATR, reward in R), MC_RUNS times. If the setup's entries carry information, the real
average R sits above most random runs. (2) Trade resampling: the real trades redrawn in random order,
one year's worth at a time, for the spread of yearly results, the chance of a losing year and drawdowns.

32 variants (2 setups x 4 triggers x 2 stops x 2 targets), all reported. Train 2016-2018 picks one
variant per setup (highest SQN with >= 50 trades); validation 2019-2022 judges it. Every trade also
records its 1H context (confirm / neutral / contradict), the 15m bias, session, volatility regime and
GSE's confluence checks, so the report measures which of them separate better trades from worse.
They are reported, never used to pick.

Study S5 (`run_wide_study`) runs the same setups and triggers with wider stops and nearer targets:
stops 2 / 3 / 5 ATR from the entry, or 1 ATR beyond the structural invalidation; targets 0.25 / 0.5 /
0.75 / 1 R, or the nearest opposing structure (TP1-like, at least 0.25 R). 160 variants, chosen and
judged exactly as in S4.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, experiments, metrics, structure
from . import msnr_search as ms
from . import strategy as st
from .structure import ST_FLIP, ST_FRESH, isna

SWING, TICK = 10, 0.01
SETUPS = {"A_pullback": ST_FRESH, "B_flip": ST_FLIP}
TRIGGERS = ["touch", "rejection", "sweep_reclaim", "bos"]
STOPS = ["structural", "structural_floor"]
TARGETS = ["tp2", "2R"]
SWEEP_WINDOW, BOS_MIN, BOS_WINDOW = 8, 2, 16
LOADS = {"discovery": ("2015-01-01", "2023-01-04")}
PERIODS = {"train": ("2016-01-01", "2019-01-01"), "val": ("2019-01-01", "2023-01-01")}
COSTS = ms.COSTS
MIN_TRADES = 50
S5_STOPS = ["atr2", "atr3", "atr5", "structural_buf1"]
S5_TARGETS = ["r0.25", "r0.5", "r0.75", "r1", "near"]
MC_RUNS, MC_YEARS, MC_SEED = 50, 5000, 20261021
CHECKS = ["bias", "recent_bos", "room", "sweep_recent", "rejection_recent", "volume", "killzone", "score_75"]


# ── Context: the trend engine and the 1H confirmation ───────────────────

def context(m15: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """GSE bias of the closed 1D, 4H and 1H candles at each 15m close; trend +1 / -1 / 0 (mixed)."""
    core = structure.CoreParams(swing_len=SWING)
    out = {}
    for tf in ("1D", "4H", "1H"):
        htf = data.aggregate(history, tf)
        htf = htf.assign(score=structure.bias_scores(htf, core))
        out[tf] = data.align(m15, htf, ["score"], at="close")["score"].to_numpy(float)
    d1, h4 = out["1D"], out["4H"]
    trend = np.where((d1 > 0) & (h4 > 0), 1, np.where((d1 < 0) & (h4 < 0), -1, 0))
    # Daily ATR as a share of price, for volatility regimes (closed days only).
    day = data.aggregate(history, "1D")
    day = day.assign(atr_pct=structure.pine_atr(*(day[k].to_numpy(float) for k in ("high", "low", "close")), 14)
                     / day["close"].to_numpy(float))
    atr_pct = data.align(m15, day, ["atr_pct"], at="close")["atr_pct"].to_numpy(float)
    return pd.DataFrame({"d1": d1, "h4": h4, "h1": out["1H"], "trend": trend, "atr_pct": atr_pct}, index=m15.index)


# ── Triggers after a touch (pure, so they can be tested on their own) ───

def step(setup: dict, t: int, O, H, L, C) -> tuple[list[str], bool]:
    """Advance one setup to the close of candle t: the triggers that fire now, and whether it is finished.

    setup: price, side, touch (candle index), ext (most adverse price since the touch), high_since (most
    favourable price since the touch, before t), fired (set of triggers already fired)."""
    p, d, k = setup["price"], setup["side"], t - setup["touch"]
    adverse = L[t] if d == 1 else H[t]
    setup["ext"] = adverse if setup.get("ext") is None else (min(setup["ext"], adverse) if d == 1 else max(setup["ext"], adverse))
    closed_back = d * (C[t] - p) > 0
    fired = []
    if k == 0 and closed_back:
        rng = H[t] - L[t]
        wick = (min(O[t], C[t]) - L[t]) if d == 1 else (H[t] - max(O[t], C[t]))
        if rng > 0 and d * (C[t] - O[t]) > 0 and wick / rng >= 0.5:
            fired.append("rejection")
    if k <= SWEEP_WINDOW and d * (p - adverse) > 0 and closed_back:
        fired.append("sweep_reclaim")
    if BOS_MIN <= k <= BOS_WINDOW and setup.get("best") is not None and d * (C[t] - setup["best"]) > 0:
        fired.append("bos")
    favour = H[t] if d == 1 else L[t]
    setup["best"] = favour if setup.get("best") is None else (max(setup["best"], favour) if d == 1 else min(setup["best"], favour))
    fired = [f for f in fired if f not in setup["fired"]]
    setup["fired"].update(fired)
    broken = d * (C[t] - p) < 0
    done = broken or k >= BOS_WINDOW or ("bos" in setup["fired"] and ("sweep_reclaim" in setup["fired"] or k >= SWEEP_WINDOW))
    return fired, bool(done)


# ── One pass of the level engine: every candidate entry with its plan inputs ──

def candidates(m15: pd.DataFrame, ctx: pd.DataFrame, h1: tuple, h4: tuple) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every limit candidate (each close, nearest qualifying level per setup) and every market trigger,
    with entry, invalidation, ATR and the target candidates the website engine reads at that close."""
    O, H, L, C = (m15[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    decision = st._ms(m15["close_time"])
    h1_pk, h1_idx, h1_close = h1
    h4_pk, h4_idx, h4_close, _ = h4
    trend = ctx["trend"].to_numpy(int)
    core = structure.CoreParams(swing_len=SWING, tick=TICK, **structure.V41_FLIPS)
    state = {"prev": [], "active": [], "next": 0}
    rows = []

    def watch(levels):
        return [(lv.id, lv.price, lv.role, lv.state, lv.wick) for lv in levels if not lv.in_contact
                and (lv.state == ST_FRESH or (lv.state == ST_FLIP and lv.touches == 1))]

    def raw_targets(t, levels, eqh, eql, pdh, pdl, pwh, pwl, d, entry):
        if not (st.snapshot_valid(1, h1_close[t], decision[t]) and st.snapshot_valid(2, h4_close[t], decision[t])):
            return None
        raw: list = []
        st.unpack(raw, st.packet(levels, eqh, eql, pdh, pdl, pwh, pwl, TICK), 0, decision[t], decision[t], d, entry)
        st.unpack(raw, h1_pk[int(h1_idx[t])], 1, h1_close[t], decision[t], d, entry)
        st.unpack(raw, h4_pk[int(h4_idx[t])], 2, h4_close[t], decision[t], d, entry)
        return raw

    def hook(t, levels, eqh, eql, pdh, pdl, pwh, pwl, atr, c):
        d = trend[t]
        # New setups: levels watched at the previous close that this candle touched from their own side.
        for lid, price, role, lstate, wick in state["prev"]:
            if L[t] <= price <= H[t] and role * (O[t] - price) >= 0:
                state["active"].append({"id": state["next"], "level": lid, "price": price, "side": role, "state": lstate,
                                        "touch": t, "wick": wick, "fired": set()})
                state["next"] += 1
        keep = []
        for s in state["active"]:
            fired, done = step(s, t, O, H, L, C)
            for trig in fired:
                if s["side"] == d and not isna(atr):
                    inval = s["ext"] if isna(s["wick"]) else (min(s["ext"], s["wick"]) if d == 1 else max(s["ext"], s["wick"]))
                    rows.append({"bar": t, "setup": _setup_name(s["state"]), "trigger": trig, "side": d, "uid": s["id"],
                                 "level_price": s["price"], "entry": c, "inval": inval, "atr": atr, "order": "market",
                                 "raw": raw_targets(t, levels, eqh, eql, pdh, pdl, pwh, pwl, d, c)})
            if not done:
                keep.append(s)
        state["active"] = keep
        # Resting limits for the touch trigger: the nearest qualifying level on the trend side, per setup.
        if d != 0 and not isna(atr):
            for name, lstate in SETUPS.items():
                best = None
                for lv in levels:
                    if (lv.state == lstate and st.first_touch(lv) and not lv.in_contact and lv.role == d
                            and d * (c - lv.price) > 0 and (best is None or abs(c - lv.price) < abs(c - best.price))):
                        best = lv
                if best is not None:
                    inval = best.price if isna(best.wick) else best.wick
                    rows.append({"bar": t, "setup": name, "trigger": "touch", "side": d, "uid": best.id,
                                 "level_price": best.price, "entry": best.price, "inval": inval, "atr": atr, "order": "limit",
                                 "raw": raw_targets(t, levels, eqh, eql, pdh, pdl, pwh, pwl, d, best.price)})
        state["prev"] = watch(levels)

    eng, _ = structure.run(m15, core, hook=hook)
    return pd.DataFrame(rows), eng


def _setup_name(lstate: int) -> str:
    return "A_pullback" if lstate == ST_FRESH else "B_flip"


def plan(row, stop: str, target: str) -> tuple[float, float]:
    """Stop and target for one candidate (NaN when no valid target exists).

    Stops: "structural" (invalidation + max(tick, 0.2 ATR)), "structural_floor" (that, at least 1 ATR),
    "atrK" (K ATR from the entry), "structural_bufK" (K ATR beyond the invalidation).
    Targets: "tp2" (website engine), "2R" / "rX" (X times the risk), "near" (the nearest opposing
    structure the website engine lists, at least 0.25 R away)."""
    d, entry, inval, atr = row.side, row.entry, row.inval, row.atr
    edge = min(entry, inval) if d == 1 else max(entry, inval)
    struct_stop = st.target_round(edge - d * max(TICK, atr * st.STOP_BUFFER_ATR), TICK, d)
    dist = d * (entry - struct_stop)
    if stop == "structural_floor":
        dist = max(dist, atr)
    elif stop.startswith("atr"):
        dist = float(stop[3:]) * atr
    elif stop.startswith("structural_buf"):
        dist = d * (entry - (edge - d * float(stop[14:]) * atr))
    if target.startswith("r") or target == "near":
        s = st.target_round(entry - d * dist, TICK, d)
        risk = d * (entry - s)
        if not risk > 0:
            return math.nan, math.nan
        if target == "near":
            if not isinstance(row.raw, list):
                return math.nan, math.nan
            for price, rr, *_ in st.target_candidates(list(row.raw), d, entry, risk, atr, TICK):
                if rr >= 0.25:
                    return s, price
            return math.nan, math.nan
        return s, st.target_round(entry + d * float(target[1:]) * risk, TICK, d)
    if target == "2R":
        s = st.target_round(entry - d * dist, TICK, d)
        risk = d * (entry - s)
        return (s, st.target_round(entry + d * 2.0 * risk, TICK, d)) if risk > 0 else (math.nan, math.nan)
    if not isinstance(row.raw, list):   # no fresh 1H/4H snapshot at this close
        return math.nan, math.nan
    p = st.structure_targets(list(row.raw), d, entry, inval, atr, TICK, stop_distance=dist if stop == "structural_floor" else 0.0)
    return (p["stop"], p["tp2"]) if p["reason"] == "" else (math.nan, math.nan)


def variant_signals(cand: pd.DataFrame, n: int, setup: str, trigger: str, stop: str, target: str) -> pd.DataFrame:
    """A strategy.simulate signal frame for one variant (one row per 15m candle)."""
    c = cand[(cand["setup"] == setup) & (cand["trigger"] == trigger)]
    cols = {"signal": np.zeros(n, bool), "dir": np.zeros(n), "level_id": np.full(n, np.nan), "entry": np.full(n, np.nan),
            "stop": np.full(n, np.nan), "tp1": np.full(n, np.nan), "tp2": np.full(n, np.nan), "tp3": np.full(n, np.nan)}
    order = np.array(["limit" if trigger == "touch" else "market"] * n, dtype=object)
    taken = set()
    for r in c.itertuples(index=False):
        if r.bar in taken:   # two setups firing on one candle: the first (nearest for limits) wins
            continue
        s, tp = plan(r, stop, target)
        if isna(s) or isna(tp):
            continue
        taken.add(r.bar)
        i = r.bar
        cols["signal"][i], cols["dir"][i], cols["level_id"][i] = True, r.side, r.uid
        cols["entry"][i], cols["stop"][i], cols["tp2"][i] = r.entry, s, tp
    out = pd.DataFrame(cols)
    out["order"] = order
    return out


# ── Per-trade features: what the report measures ─────────────────────────

def features(m15: pd.DataFrame, eng: pd.DataFrame, ctx: pd.DataFrame, regimes: tuple[float, float]) -> pd.DataFrame:
    """Context at each 15m close, for either trade side (suffix _1 long, _-1 short)."""
    t = m15["time"]
    ldn, ny = t.dt.tz_convert("Europe/London").dt.hour, t.dt.tz_convert("America/New_York").dt.hour
    session = np.where((ldn >= 8) & (ldn < 12), "London", np.where((ny >= 8) & (ny < 17), "New York",
                       np.where((ldn >= 12) & (ldn < 17), "London", "Asia / off-hours")))
    lo, hi = regimes
    vol = np.where(ctx["atr_pct"] < lo, "low", np.where(ctx["atr_pct"] < hi, "normal", "high"))
    f = pd.DataFrame({"session": session, "vol_regime": vol, "h1": ctx["h1"].to_numpy(), "m15": eng["trend_score"].to_numpy(),
                      "year": t.dt.year.to_numpy()}, index=m15.index)
    for d, sfx, side in ((1, "bull", "_1"), (-1, "bear", "_-1")):
        age = eng[f"{sfx}_sweep_age"].to_numpy()
        f[f"bias{side}"] = np.sign(eng["trend_score"].to_numpy()) == d
        f[f"recent_bos{side}"] = eng[f"struct_ok_{sfx}"].to_numpy(bool)
        f[f"room{side}"] = eng[f"space_ok_{sfx}"].to_numpy(bool)
        f[f"sweep_recent{side}"] = (age >= 0) & (age <= 8)
        f[f"rejection_recent{side}"] = eng[f"rej_ok_{sfx}"].to_numpy(bool)
        f[f"volume{side}"] = eng[f"vol_ok_{sfx}"].to_numpy(bool)
        f[f"score_75{side}"] = eng[f"score_{sfx}"].to_numpy(float) >= 75
    f["killzone_1"] = f["killzone_-1"] = (eng["in_london"] | eng["in_ny"]).to_numpy(bool)
    return f


def label_trades(trades: pd.DataFrame, feat: pd.DataFrame) -> pd.DataFrame:
    """Attach the signal candle's context to each trade."""
    if trades.empty:
        return trades
    out = trades.copy()
    b, d = out["signal_bar"].to_numpy(int), out["dir"].to_numpy(int)
    row = feat.iloc[b].reset_index(drop=True)
    out["session"], out["vol_regime"], out["year"] = row["session"].to_numpy(), row["vol_regime"].to_numpy(), row["year"].to_numpy()
    h1 = np.sign(row["h1"].to_numpy()) * d
    out["h1_context"] = np.where(h1 > 0, "confirm", np.where(h1 < 0, "contradict", "neutral"))
    m15 = np.sign(row["m15"].to_numpy()) * d
    out["m15_bias"] = np.where(m15 > 0, "with trend", np.where(m15 < 0, "against (pullback)", "neutral"))
    for c in CHECKS:
        out[c] = np.where(d == 1, row[f"{c}_1"].to_numpy(bool), row[f"{c}_-1"].to_numpy(bool))
    return out


# ── The study ────────────────────────────────────────────────────────────

def variants(stops: list | None = None, targets: list | None = None) -> list[tuple]:
    return list(itertools.product(SETUPS, TRIGGERS, stops or STOPS, targets or TARGETS))


def evaluate(load: tuple[str, str], periods: dict, stops: list | None = None,
             targets: list | None = None) -> tuple[pd.DataFrame, dict, dict]:
    """Every variant on `periods`; returns the scores, the labelled net trades per variant and the
    arrays the Monte Carlo needs."""
    history = data.load("M15", *load)
    m15 = history[history["time"] >= pd.Timestamp(periods[next(iter(periods))][0], tz="UTC") - pd.Timedelta(days=120)].reset_index(drop=True)
    p = st.StrategyParams(swing_len=SWING, flip_rules="4.1")
    h1, h4 = st.h1_inputs(m15, p), st.h4_inputs(m15, p)
    ctx = context(m15, history)
    cand, eng = candidates(m15, ctx, h1, h4)
    train_mask = (m15["time"] >= pd.Timestamp(PERIODS["train"][0], tz="UTC")) & (m15["time"] < pd.Timestamp(PERIODS["train"][1], tz="UTC"))
    ref = ctx.loc[train_mask, "atr_pct"] if train_mask.any() else ctx["atr_pct"]
    feat = features(m15, eng, ctx, tuple(np.nanquantile(ref, [1 / 3, 2 / 3])))
    rows, trades = [], {}
    for v in variants(stops, targets):
        sig = variant_signals(cand, len(m15), *v)
        row = dict(zip(("setup", "trigger", "stop", "target"), v))
        for period, (a, b) in periods.items():
            weeks = (pd.Timestamp(b) - pd.Timestamp(a)).days / 7
            for cost, broker in COSTS.items():
                tr, _ = st.simulate(m15, sig, a, b, broker)
                s = metrics.summarize(tr, weeks)
                keys = ("trades", "win_rate", "expectancy_R", "profit_factor", "max_drawdown_R", "sqn") if cost == "net" else ("expectancy_R",)
                for k in keys:
                    row[f"{period}_{cost}_{k}"] = s.get(k, np.nan)
                if cost == "net":
                    trades[(v, period)] = label_trades(tr, feat)
                    if len(tr):
                        ci = metrics.bootstrap_mean(tr, level=1 - 0.10 / len(SETUPS))
                        row[f"{period}_net_ci_low"] = ci["low"]
        rows.append(row)
    env = {"m15": m15, "trend": ctx["trend"].to_numpy(int), "atr": eng["atr"].to_numpy(float)}
    return pd.DataFrame(rows), trades, env


def random_entries(env: dict, real: pd.DataFrame, period: tuple[str, str], rng: np.random.Generator) -> np.ndarray:
    """Average net R of MC_RUNS random-entry runs with the real trades' count and risk geometry."""
    m15, trend, atr = env["m15"], env["trend"], env["atr"]
    if len(real) < 2:
        return np.array([])
    c = m15["close"].to_numpy(float)
    t = m15["time"]
    lo, hi = int(t.searchsorted(pd.Timestamp(period[0], tz="UTC"))), int(t.searchsorted(pd.Timestamp(period[1], tz="UTC")))
    bars = np.arange(lo, hi)
    bars = bars[(trend[bars] != 0) & (atr[bars] > 0)]
    sb = real["signal_bar"].to_numpy(int)
    risk_atr = real["risk"].to_numpy(float) / atr[sb]
    rr = real["dir"].to_numpy(float) * (real["tp2"].to_numpy(float) - real["entry"].to_numpy(float)) / real["risk"].to_numpy(float)
    n = len(m15)
    out = []
    for _ in range(MC_RUNS):
        pick = np.sort(rng.choice(bars, size=min(len(real), len(bars)), replace=False))
        j = rng.integers(0, len(real), size=len(pick))
        d = trend[pick].astype(float)
        risk = risk_atr[j] * atr[pick]
        cols = {"signal": np.zeros(n, bool), "dir": np.zeros(n), "level_id": np.full(n, np.nan), "entry": np.full(n, np.nan),
                "stop": np.full(n, np.nan), "tp1": np.full(n, np.nan), "tp2": np.full(n, np.nan), "tp3": np.full(n, np.nan)}
        cols["signal"][pick], cols["dir"][pick], cols["level_id"][pick] = True, d, np.arange(len(pick))
        cols["entry"][pick] = c[pick]
        cols["stop"][pick] = st.side_round(c[pick] - d * risk, TICK, d)
        cols["tp2"][pick] = st.side_round(c[pick] + d * rr[j] * risk, TICK, d)
        sig = pd.DataFrame(cols)
        sig["order"] = "market"
        tr, _ = st.simulate(m15, sig, *period, COSTS["net"])
        out.append(tr["R"].mean() if len(tr) else np.nan)
    return np.array(out)


def resample_years(real: pd.DataFrame, weeks: float, rng: np.random.Generator) -> dict:
    """One year's worth of the real trades, redrawn in random order MC_YEARS times."""
    r = real["R"].to_numpy(float)
    if len(r) < 2:
        return {}
    per_year = max(1, int(round(len(r) / weeks * 52)))
    draws = r[rng.integers(0, len(r), size=(MC_YEARS, per_year))]
    totals = draws.sum(1)
    eq = np.cumsum(draws, 1)
    dd = (np.maximum.accumulate(np.maximum(eq, 0), 1) - eq).max(1)
    return {"trades_per_year": per_year, "year_R_median": float(np.median(totals)), "year_R_p5": float(np.quantile(totals, 0.05)),
            "year_R_p95": float(np.quantile(totals, 0.95)), "losing_year_chance": float((totals < 0).mean()),
            "max_drawdown_R_median": float(np.median(dd)), "max_drawdown_R_p95": float(np.quantile(dd, 0.95))}


def select(scores: pd.DataFrame) -> pd.DataFrame:
    """Per setup, the variant with the highest training SQN among those with enough training trades."""
    ok = scores[scores["train_net_trades"] >= MIN_TRADES]
    return ok.sort_values("train_net_sqn", ascending=False).groupby("setup", sort=False).head(1).reset_index(drop=True)


def verdict(row: pd.Series) -> str:
    n, e = row.get("val_net_trades", 0), row.get("val_net_expectancy_R")
    if not n >= MIN_TRADES:
        return "inconclusive"
    if not e > 0:
        return "rejected"
    if row.get("val_net_ci_low", -1) > 0 and row.get("val_net_profit_factor", 0) >= metrics.MIN_PROFIT_FACTOR:
        return "candidate"
    return "watch"


def breakdown(tr: pd.DataFrame, column: str) -> pd.DataFrame:
    if tr.empty:
        return pd.DataFrame()
    g = tr.groupby(column)["R"]
    return pd.DataFrame({"trades": g.size(), "win_rate": g.apply(lambda r: (r > 0).mean()), "avg_R": g.mean(),
                         "total_R": g.sum()}).round(3)


def check_table(tr: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in CHECKS:
        on, off = tr.loc[tr[c], "R"], tr.loc[~tr[c], "R"]
        rows.append({"check": c, "trades_with": len(on), "avg_R_with": on.mean(), "trades_without": len(off),
                     "avg_R_without": off.mean(), "difference": on.mean() - off.mean()})
    return pd.DataFrame(rows).set_index("check").round(3)


def monte_carlo(chosen: pd.DataFrame, trades: dict, env: dict) -> pd.DataFrame:
    rng = np.random.default_rng(MC_SEED)
    rows = []
    for _, r in chosen.iterrows():
        v = (r["setup"], r["trigger"], r["stop"], r["target"])
        for period, (a, b) in PERIODS.items():
            real = trades[(v, period)]
            rand = random_entries(env, real, (a, b), rng)
            avg = real["R"].mean() if len(real) else np.nan
            row = {"setup": r["setup"], "period": period, "real_avg_R": avg,
                   "random_avg_R_mean": np.nanmean(rand) if len(rand) else np.nan,
                   "random_p5": np.nanquantile(rand, 0.05) if len(rand) else np.nan,
                   "random_p95": np.nanquantile(rand, 0.95) if len(rand) else np.nan,
                   "share_random_at_least_real": float(np.mean(rand >= avg)) if len(rand) else np.nan}
            row.update(resample_years(real, (pd.Timestamp(b) - pd.Timestamp(a)).days / 7, rng))
            rows.append(row)
    return pd.DataFrame(rows)


S4_TITLE = "S4 — GSE's two setups, tested separately (1D + 4H trend, 1H context, 15m entry)"
S4_ABOUT = ("Four entry triggers, two structural stops, two targets: 32 variants, all shown.")
S5_TITLE = "S5 — GSE's two setups with wider stops and nearer targets"
S5_ABOUT = ("The S4 setups and triggers with stops of 2 / 3 / 5 ATR from the entry or 1 ATR beyond the structural "
            "invalidation, and targets of 0.25 / 0.5 / 0.75 / 1 R or the nearest opposing structure (at least 0.25 R): "
            "160 variants, all shown. A fixed target of X R needs a win rate above 1 / (1 + X) before costs to break "
            "even (0.25 R: 80%, 0.5 R: 67%, 0.75 R: 57%, 1 R: 50%); costs raise it further.")


def run_wide_study(out_dir: Path | None = None) -> Path:
    return run_study(out_dir, "S5", S5_STOPS, S5_TARGETS, S5_TITLE, S5_ABOUT)


def run_study(out_dir: Path | None = None, name: str = "S4", stops: list | None = None, targets: list | None = None,
              title: str = S4_TITLE, about: str = S4_ABOUT) -> Path:
    scores, trades, env = evaluate(LOADS["discovery"], PERIODS, stops, targets)
    chosen = select(scores)
    chosen["verdict"] = [verdict(r) for _, r in chosen.iterrows()]
    mc = monte_carlo(chosen, trades, env)
    out_dir = out_dir or data.ROOT / "results" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(out_dir / "variants.csv", index=False)
    mc.to_csv(out_dir / "monte_carlo.csv", index=False)
    chosen.to_csv(out_dir / "selected.csv", index=False)
    for _, r in chosen.iterrows():
        v = (r["setup"], r["trigger"], r["stop"], r["target"])
        for period in PERIODS:
            trades[(v, period)].to_csv(out_dir / f"trades_{r['setup']}_{period}.csv", index=False)
    manifest = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    prov = {"git": experiments._git(), "dataset_sha256": manifest["sha256"], "variants": len(scores), "setups": list(SETUPS),
            "triggers": TRIGGERS, "stops": stops or STOPS, "targets": targets or TARGETS, "periods": PERIODS,
            "status": experiments.PROVISIONAL}
    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(report(scores, chosen, trades, mc, prov, title, about), encoding="utf-8")
    return out_dir


def report(scores: pd.DataFrame, chosen: pd.DataFrame, trades: dict, mc: pd.DataFrame, prov: dict,
           title: str = S4_TITLE, about: str = S4_ABOUT) -> str:
    md = experiments._md
    cols = ["setup", "trigger", "stop", "target"]
    show = cols + [f"{p}_{k}" for p in PERIODS for k in ("net_trades", "net_win_rate", "net_expectancy_R", "net_profit_factor",
                                                         "net_max_drawdown_R", "gross_expectancy_R")]
    lines = [
        f"# {title}", "",
        f"> {prov['status']}", "",
        "Setup A: first touch of a fresh 15m level after a pullback against the 1D + 4H trend. Setup B: first touch "
        f"of a confirmed 15m flipped level, continuing the trend. {about} Train 2016–2018 picks one per setup; "
        "validation 2019–2022 judges it. "
        "OANDA bid/ask + 0.10 slippage (net); gross = mid prices, no slippage. Rules: gse_research/setups.py.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''} · dataset `{prov['dataset_sha256'][:12]}…`", "",
        "## Every variant", "", md(scores[show].set_index("setup").round(3)), "",
        "## Selected on train, judged on validation", "",
        md(chosen[cols + ["train_net_trades", "train_net_expectancy_R", "train_net_sqn", "val_net_trades", "val_net_win_rate",
                          "val_net_expectancy_R", "val_net_profit_factor", "val_net_ci_low", "val_gross_expectancy_R",
                          "verdict"]].set_index("setup").round(3)) if len(chosen) else "No variant had enough training trades.", "",
        "## Monte Carlo", "",
        f"Random entries: {MC_RUNS} runs with the same number of entries at random 15m closes in the trend's direction, "
        "with stop and target sizes drawn from the real trades. share_random_at_least_real is the share of random runs "
        "that did as well as the setup (small = the entries carry information). Trade resampling: one year of the real "
        f"trades redrawn {MC_YEARS:,} times (yearly R, losing-year chance, drawdowns in R).", "",
        md(mc.set_index("setup").round(3)) if len(mc) else "No selected variant.", ""]
    for _, r in chosen.iterrows():
        v = (r["setup"], r["trigger"], r["stop"], r["target"])
        lines += [f"## {r['setup']} ({r['trigger']}, {r['stop']}, {r['target']}): where it does better or worse", "",
                  "Net R per trade. Measured on both periods; nothing here was used to pick the variant.", ""]
        for period in PERIODS:
            tr = trades[(v, period)]
            if tr.empty:
                continue
            lines += [f"### {period}", ""]
            for col, title in (("year", "By year"), ("session", "By session (signal candle)"), ("vol_regime", "By volatility regime (daily ATR %, train terciles)"),
                               ("h1_context", "By 1H context"), ("m15_bias", "By 15m bias at the signal")):
                lines += [f"**{title}**", "", md(breakdown(tr, col)), ""]
            lines += ["**GSE confluence checks: trades with the check against trades without**", "", md(check_table(tr)), ""]
    cand = chosen[chosen["verdict"] == "candidate"] if len(chosen) else chosen
    lines += ["## Conclusion", "",
              (f"**{len(cand)} setup(s) pass validation.** No untouched period is left for a final test: 2023+ was spent on "
               "X1 and 2012–2015 on G1. Next: a forward test on live data, or the owner's decision on 2023–2026."
               if len(cand) else
               "**Neither setup passes validation.** The variant training picked for each setup did not make money after "
               "costs on 2019–2022 with enough evidence."), "",
              "## Limitations", "",
              "- Trend from GSE's bias on 1D and 4H; other trend definitions could differ.",
              "- One trade at a time per variant; a trade open blocks later signals.",
              "- Provisional until the parity gate (pivot tie rule, OANDA versus BlackBull).", ""]
    return "\n".join(lines)
