"""Study G1: a broad search for any profitable XAU/USD rule, judged on a holdout no study has touched.

Families of rules (none needs TradingView, so OANDA data before 2016 is usable):
- donchian: a close through the highest high / lowest low of the previous N candles (trend breakout);
- ema_cross: a fast EMA crossing a slow EMA (trend);
- rsi2: RSI(2) at an extreme, optionally only with the 200 EMA trend (short-term mean reversion);
- asian_breakout (15m): the first close beyond the London 00:00-07:00 range, 07:00 to a cut-off;
- drift: holding one side from a fixed New York hour for 1-8 hours (time-of-day seasonality);
- big_bar: after a candle of k ATR or more, with it or against it;
- gse_break: GSE's confirmed breaks of structure (BOS/CHoCH), with them or against them;
- gse_sweep: GSE's qualified liquidity sweeps, traded as reversals;
- prev_day: a close through the previous day's high or low, with it or against it;
- ny_open: the first close beyond the New York 08:00 opening range (30 or 60 minutes), until 12:00.
Each crossed with sides (long, short, both), a session filter, a daily-trend filter and exits:
fixed stop and target, an ATR trail, a time exit, the family's own exit, a range stop (Asian breakout).

Entry: a market order at the next candle's open after the signal close. Fills on OANDA bid/ask
with 0.10 slippage on market orders and stops; a candle that opens through an exit fills at its
open; a candle reaching stop and target counts as a stop. R is per planned risk (the stop
distance, or 1 ATR for rules without a stop).

PRE-REGISTERED (results/G1/rule.json, committed before the run):
1. Discovery: train 2016-2018 and validation 2019-2022, every rule, after costs.
2. Finalists: rules with >= MIN_TRAIN train and >= MIN_VAL validation trades, positive after costs and
   profit factor >= 1.1 in both periods, ranked by the lower of the two SQNs; the top FINALISTS.
3. Holdout 2012-2015, run once on the finalists only (the shards never load it). A rule passes with
   >= 50 holdout trades, positive expectancy, profit factor >= 1.2, a 90% weekly-block bootstrap lower
   bound above zero after the FINALISTS-way correction, and at least 3 of the 4 years positive.
2023+ (spent on X1) is not used.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

from . import data, experiments, metrics, structure

PERIODS = {"train": ("2016-01-01", "2019-01-01"), "val": ("2019-01-01", "2023-01-01")}
HOLDOUT = ("2012-01-01", "2016-01-01")
LOADS = {"discovery": ("2015-01-01", "2023-01-04"), "holdout": ("2011-01-01", "2016-01-05")}
SLIP = 0.10
MIN_TRAIN, MIN_VAL, FINALISTS = 50, 70, 10
SIDES = ["long", "short", "both"]

# name: (stop ATR or 0 = none, target R or 0 = none, trail ATR or 0, trail start R, time exit candles or 0,
#        family exit on/off). Rules without a stop measure R in ATR at entry.
EXITS = {
    "s1.5_t1.5": (1.5, 1.5, 0.0, 0.0, 0, False),
    "s2_t3": (2.0, 3.0, 0.0, 0.0, 0, False),
    "s3_trail3": (3.0, 0.0, 3.0, 0.0, 0, False),
    "s2_time10": (2.0, 0.0, 0.0, 0.0, 10, False),
    "family_s3": (3.0, 0.0, 0.0, 0.0, 0, True),
}


# ── Prices and indicators per chart ─────────────────────────────────────

def chart_arrays(m15: pd.DataFrame, tf: str) -> dict:
    c = m15 if tf == "15m" else data.aggregate(m15, tf)
    c = c[c["candles"] > 0].reset_index(drop=True) if "candles" in c else c.reset_index(drop=True)
    o, h, l, cl = (c[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t = c["time"]
    ny = t.dt.tz_convert("America/New_York")
    ldn = t.dt.tz_convert("Europe/London")
    d1 = data.aggregate(m15, "1D")
    d1 = d1.assign(ema50=structure.pine_ema(d1["close"].to_numpy(float), 50))
    d1_ema = data.align(c, d1, ["ema50"], at="close")["ema50"].to_numpy(float)
    d1_close = data.align(c, d1, ["close"], at="close")["close"].to_numpy(float)
    prev = data.align(c, d1, ["high", "low"], at="open")
    out = {"frame": c, "tf": tf, "time": t, "o": o, "h": h, "l": l, "c": cl,
           "atr": structure.pine_atr(h, l, cl, 14), "year": t.dt.year.to_numpy(),
           "ny_hour": (ny.dt.hour + ny.dt.minute / 60).to_numpy(float),
           "ldn_hour": (ldn.dt.hour + ldn.dt.minute / 60).to_numpy(float),
           "ldn_date": ldn.dt.date.to_numpy(),
           "killzone": (((ldn.dt.hour >= 8) & (ldn.dt.hour < 17)) | ((ny.dt.hour >= 8) & (ny.dt.hour < 17))).to_numpy(),
           "ny_date": (t.dt.tz_convert("America/New_York")).dt.date.to_numpy(),
           "pdh": prev["high"].to_numpy(float), "pdl": prev["low"].to_numpy(float),
           "d1_trend": np.sign(d1_close - d1_ema)}
    for side in ("bid", "ask"):
        for k in ("open", "high", "low", "close"):
            out[f"{side}_{k}"] = c[f"{side}_{k}"].to_numpy(float)
    return out


def rolling_prev(x: np.ndarray, n: int, fn) -> np.ndarray:
    """fn over the previous n values (excluding the current one)."""
    s = pd.Series(x).shift(1).rolling(n, min_periods=n)
    return (s.max() if fn == "max" else s.min()).to_numpy()


def rsi(c: np.ndarray, n: int) -> np.ndarray:
    d = np.diff(c, prepend=np.nan)
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    up[0] = dn[0] = 0.0
    au, ad = structure.pine_rma(up, n), structure.pine_rma(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ad == 0, 100.0, 100 - 100 / (1 + au / ad))


def cross_up(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    prev = np.r_[False, (a[:-1] <= b[:-1])]
    return (a > b) & prev


# ── Signal families: (direction at each close, exit-long, exit-short, risk distance or None) ──

def sig_donchian(ch: dict, n: int):
    hi, lo = rolling_prev(ch["h"], n, "max"), rolling_prev(ch["l"], n, "min")
    c = ch["c"]
    up, dn = cross_up(c, hi), cross_up(-c, -lo)
    m = max(2, n // 2)
    ex_l, ex_s = c < rolling_prev(ch["l"], m, "min"), c > rolling_prev(ch["h"], m, "max")
    return np.where(up, 1, np.where(dn, -1, 0)), ex_l, ex_s, None


def sig_ema(ch: dict, f: int, s: int):
    a, b = structure.pine_ema(ch["c"], f), structure.pine_ema(ch["c"], s)
    up, dn = cross_up(a, b), cross_up(b, a)
    return np.where(up, 1, np.where(dn, -1, 0)), dn, up, None


def sig_rsi2(ch: dict, th: float, trend: bool):
    r = rsi(ch["c"], 2)
    long_, short_ = r < th, r > 100 - th
    if trend:
        e = structure.pine_ema(ch["c"], 200)
        long_, short_ = long_ & (ch["c"] > e), short_ & (ch["c"] < e)
    return np.where(long_, 1, np.where(short_, -1, 0)), r > 70, r < 30, None


def sig_asian(ch: dict, buffer_atr: float, end_hour: float):
    lh, date = ch["ldn_hour"], ch["ldn_date"]
    df = pd.DataFrame({"date": date, "h": np.where(lh < 7, ch["h"], np.nan), "l": np.where(lh < 7, ch["l"], np.nan)})
    g = df.groupby("date")
    # The range is complete once 07:00 London has passed; entries start then.
    rh, rl = g["h"].transform("max").to_numpy(), g["l"].transform("min").to_numpy()
    c, buf = ch["c"], buffer_atr * np.nan_to_num(ch["atr"])
    window = (lh >= 7) & (lh < end_hour)
    up, dn = window & (c > rh + buf), window & (c < rl - buf)
    first = pd.Series(up | dn).groupby(date).cumsum().to_numpy() == 1
    d = np.where(up & first, 1, np.where(dn & first, -1, 0))
    late = lh >= 20
    risk = np.where(d == 1, c - rl, np.where(d == -1, rh - c, np.nan))
    return d, late, late, risk


def sig_ny_open(ch: dict, minutes: int, end_hour: float = 12.0):
    nh, date = ch["ny_hour"], ch["ny_date"]
    in_range = (nh >= 8) & (nh < 8 + minutes / 60)
    df = pd.DataFrame({"date": date, "h": np.where(in_range, ch["h"], np.nan), "l": np.where(in_range, ch["l"], np.nan)})
    g = df.groupby("date")
    rh, rl = g["h"].transform("max").to_numpy(), g["l"].transform("min").to_numpy()
    c = ch["c"]
    window = (nh >= 8 + minutes / 60) & (nh < end_hour)
    up, dn = window & (c > rh), window & (c < rl)
    first = pd.Series(up | dn).groupby(date).cumsum().to_numpy() == 1
    d = np.where(up & first, 1, np.where(dn & first, -1, 0))
    late = nh >= 16
    risk = np.where(d == 1, c - rl, np.where(d == -1, rh - c, np.nan))
    return d, late, late, risk


def sig_prev_day(ch: dict, fade: bool):
    c = ch["c"]
    up, dn = cross_up(c, ch["pdh"]), cross_up(-c, -ch["pdl"])
    d = np.where(up, 1, np.where(dn, -1, 0))
    return (-d if fade else d), np.zeros(len(d), bool), np.zeros(len(d), bool), None


def sig_drift(ch: dict, hour: int):
    # Enter at the open of the 1H candle that starts at `hour` New York: the signal is the close before it.
    nxt = np.r_[ch["ny_hour"][1:], np.nan]
    return np.where(nxt == hour, 1, 0), np.zeros(len(nxt), bool), np.zeros(len(nxt), bool), None


def sig_big_bar(ch: dict, k: float, fade: bool):
    rng, body = ch["h"] - ch["l"], ch["c"] - ch["o"]
    prev_atr = np.r_[np.nan, ch["atr"][:-1]]
    big = (rng >= k * prev_atr) & (np.abs(body) >= 0.5 * rng)
    d = np.where(big, np.sign(body), 0).astype(int)
    return (-d if fade else d), np.zeros(len(d), bool), np.zeros(len(d), bool), None


def sig_gse(ch: dict, lookback: int, kind: str, fade: bool = False):
    out, _ = structure.run(ch["frame"], structure.CoreParams(swing_len=lookback))
    if kind == "break":
        up = (out["bos_bull"] | out["choch_bull"]).to_numpy(bool)
        dn = (out["bos_bear"] | out["choch_bear"]).to_numpy(bool)
        d = np.where(up, 1, np.where(dn, -1, 0))
        d = -d if fade else d
    else:
        d = np.where(out["bull_sweep_q"].to_numpy(bool), 1, np.where(out["bear_sweep_q"].to_numpy(bool), -1, 0))
    return d, np.zeros(len(d), bool), np.zeros(len(d), bool), None


FAMILIES = {
    "donchian": (["1H", "4H", "1D"], [{"n": n} for n in (10, 20, 55, 100, 200)], sig_donchian),
    "ema_cross": (["1H", "4H", "1D"], [{"f": f, "s": s} for f, s in ((5, 20), (10, 50), (20, 100), (50, 200))], sig_ema),
    "rsi2": (["15m", "1H", "4H"], [{"th": th, "trend": tr} for th in (5, 10, 20) for tr in (False, True)], sig_rsi2),
    "asian_breakout": (["15m"], [{"buffer_atr": b, "end_hour": e} for b in (0.0, 0.1) for e in (10.0, 12.0)], sig_asian),
    "drift": (["1H"], [{"hour": h} for h in range(24)], sig_drift),
    "big_bar": (["15m", "1H", "4H"], [{"k": k, "fade": f} for k in (2.0, 3.0) for f in (False, True)], sig_big_bar),
    "gse_break": (["1H", "4H"], [{"lookback": lb, "kind": "break", "fade": f} for lb in (5, 10) for f in (False, True)], sig_gse),
    "gse_sweep": (["15m", "1H", "4H"], [{"lookback": lb, "kind": "sweep"} for lb in (5, 10)], sig_gse),
    "prev_day": (["15m", "1H"], [{"fade": f} for f in (False, True)], sig_prev_day),
    "ny_open": (["15m"], [{"minutes": m} for m in (30, 60)], sig_ny_open),
}
NO_FAMILY_EXIT = ("big_bar", "gse_break", "gse_sweep", "prev_day")
RANGE_STOP = ("asian_breakout", "ny_open")
DRIFT_HOLDS = [1, 2, 4, 8]


def rules() -> list[dict]:
    """Every rule of the search, in a fixed order (shards take every n-th)."""
    out = []
    for fam, (tfs, params, _) in FAMILIES.items():
        for tf, p in itertools.product(tfs, params):
            if fam == "drift":
                for hold, side in itertools.product(DRIFT_HOLDS, ["long", "short"]):
                    out.append({"family": fam, "tf": tf, "params": p, "side": side, "session": False, "d1": False,
                                "exit": f"time{hold}"})
                continue
            exits = list(EXITS) + (["range_t1", "range_t2"] if fam in RANGE_STOP else [])
            for side, sess, d1, ex in itertools.product(SIDES, (False, True), (False, True), exits):
                if ex == "family_s3" and fam in NO_FAMILY_EXIT:
                    continue  # no family exit: covered by the time exit
                out.append({"family": fam, "tf": tf, "params": p, "side": side, "session": sess, "d1": d1, "exit": ex})
    return out


def exit_spec(name: str) -> tuple:
    if name.startswith("time"):
        return (0.0, 0.0, 0.0, 0.0, int(name[4:]), False)
    if name.startswith("range_t"):
        return (-1.0, float(name[7:]), 0.0, 0.0, 0, True)   # stop at the other side of the range; flat by the family's hour
    return EXITS[name]


# ── The trade simulator ─────────────────────────────────────────────────

@njit(cache=True)
def simulate(sig, ex_l, ex_s, risk_px, bo, bh, bl, bc, ao, ah, al, ac, atr, start, end,
             stop_k, target_r, trail_k, trail_start, max_bars, family_exit, slip):
    """Market entries at the next open after a signal close in [start, end); one position at a time.
    Returns (entry signal bar, exit bar, side, R) per trade, R per planned risk."""
    n = len(sig)
    out_sig = np.empty(n, np.int64)
    out_exit = np.empty(n, np.int64)
    out_side = np.empty(n, np.int64)
    out_r = np.empty(n, np.float64)
    k = 0
    pos = 0
    pend_entry = 0
    pend_exit = False
    sig_bar = 0
    entry_bar = 0
    fill = 0.0
    stop = 0.0
    tp = 0.0
    unit = 0.0
    best = 0.0
    peak = 0.0
    pend_unit = 0.0
    for t in range(start, n):
        # 1. Orders from the last close.
        if pend_exit and pos != 0:
            px = (bo[t] - slip) if pos == 1 else (ao[t] + slip)
            out_sig[k] = sig_bar; out_exit[k] = t; out_side[k] = pos; out_r[k] = pos * (px - fill) / unit
            k += 1
            pos = 0
        pend_exit = False
        if pend_entry != 0:
            pos = pend_entry
            pend_entry = 0
            fill = (ao[t] + slip) if pos == 1 else (bo[t] - slip)
            unit = pend_unit
            entry_bar = t
            stop = fill - pos * unit if stop_k != 0.0 else -pos * 1e18
            tp = fill + pos * target_r * unit if target_r > 0.0 else pos * 1e18
            best = (bc[t] if pos == 1 else ac[t])
            peak = 0.0
        # 2. Stop and target during the candle (a gap through fills at the open; stop first).
        if pos != 0:
            xo, xh, xl = (bo[t], bh[t], bl[t]) if pos == 1 else (ao[t], ah[t], al[t])
            adverse = xl if pos == 1 else xh
            favour = xh if pos == 1 else xl
            px = np.nan
            if t > entry_bar and pos * (xo - stop) <= 0:
                px = xo - pos * slip
            elif t > entry_bar and pos * (xo - tp) >= 0:
                px = xo
            elif pos * (adverse - stop) <= 0:
                px = stop - pos * slip
            elif pos * (favour - tp) >= 0:
                px = tp
            if not np.isnan(px):
                out_sig[k] = sig_bar; out_exit[k] = t; out_side[k] = pos; out_r[k] = pos * (px - fill) / unit
                k += 1
                pos = 0
        # 3. At the close: trail, time and family exits (they work at the next open).
        if pos != 0:
            cl = bc[t] if pos == 1 else ac[t]
            if pos * (cl - best) > 0:
                best = cl
            peak = max(peak, pos * (cl - fill) / unit)
            if trail_k > 0.0 and peak >= trail_start and not np.isnan(atr[t]):
                cand = best - pos * trail_k * atr[t]
                if pos * (cand - stop) > 0 and pos * (cl - cand) > 0:
                    stop = cand
            if max_bars > 0 and t - entry_bar + 1 >= max_bars:
                pend_exit = True
            if family_exit and ((pos == 1 and ex_l[t]) or (pos == -1 and ex_s[t])):
                pend_exit = True
        # 4. A new signal while flat.
        if pos == 0 and t >= start and t < end and t + 1 < n and sig[t] != 0 and not np.isnan(atr[t]) and atr[t] > 0:
            r = atr[t] if stop_k == 0.0 else (risk_px[t] if stop_k < 0.0 else stop_k * atr[t])
            if r > 0 and not np.isnan(r):
                pend_entry = sig[t]
                pend_unit = r
                sig_bar = t
        if t >= end and pos == 0 and pend_entry == 0:
            break
    return out_sig[:k], out_exit[:k], out_side[:k], out_r[:k]


# ── Running rules ───────────────────────────────────────────────────────

class Charts:
    """Chart arrays and family signals, computed once per (load, tf) and (rule family, params)."""

    def __init__(self, m15: pd.DataFrame):
        self.m15, self.charts, self.signals = m15, {}, {}

    def chart(self, tf: str) -> dict:
        if tf not in self.charts:
            self.charts[tf] = chart_arrays(self.m15, tf)
        return self.charts[tf]

    def signal(self, fam: str, tf: str, params: dict):
        key = (fam, tf, json.dumps(params, sort_keys=True))
        if key not in self.signals:
            self.signals[key] = FAMILIES[fam][2](self.chart(tf), **params)
        return self.signals[key]


def run_rule(cs: Charts, rule: dict, period: tuple[str, str]) -> pd.DataFrame:
    ch = cs.chart(rule["tf"])
    d, ex_l, ex_s, risk = cs.signal(rule["family"], rule["tf"], rule["params"])
    d = d.copy()
    if rule["side"] == "long":
        d[d < 0] = 0
    elif rule["side"] == "short":
        d[d > 0] = 0
    if rule["session"]:
        d[~ch["killzone"]] = 0
    if rule["d1"]:
        d[d != ch["d1_trend"]] = 0
    if rule["family"] == "drift":
        d = d * (1 if rule["side"] == "long" else -1)
    stop_k, target_r, trail_k, trail_start, max_bars, fam_exit = exit_spec(rule["exit"])
    t = ch["time"]
    start = int(t.searchsorted(pd.Timestamp(period[0], tz="UTC")))
    end = int(t.searchsorted(pd.Timestamp(period[1], tz="UTC")))
    risk_px = risk if risk is not None else np.full(len(d), np.nan)
    sb, xb, side, r = simulate(d.astype(np.int64), np.asarray(ex_l, bool), np.asarray(ex_s, bool), risk_px.astype(float),
                               ch["bid_open"], ch["bid_high"], ch["bid_low"], ch["bid_close"],
                               ch["ask_open"], ch["ask_high"], ch["ask_low"], ch["ask_close"], ch["atr"],
                               start, end, stop_k, target_r, trail_k, trail_start, max_bars, fam_exit, SLIP)
    return pd.DataFrame({"entry_time": t.iloc[sb].reset_index(drop=True) if len(sb) else pd.Series([], dtype=t.dtype),
                         "exit_time": t.iloc[xb].reset_index(drop=True) if len(xb) else pd.Series([], dtype=t.dtype),
                         "side": side, "R": r})


def score(trades: pd.DataFrame, period: tuple[str, str], prefix: str) -> dict:
    r = trades["R"].to_numpy(float)
    n = len(r)
    wins, losses = r[r > 0].sum(), -r[r <= 0].sum()
    row = {f"{prefix}_trades": n, f"{prefix}_expectancy_R": r.mean() if n else np.nan,
           f"{prefix}_win_rate": (r > 0).mean() if n else np.nan,
           f"{prefix}_profit_factor": wins / losses if losses > 0 else (np.inf if wins > 0 else np.nan),
           f"{prefix}_sqn": math.sqrt(n) * r.mean() / r.std(ddof=1) if n > 1 and r.std(ddof=1) > 0 else np.nan,
           f"{prefix}_max_drawdown_R": metrics.max_drawdown(pd.Series(r))}
    years = range(int(period[0][:4]), int(period[1][:4]))
    yr = trades["entry_time"].dt.year.to_numpy() if n else np.array([])
    for y in years:
        m = yr == y
        row[f"{prefix}_{y}_R"] = r[m].mean() if m.any() else np.nan
    return row


def rule_key(rule: dict) -> str:
    return json.dumps(rule, sort_keys=True)


def discover(rule_list: list[dict], progress=None) -> pd.DataFrame:
    """Train and validation for every rule (the holdout is never loaded here)."""
    cs = Charts(data.load("M15", *LOADS["discovery"]))
    rows = []
    for i, rule in enumerate(rule_list):
        row = {"rule": rule_key(rule), "family": rule["family"], "tf": rule["tf"], "params": json.dumps(rule["params"]),
               "side": rule["side"], "session": rule["session"], "d1": rule["d1"], "exit": rule["exit"]}
        trades = run_rule(cs, rule, (PERIODS["train"][0], PERIODS["val"][1]))
        for p, (a, b) in PERIODS.items():
            m = (trades["entry_time"] >= pd.Timestamp(a, tz="UTC")) & (trades["entry_time"] < pd.Timestamp(b, tz="UTC"))
            row.update(score(trades[m], (a, b), p))
        rows.append(row)
        if progress and i % 200 == 0:
            progress(i / len(rule_list), f"{i:,} of {len(rule_list):,} rules")
    return pd.DataFrame(rows)


def finalists(trials: pd.DataFrame) -> pd.DataFrame:
    ok = trials[(trials["train_trades"] >= MIN_TRAIN) & (trials["val_trades"] >= MIN_VAL)
                & (trials["train_expectancy_R"] > 0) & (trials["val_expectancy_R"] > 0)
                & (trials["train_profit_factor"] >= 1.1) & (trials["val_profit_factor"] >= 1.1)]
    ok = ok.assign(min_sqn=np.minimum(ok["train_sqn"], ok["val_sqn"]))
    return ok.sort_values("min_sqn", ascending=False).head(FINALISTS).reset_index(drop=True)


def holdout(final: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The one-shot holdout on the finalists only."""
    cs = Charts(data.load("M15", *LOADS["holdout"]))
    level = 1 - 0.10 / max(1, len(final))
    rows, trades_by_rule = [], {}
    for _, f in final.iterrows():
        rule = json.loads(f["rule"])
        trades = run_rule(cs, rule, HOLDOUT)
        trades_by_rule[f["rule"]] = trades
        row = {**f.to_dict(), **score(trades, HOLDOUT, "holdout")}
        ci = metrics.bootstrap_mean(trades.rename(columns={"entry_time": "entry_time"}), level=level) if len(trades) > 1 else {"low": np.nan}
        row["holdout_ci_low"] = ci["low"]
        years = [row.get(f"holdout_{y}_R") for y in range(int(HOLDOUT[0][:4]), int(HOLDOUT[1][:4]))]
        row["holdout_years_positive"] = int(sum((y or 0) > 0 for y in years))
        row["verdict"] = holdout_verdict(row)
        rows.append(row)
    return pd.DataFrame(rows), trades_by_rule


def holdout_verdict(row: dict) -> str:
    if (row.get("holdout_trades") or 0) < 50:
        return "inconclusive"
    if not (row.get("holdout_expectancy_R") or -1) > 0:
        return "fail"
    if ((row.get("holdout_profit_factor") or 0) >= 1.2 and (row.get("holdout_ci_low") or -1) > 0
            and row["holdout_years_positive"] >= 3):
        return "pass"
    return "weak"


def run_shard(shard: int, of: int, out_dir: Path, progress=None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    discover(rules()[shard::of], progress).to_csv(out_dir / f"trials_part_{shard}.csv", index=False)
    return out_dir


def merge(parts_dir: Path, out_dir: Path) -> Path:
    parts = sorted(Path(parts_dir).glob("**/trials_part_*.csv"))
    trials = pd.concat([pd.read_csv(p) for p in parts], ignore_index=True)
    if len(trials) != len(rules()) or trials["rule"].duplicated().any():
        raise SystemExit(f"{len(parts)} parts hold {len(trials):,} rows; expected {len(rules()):,} distinct rules")
    final = finalists(trials)
    judged, trades = holdout(final) if len(final) else (final.assign(verdict=[]), {})
    out_dir.mkdir(parents=True, exist_ok=True)
    trials.to_csv(out_dir / "trials.csv", index=False)
    judged.to_csv(out_dir / "finalists.csv", index=False)
    for i, (key, t) in enumerate(trades.items()):
        t.to_csv(out_dir / f"holdout_trades_{i + 1}.csv", index=False)
    prov = {"git": experiments._git(), "rules": len(trials), "families": list(FAMILIES), "exits": EXITS,
            "periods": PERIODS, "holdout": HOLDOUT, "min_train": MIN_TRAIN, "min_val": MIN_VAL, "finalists": FINALISTS,
            "slippage": SLIP, "status": "pre-registered in results/G1/rule.json"}
    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(report(trials, judged, prov), encoding="utf-8")
    return out_dir


def report(trials: pd.DataFrame, judged: pd.DataFrame, prov: dict) -> str:
    md, fmt = experiments._md, experiments._fmt
    elig = trials[(trials["train_trades"] >= MIN_TRAIN) & (trials["val_trades"] >= MIN_VAL)]
    both = elig[(elig["train_expectancy_R"] > 0) & (elig["val_expectancy_R"] > 0)]
    # With no edge, train and validation signs are independent: the expected count of rules positive in both.
    chance = len(elig) * (elig["train_expectancy_R"] > 0).mean() * (elig["val_expectancy_R"] > 0).mean() if len(elig) else 0
    passed = judged[judged["verdict"] == "pass"] if len(judged) else judged
    cols = ["family", "tf", "params", "side", "session", "d1", "exit", "train_trades", "train_expectancy_R", "train_profit_factor",
            "val_trades", "val_expectancy_R", "val_profit_factor", "holdout_trades", "holdout_expectancy_R",
            "holdout_profit_factor", "holdout_ci_low", "holdout_years_positive", "verdict"]
    fam = elig.groupby("family").agg(rules=("rule", "size"), train_R=("train_expectancy_R", "mean"),
                                     val_R=("val_expectancy_R", "mean"), best_val_R=("val_expectancy_R", "max"),
                                     positive_both=("val_expectancy_R", lambda s: int(((s > 0) & (elig.loc[s.index, "train_expectancy_R"] > 0)).sum())))
    lines = [
        "# G1 — Broad search for a profitable XAU/USD rule, judged on an untouched holdout", "",
        f"{len(trials):,} rules over {len(FAMILIES)} families. Train 2016–2018 and validation 2019–2022 pick up to "
        f"{FINALISTS} finalists; the holdout 2012–2015 (never used by any study) judges them once. OANDA bid/ask + "
        f"{SLIP} slippage. Pre-registered: results/G1/rule.json.", "",
        f"Git `{prov['git']['commit'][:10]}`{' (dirty)' if prov['git']['dirty'] else ''}", "",
        "## Summary", "",
        f"- Rules with enough trades in both periods: {len(elig):,} of {len(trials):,}.",
        f"- Positive after costs in both periods: {len(both):,} (about {chance:.0f} expected by chance alone).",
        f"- Finalists (positive and profit factor ≥ 1.1 in both): {len(judged)}.",
        f"- Holdout verdicts: " + (", ".join(f"{n} {k}" for k, n in judged["verdict"].value_counts().items()) if len(judged) else "none") + ".", "",
        "## Finalists on the holdout (2012–2015)", "",
        md(judged[[c for c in cols if c in judged]].set_index("family").round(3)) if len(judged) else "No rule qualified as a finalist.", "",
        "## By family (rules with enough trades)", "", md(fam.round(3)), "",
        "## Conclusion", "",
        (f"**{len(passed)} rule(s) pass the untouched holdout.** Next: a forward test on live data before any money."
         if len(passed) else
         "**No rule passes the untouched holdout.** Rules that made money in 2016–2022 did not keep doing so in 2012–2015."), "",
        "## Limitations", "",
        "- 2012–2015 OANDA data has more gaps than 2016+ (see results/data_quality).",
        "- Market orders only; no limit entries, partial exits or position sizing.", ""]
    return "\n".join(lines)
