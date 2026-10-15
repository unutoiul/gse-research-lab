"""GSE Strategy v4.0 (fresh touch + H4 + website targets), ported from the Pine source.

Source: gse-website commit 19564ee, `tradingview/gse_4.0/src/strategy-*.pine`
and `strategy.pine` (FRESH_LEVEL_STRATEGY.md). The levels come from the
structure port (`structure.py`), which runs on 15m, 1H and 4H candles.

What TradingView does that this module models explicitly:
- `request.security(tf, x[1], lookahead_on)`: the previous COMPLETED 1H/4H
  candle, seen from each 15m candle's open (`data.align(at="open")`).
- The broker emulator: an order placed at a close works from the next candle;
  a limit fills when price trades through it (at the open if it gaps); a
  bracket can fill on the entry candle. The order of events inside a candle is
  unknown, so two path models are offered (see `simulate`).
Fills use OANDA bid/ask: a long's limit fills when the ask reaches it, its
stop and target on the bid; shorts mirror it.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import structure
from .data import aggregate, align
from .structure import ST_CAND, ST_FLIP, ST_FRESH, isna, pivots

STOP_BUFFER_ATR, CLEARANCE_ATR, CLUSTER_ATR, MIN_R, MAX_ATR = 0.20, 0.10, 0.05, 1.5, 8.0
AGE_LIMIT_MS = {0: 900_000, 1: 7_200_000, 2: 28_800_000}  # f_target_snapshot_valid: M15, H1 2h, H4 8h


@dataclass(frozen=True)
class StrategyParams:
    """strategy-inputs.pine: the two analytical inputs. The rest is fixed in the Pine source."""
    swing_len: int = 10      # Chart swing lookback (M15 and H1 levels)
    h4_swing_len: int = 10   # H4 swing lookback (H4 direction and levels)
    tick: float = 0.01
    pivot_ties: str = "strict"
    # strategy-targets.pine constants (also the website's target engine). Not TradingView inputs.
    stop_buffer_atr: float = STOP_BUFFER_ATR
    min_r: float = MIN_R
    max_atr: float = MAX_ATR
    # Research variants, not in the Pine source (the defaults are the Pine behaviour).
    h4_mode: str = "with"    # "against": sell fresh resistance when 4H is up, buy fresh support when it is down
    stop_usd: float = 0.0    # > 0: fixed stop this many dollars from the entry instead of the structural stop
    stop_atr: float = 0.0    # > 0: fixed stop this many chart ATRs from the entry (scales with gold's price)
    d1_mode: str = "off"     # "with" / "against": trade only when GSE's 1D bias agrees with / opposes the trade
    # "limit": a limit at the level (the Pine). After the first touch of a fresh level, at the next open:
    # "rejection" if the candle closed back with the indicator's rejection wick (>= half its range),
    # "close_back" if it simply closed back on the level's side (the indicator's candle-close touch).
    entry_mode: str = "limit"
    # Which untouched levels can be entered: "fresh" A/V levels (the Pine), "flip" levels a body closed
    # through and nothing has touched since (flip candidates: Malaysian SnR's "fresh again"), or "both".
    # "flipped": confirmed flipped levels (broken, retested and held) on their first touch after that
    # confirming retest: the indicator's "Flipped support/resistance touched" alert.
    level_type: str = "fresh"
    # > 0: a fixed target this many times the risk, in place of the website's structure target
    # (no target rules then: every picked level is a signal).
    target_r: float = 0.0
    # "4.0": the v4.0 level engine (the Pine strategy this module ports); "4.1": with v4.1's
    # role-reversal rules (minimum touches, decisive break, move away first, failed flips).
    flip_rules: str = "4.0"
    # False: skip the Pine's check that the 1H/4H target snapshots are fresh. Only the website
    # structure target reads them, so fixed-exit research variants (and the 4H chart) do without.
    htf_check: bool = True

    def stop_distance(self, atr: float) -> float:
        """Fixed stop distance from the entry, or 0 for the Pine structural stop."""
        return self.stop_usd if self.stop_usd > 0 else self.stop_atr * atr if self.stop_atr > 0 else 0.0

    def core(self, swing_len: int) -> structure.CoreParams:
        # strategy-inputs.pine constants: zone_count 8, flips on (35%, 20 bars), merging off, EQ 0.15 ATR.
        flips = structure.V41_FLIPS if self.flip_rules == "4.1" else {}
        return structure.CoreParams(swing_len=swing_len, tick=self.tick, pivot_ties=self.pivot_ties, **flips)


# ── f_fresh_h4 (strategy-helpers.pine:2-24) ─────────────────────────────

def fresh_h4_direction(previous: int, bull_break: bool, bear_break: bool) -> int:
    return -1 if bear_break else 1 if bull_break else previous


def fresh_h4(h4: pd.DataFrame, swing_len: int, ties: str = "strict") -> np.ndarray:
    """The last 4H break direction, one value per 4H candle."""
    h, l, c = (h4[k].to_numpy(float) for k in ("high", "low", "close"))
    PH, PL = pivots(h, swing_len, swing_len, True, ties), pivots(l, swing_len, swing_len, False, ties)
    swing_high = swing_low = math.nan
    high_used = low_used = False
    direction = 0
    out = np.zeros(len(c))
    for t in range(len(c)):
        if not isna(PH[t]):
            swing_high, high_used = PH[t], False
        if not isna(PL[t]):
            swing_low, low_used = PL[t], False
        bull = not high_used and not isna(swing_high) and c[t] > swing_high
        bear = not low_used and not isna(swing_low) and c[t] < swing_low
        direction = fresh_h4_direction(direction, bull, bear)
        high_used = high_used or bull
        low_used = low_used or bear
        out[t] = direction
    return out


ENTRY_STATES = {"fresh": (ST_FRESH,), "flip": (ST_CAND,), "both": (ST_FRESH, ST_CAND), "flipped": (ST_FLIP,)}


def first_touch(lv) -> bool:
    """Not yet touched in its current state: no touch for a fresh level or a flip candidate; for a
    confirmed flipped level, only its confirming retest (core.pine sets touches to 1 there)."""
    return lv.touches == (1 if lv.state == ST_FLIP else 0)


def touch_pick(levels, h4_dir: int, bar_close: float, states: tuple = (ST_FRESH,)):
    """f_touch_pick (strategy-helpers.pine:26-34): nearest fresh, untouched, not-in-contact level on the
    trade side (support for a long, resistance for a short; in the Pine the trade side is the H4 side)."""
    best = None
    for lv in levels:
        if lv.state in states and first_touch(lv) and not lv.in_contact and lv.role == h4_dir and lv.role * (bar_close - lv.price) > 0:
            if best is None or abs(bar_close - lv.price) < abs(bar_close - best.price):
                best = lv
    return best


def reaction_pick(levels, d: int, was_fresh: set, o: float, h: float, l: float, c: float, strict: bool = True):
    """Research variant: a level that was fresh and untouched at the previous close and that this
    candle touched and closed back on its side of. strict: the indicator's level-reaction rule
    (alerts.pine f_level_reaction_pct), a candle closing in the trade direction with a rejection
    wick of at least half its range; otherwise any close back (the indicator's candle-close touch
    timing). The nearest such level to the close, or None."""
    rng = h - l
    if not rng > 0:
        return None
    if strict and d == 1 and not (c > o and (min(o, c) - l) / rng >= 0.5):
        return None
    if strict and d == -1 and not (c < o and (h - max(o, c)) / rng >= 0.5):
        return None
    best = None
    for lv in levels:
        if lv.id in was_fresh and lv.role == d and l <= lv.price <= h and d * (c - lv.price) > 0:
            if best is None or abs(c - lv.price) < abs(c - best.price):
                best = lv
    return best


# ── Inducement: minor wick swings in front of the level (research variant) ─

IND_MAX_AGE = 20     # candles a sweep of a minor swing is remembered (the longest age tested)
TRAIL_LEN = 3        # minor swing lookback of the swing trailing stop


@dataclass
class Minors:
    """Confirmed minor wick swings of one side (lows: the support side, highs: the resistance side), in
    confirmation order. `taken` is the first later candle whose wick goes beyond the swing (len(chart) if
    none); `swept` says that candle closed back on the swing's side; `extreme` is its low / high."""
    confirm: list
    origin: list
    price: list
    taken: list
    swept: list
    extreme: list
    sweep_bar: list | None = None    # the swept swings, ordered by the candle that swept them
    sweep_idx: list | None = None


def minor_swings(chart: pd.DataFrame, k: int, lows: bool, ties: str = "strict") -> Minors:
    h, l, c = (chart[x].to_numpy(float) for x in ("high", "low", "close"))
    piv = pivots(l if lows else h, k, k, not lows, ties)
    n = len(c)
    m = Minors([], [], [], [], [], [])
    for cb in np.flatnonzero(~np.isnan(piv)):
        px = piv[cb]
        j, step, taken = cb + 1, 64, n
        while j < n:
            seg = l[j:j + step] < px if lows else h[j:j + step] > px
            if seg.any():
                taken = j + int(np.argmax(seg))
                break
            j, step = j + step, step * 2
        m.confirm.append(int(cb)); m.origin.append(int(cb - k)); m.price.append(float(px)); m.taken.append(taken)
        if taken < n:
            m.swept.append(bool(c[taken] > px) if lows else bool(c[taken] < px))
            m.extreme.append(float(l[taken] if lows else h[taken]))
        else:
            m.swept.append(False); m.extreme.append(math.nan)
    order = sorted((tk, i) for i, (tk, sw) in enumerate(zip(m.taken, m.swept)) if sw)
    m.sweep_bar, m.sweep_idx = [tk for tk, _ in order], [i for _, i in order]
    return m


def inducement(m: Minors, d: int, level_price: float, after_bar: int, t: int, cutoff: int) -> tuple[int, int]:
    """Inducement in front of a level, as known at the close of candle t.

    Eligible: a minor swing on the trade side (lows for a long) that formed after `after_bar` and lies
    beyond the level, between it and price. Returns (state, sweep_age). state: 0 no eligible swing,
    1 the newest one is still untaken (present), 2 it was taken by candle `cutoff` (cleared).
    sweep_age: t minus the latest candle up to `cutoff` that went beyond an eligible swing and closed
    back, its extreme still short of the level (swept); -1 if none within IND_MAX_AGE.
    `cutoff` is t for a resting limit, t - 1 when candle t is the touch itself."""
    state, i = 0, bisect.bisect_right(m.confirm, t) - 1
    while i >= 0 and m.origin[i] > after_bar:
        if d * (m.price[i] - level_price) > 0:
            state = 2 if m.taken[i] <= cutoff else 1
            break
        i -= 1
    age = -1
    j = bisect.bisect_right(m.sweep_bar, cutoff) - 1
    while j >= 0 and m.sweep_bar[j] >= cutoff - IND_MAX_AGE:
        k = m.sweep_idx[j]
        if m.origin[k] > after_bar and d * (m.price[k] - level_price) > 0 and d * (m.extreme[k] - level_price) > 0:
            age = t - m.sweep_bar[j]
            break
        j -= 1
    return state, age


# ── Target snapshots (strategy-target-data.pine) ────────────────────────

def _mintick(price: float, tick: float) -> float:
    """str.tostring(price, format.mintick): the packet carries prices rounded to the tick."""
    return round(math.floor(price / tick + 0.5) * tick, 10)


def packet(levels, eqh_pool, eql_pool, pd_h, pd_l, pw_h, pw_l, tick: float) -> list[tuple]:
    """f_target_packet: (price, role, kind, fresh); kind 0 S/R, 1 EQH, 2 EQL, 3 previous day, 4 previous week."""
    out = []

    def rec(price, role, kind, fresh):
        if not isna(price) and 0 < price < 1e9:
            out.append((_mintick(price, tick), role, kind, fresh))
    for lv in levels:
        if lv.state != ST_CAND:
            rec(lv.price, lv.role, 0, lv.state == ST_FRESH)
    for p in eqh_pool:
        rec(p, -1, 1, False)
    for p in eql_pool:
        rec(p, 1, 2, False)
    rec(pd_h, -1, 3, False)
    rec(pd_l, 1, 3, False)
    rec(pw_h, -1, 4, False)
    rec(pw_l, 1, 4, False)
    return out


def snapshots(candles: pd.DataFrame, core: structure.CoreParams) -> list[list[tuple]]:
    """f_target_snapshot: the core engine on another timeframe's candles; one packet per candle."""
    packets: list[list[tuple]] = []
    structure.run(candles, core, hook=lambda t, lv, eqh, eql, pdh, pdl, pwh, pwl, atr, c:
                  packets.append(packet(lv, eqh, eql, pdh, pdl, pwh, pwl, core.tick)))
    return packets


def snapshot_valid(source_tf: int, snapshot_close, decision_close) -> bool:
    if snapshot_close is None or snapshot_close > decision_close:
        return False
    return decision_close - snapshot_close <= AGE_LIMIT_MS[source_tf]


# ── Website target engine (strategy-targets.pine) ───────────────────────

def target_round(price: float, tick: float, d: int) -> float:
    q = price / tick
    return (math.floor(q + 1e-9) if d == 1 else math.ceil(q - 1e-9)) * tick


def side_round(price, tick: float, d):
    """target_round for arrays: the same arithmetic, element by element."""
    q = np.asarray(price, dtype=float) / tick
    return np.where(np.asarray(d) == 1, np.floor(q + 1e-9), np.ceil(q - 1e-9)) * tick


def fixed_plan(d: int, entry: float, wick: float, atr: float, p: "StrategyParams") -> dict:
    """Research variant: the stop as the strategy places it (fixed distance, or beyond the wick),
    and a target p.target_r times the risk instead of the website's structure target."""
    plan = {"stop": math.nan, "tp1": math.nan, "tp2": math.nan, "tp3": math.nan, "reason": ""}
    dist = p.stop_distance(atr) if not isna(atr) else 0.0
    if dist > 0:
        plan["stop"] = target_round(entry - d * dist, p.tick, d)
    elif not isna(wick) and not isna(atr):
        invalidation = min(entry, wick) if d == 1 else max(entry, wick)
        plan["stop"] = target_round(invalidation - d * max(p.tick, atr * p.stop_buffer_atr), p.tick, d)
    risk = d * (entry - plan["stop"])
    if not risk > 0:
        plan["reason"] = "missing_invalidation"
        return plan
    plan["tp2"] = target_round(entry + d * p.target_r * risk, p.tick, d)
    return plan


def target_add(raw: list, d: int, entry: float, price: float, strength: int, major: bool, source_key: int) -> None:
    """Insert by distance from entry; the higher strength wins an exact-price tie."""
    if not isna(price) and 0 < price < 1e9 and d * (price - entry) >= 0:
        i = 0
        while i < len(raw) and (d * (raw[i][0] - price) < 0 or (raw[i][0] == price and raw[i][1] >= strength)):
            i += 1
        raw.insert(i, (price, strength, major, source_key))


def unpack(raw: list, records, source_tf: int, snapshot_close, decision_close, d: int, entry: float) -> None:
    if records is None or not snapshot_valid(source_tf, snapshot_close, decision_close):
        return
    htf = source_tf != 0
    base = 80 if source_tf == 2 else 65 if source_tf == 1 else 45
    for price, role, kind, fresh in records:
        if role == -d:
            strength = (base + (5 if fresh else 0)) if kind == 0 else 65 if kind == 3 else 80 if kind == 4 else (55 if htf else 35)
            target_add(raw, d, entry, price, strength, htf or kind >= 3, source_tf * 10 + kind)


def target_candidates(raw: list, d: int, entry: float, risk: float, atr: float, tick: float) -> list[tuple]:
    """Cluster at the near edge: (price, rr, distance_atr, score, major)."""
    cluster, padding = max(tick, atr * CLUSTER_ATR), max(tick, atr * CLEARANCE_ATR)
    out, i = [], 0
    while i < len(raw):
        first = raw[i]
        strength, major, sources, j = first[1], False, [], i
        while j < len(raw) and abs(raw[j][0] - first[0]) <= cluster + 1e-9:
            strength = max(strength, raw[j][1])
            major = major or raw[j][2]
            if raw[j][3] not in sources:
                sources.append(raw[j][3])
            j += 1
        price = target_round(first[0] - d * padding, tick, d)
        dist = d * (price - entry) / atr
        score = int(math.floor(strength + min(10, (len(sources) - 1) * 5) - min(25, max(0.0, dist) * 2) + 0.5))
        out.append((price, d * (price - entry) / risk, dist, score, major))
        i = j
    return out


def structure_targets(raw: list, d: int, entry: float, wick: float, atr: float, tick: float,
                      stop_buffer_atr: float = STOP_BUFFER_ATR, min_r: float = MIN_R, max_atr: float = MAX_ATR,
                      stop_distance: float = 0.0) -> dict:
    """f_structure_targets: stop, TP1/TP2/TP3 and the rejection reason ("" when TP2 exists).

    stop_distance > 0 (research variant) puts the stop that far from the entry instead of
    beyond the level's wick; targets are then measured against that risk."""
    plan = {"stop": math.nan, "tp1": math.nan, "tp2": math.nan, "tp3": math.nan, "reason": ""}
    valid = lambda x: not isna(x) and 0 < x < 1e9
    if not valid(wick) or not valid(atr) or not valid(tick):
        plan["reason"] = "missing_invalidation"
        return plan
    invalidation = min(entry, wick) if d == 1 else max(entry, wick)
    if stop_distance > 0:
        plan["stop"] = target_round(entry - d * stop_distance, tick, d)
    else:
        plan["stop"] = target_round(invalidation - d * max(tick, atr * stop_buffer_atr), tick, d)
    risk = d * (entry - plan["stop"])
    if not valid(plan["stop"]) or not valid(risk):
        plan["reason"] = "missing_invalidation"
        return plan
    cands = target_candidates(raw, d, entry, risk, atr, tick)
    if not cands:
        plan["reason"] = "no_opposing_structure"
        return plan
    invalid = cands[0][1] <= 0
    barrier = math.nan
    for c in cands:
        invalid = invalid or not valid(c[0])
        if isna(barrier) and c[4]:
            barrier = c[0]
    if invalid:
        plan["reason"] = "insufficient_room"
        return plan
    best, eligible = None, False
    for i, c in enumerate(cands):
        reachable = isna(barrier) or d * (c[0] - barrier) <= 1e-9
        if reachable and c[1] + 1e-9 >= min_r:
            eligible = True
            if c[2] <= max_atr + 1e-9:
                if best is None or c[3] > cands[best][3] or (c[3] == cands[best][3] and c[2] < cands[best][2]):
                    best = i
    if best is None:
        plan["reason"] = "target_too_distant" if eligible else "insufficient_room"
        return plan
    plan["tp2"] = cands[best][0]
    nearest = cands[0][0]
    plan["tp1"] = math.nan if nearest == plan["tp2"] else nearest
    next_minor = math.nan
    for c in cands:
        if d * (c[0] - plan["tp2"]) > 1e-9:
            if isna(next_minor):
                next_minor = c[0]
            if isna(plan["tp3"]) and c[4]:
                plan["tp3"] = c[0]
    if isna(plan["tp3"]):
        plan["tp3"] = next_minor
    return plan


# ── Signals per 15m candle (strategy.pine:1-29) ─────────────────────────

def _ms(ts: pd.Series) -> np.ndarray:
    return (ts.astype("datetime64[ns, UTC]").astype("int64") // 1_000_000).to_numpy()


def h1_inputs(m15: pd.DataFrame, p: StrategyParams) -> tuple:
    """1H target packets (chart swing lookback), as each 15m candle sees them: [1] with lookahead on."""
    h1 = aggregate(m15, "1H")
    h1 = h1.assign(idx=np.arange(len(h1)))
    seen = align(m15, h1, ["idx"], at="open")
    return snapshots(h1, p.core(p.swing_len)), seen["idx"].to_numpy(), _ms(seen["htf_close_time"].fillna(pd.Timestamp(0, tz="UTC")))


def h4_inputs(m15: pd.DataFrame, p: StrategyParams) -> tuple:
    """4H direction and target packets (H4 swing lookback), as each 15m candle sees them."""
    h4 = aggregate(m15, "4H")
    h4 = h4.assign(dir=fresh_h4(h4, p.h4_swing_len, p.pivot_ties), idx=np.arange(len(h4)))
    seen = align(m15, h4, ["dir", "idx"], at="open")
    return (snapshots(h4, p.core(p.h4_swing_len)), seen["idx"].to_numpy(),
            _ms(seen["htf_close_time"].fillna(pd.Timestamp(0, tz="UTC"))), seen["dir"].to_numpy())


def d1_inputs(chart: pd.DataFrame, p: StrategyParams, history: pd.DataFrame | None = None) -> np.ndarray:
    """GSE's 1D bias score (f_bias_score, chart swing lookback) as each chart candle sees it at its close:
    closed days only, the day that closes with the candle included (mtf.pine f_mtf_score).

    `history` (M15 from further back) gives the daily EMA50 and pivots time to settle."""
    d1 = aggregate(chart if history is None else history, "1D")
    d1 = d1.assign(score=structure.bias_scores(d1, p.core(p.swing_len)))
    return align(chart, d1, ["score"], at="close")["score"].to_numpy(float)


def signals(m15: pd.DataFrame, p: StrategyParams = StrategyParams(), h1: tuple | None = None, h4: tuple | None = None,
            d1: np.ndarray | None = None, ind_lens: tuple = ()) -> pd.DataFrame:
    """For every chart close: trade direction, the picked level and its frozen plan, or why there is none.

    The chart is the 15m frame of the Pine strategy, or a 1H frame (research variant: the Pine
    strategy trades only on 15m). `dir` is the trade direction (the H4 direction, or its opposite
    when h4_mode is "against"); `h4_dir` is the H4 direction itself; `d1` the 1D bias when used.
    `order` is "limit" (a limit at the level, as in the Pine) or "market" (entry_mode "rejection" or
    "close_back": a market order at the next open after the confirming candle, planned from its close).
    h4_mode "off" (research variant) trades either side: the nearest enterable support or resistance.

    `ind_lens`: minor swing lookbacks for which each signal records its inducement (`ind{k}_state`,
    `ind{k}_sweep_age`; see `inducement`)."""
    if h1 is None and not p.htf_check:
        h1 = ([], np.zeros(len(m15)), np.zeros(len(m15), dtype=np.int64))  # read only by the snapshot check
    h1_pk, h1_idx, h1_close = h1 if h1 is not None else h1_inputs(m15, p)
    h4_pk, h4_idx, h4_close, dir_seen = h4 if h4 is not None else h4_inputs(m15, p)
    decision = _ms(m15["close_time"])
    n = len(m15)
    cols = {k: [None] * n for k in ("dir", "h4_dir", "d1", "level_id", "entry", "wick", "stop", "tp1", "tp2", "tp3", "reason",
                                    "atr")}
    confirm = p.entry_mode in ("rejection", "close_back")
    cols["order"] = ["market" if confirm else "limit"] * n
    O, H, Lo = (m15[k].to_numpy(float) for k in ("open", "high", "low"))
    states = ENTRY_STATES[p.level_type]
    track = {"fresh": set()}  # ids of enterable, untouched levels at the previous close (confirmed entries)
    flip = {"with": 1, "against": -1, "off": 0}[p.h4_mode]
    d1_want = {"off": 0, "with": 1, "against": -1}[p.d1_mode]
    if d1_want and d1 is None:
        d1 = d1_inputs(m15, p)
    sides = {k: {1: minor_swings(m15, k, True, p.pivot_ties), -1: minor_swings(m15, k, False, p.pivot_ties)} for k in ind_lens}
    for k in ind_lens:
        cols[f"ind{k}_state"], cols[f"ind{k}_sweep_age"] = [0] * n, [-1] * n

    def nearest(a, b, c):
        return a if b is None else b if a is None else (a if abs(c - a.price) <= abs(c - b.price) else b)

    def hook(t, levels, eqh, eql, pdh, pdl, pwh, pwl, atr, c):
        # A flipped level still sitting on its confirming retest is not a new visit (alerts.pine watch list).
        was_fresh, track["fresh"] = track["fresh"], {lv.id for lv in levels if lv.state in states and first_touch(lv)
                                                     and not (lv.state == ST_FLIP and lv.in_contact)}
        cols["atr"][t] = atr
        h4 = 0 if isna(dir_seen[t]) else int(np.sign(dir_seen[t]))
        d = h4 * flip
        cols["dir"][t], cols["h4_dir"][t] = d, h4
        if p.htf_check:
            h1_ok = not isna(h1_idx[t]) and snapshot_valid(1, h1_close[t], decision[t])
            h4_ok = not isna(h4_idx[t]) and snapshot_valid(2, h4_close[t], decision[t])
            if not (h1_ok and h4_ok):
                cols["reason"][t] = "waiting_htf_data"
                return
        if d == 0 and flip != 0:
            cols["reason"][t] = "no_h4_direction"
            return

        def d1_blocks(side):
            cols["d1"][t] = d1[t]
            if isna(d1[t]) or np.sign(d1[t]) != side * d1_want:  # a neutral (0) day trades neither way
                cols["reason"][t] = "d1_context"
                return True
            return False
        if d1_want and flip and d1_blocks(d):
            return
        if confirm:
            strict = p.entry_mode == "rejection"
            pick = lambda side: reaction_pick(levels, side, was_fresh, O[t], H[t], Lo[t], c, strict=strict)
            lv = pick(d) if flip else nearest(pick(1), pick(-1), c)
            if lv is None:
                cols["reason"][t] = "no_rejection"
                return
        else:
            lv = touch_pick(levels, d, c, states) if flip else nearest(touch_pick(levels, 1, c, states),
                                                                       touch_pick(levels, -1, c, states), c)
            if lv is None:
                cols["reason"][t] = "no_fresh_level"
                return
        if not flip:
            d = lv.role
            cols["dir"][t] = d
            if d1_want and d1_blocks(d):
                return
        if confirm:
            # Planned from the rejection close; the stop goes beyond the rejection wick.
            extreme = Lo[t] if d == 1 else H[t]
            entry, wick = c, extreme if isna(lv.wick) else (min(extreme, lv.wick) if d == 1 else max(extreme, lv.wick))
        else:
            # A flip candidate has no wick yet: its invalidation is the level itself.
            entry, wick = lv.price, lv.price if isna(lv.wick) else lv.wick
        # Inducement counts from the level's own pivot, or for a flipped level from its break.
        after = lv.born_bar if lv.state == ST_FLIP else lv.origin_bar
        for k in ind_lens:
            state, age = inducement(sides[k][d], d, lv.price, after, t, t - 1 if confirm else t)
            cols[f"ind{k}_state"][t], cols[f"ind{k}_sweep_age"][t] = state, age
        if p.target_r > 0:
            plan = fixed_plan(d, entry, wick, atr, p)
        else:
            raw: list = []
            unpack(raw, packet(levels, eqh, eql, pdh, pdl, pwh, pwl, p.tick), 0, decision[t], decision[t], d, entry)
            unpack(raw, h1_pk[int(h1_idx[t])], 1, h1_close[t], decision[t], d, entry)
            unpack(raw, h4_pk[int(h4_idx[t])], 2, h4_close[t], decision[t], d, entry)
            plan = structure_targets(raw, d, entry, wick, atr, p.tick, p.stop_buffer_atr, p.min_r, p.max_atr,
                                     p.stop_distance(atr) if not isna(atr) else 0.0)
        cols["level_id"][t], cols["entry"][t], cols["wick"][t] = lv.id, entry, wick
        for k in ("stop", "tp1", "tp2", "tp3"):
            cols[k][t] = plan[k]
        cols["reason"][t] = plan["reason"] or "signal"

    eng, _ = structure.run(m15, p.core(p.swing_len), hook=hook)
    out = pd.DataFrame(cols, index=m15.index)
    out["signal"] = out["reason"] == "signal"
    # Confluence readings at each close, from the same level engine (chart bias, sweeps, sessions).
    for k in FEATURES:
        out[k] = eng[k].to_numpy()
    # The latest confirmed minor swing low / high at each close, for the swing trailing stop.
    for name, lows in (("swing_low", True), ("swing_high", False)):
        src = m15["low" if lows else "high"].to_numpy(float)
        out[name] = pd.Series(pivots(src, TRAIL_LEN, TRAIL_LEN, not lows, p.pivot_ties)).ffill().to_numpy()
    return out


FEATURES = ("trend_score", "bull_sweep_age", "bear_sweep_age", "in_asian", "in_london", "in_ny")


# ── Orders and broker emulation (strategy.pine:31-78) ───────────────────

@dataclass(frozen=True)
class Broker:
    path: str = "conservative"   # or "tradingview"
    slippage: float = 0.10       # adverse, on stop fills and the end-of-range market close
    spread_scale: float = 1.0    # 1: OANDA bid/ask; 0.5: half the spread (raw-spread account); 0: mid prices


@dataclass(frozen=True)
class Manage:
    """Research variant: moving the stop of an open trade. Decided at a candle's close from that close
    (on the exit side's prices) and working from the next candle, so it never uses a candle's own extremes.
    be_r > 0: once a close is be_r R in profit, the stop moves to the fill price.
    trail "atr": once a close is trail_start_r R in profit, the stop trails trail_atr chart ATRs behind the
    best close; "swing": beyond the latest confirmed minor swing (lookback TRAIL_LEN), less the website's
    0.2 ATR stop buffer. A stop only moves toward profit and stays behind the close."""
    be_r: float = 0.0
    trail: str = "none"
    trail_start_r: float = 1.0
    trail_atr: float = 2.0
    buffer_atr: float = STOP_BUFFER_ATR
    tick: float = 0.01


HIGH_FIRST, LOW_FIRST = ["o", "h", "l", "c"], ["o", "l", "h", "c"]


def _path(o, h, l, c, model: str, d: int, in_position: bool) -> list[str]:
    """The order of a candle's extremes.

    'tradingview' (TradingView's broker emulator): the extreme nearer the open comes first.
    'conservative' (worst case): while waiting to fill, the favourable extreme comes before
    the fill; once in a position, the adverse extreme comes first.
    """
    if model == "tradingview":
        return HIGH_FIRST if (h - o) <= (o - l) else LOW_FIRST
    adverse_first = LOW_FIRST if d == 1 else HIGH_FIRST
    favourable_first = HIGH_FIRST if d == 1 else LOW_FIRST
    return adverse_first if in_position else favourable_first


def simulate(m15: pd.DataFrame, sig: pd.DataFrame, start: str, end: str, broker: Broker = Broker(),
             manage: Manage | None = None) -> tuple[pd.DataFrame, dict]:
    """Run the order logic over [start, end) by candle close time. Returns trades and order counts.

    A NaN target (`tp2`) means no target: the trade ends at its (managed) stop or at the range end."""
    t_start, t_end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    in_test = ((m15["close_time"] >= t_start) & (m15["close_time"] < t_end)).to_numpy()
    after_end = (m15["close_time"] >= t_end).to_numpy()
    mid = {k: m15[k].to_numpy(float) for k in ("open", "high", "low", "close")}
    f = broker.spread_scale
    bid = {k: mid[k] + f * (m15[f"bid_{k}"].to_numpy(float) - mid[k]) for k in mid}
    ask = {k: mid[k] + f * (m15[f"ask_{k}"].to_numpy(float) - mid[k]) for k in mid}
    S = {k: sig[k].tolist() for k in ("signal", "dir", "level_id", "entry", "stop", "tp1", "tp2", "tp3")}
    S["order"] = sig["order"].tolist() if "order" in sig else ["limit"] * len(sig)
    key = {"o": "open", "h": "high", "l": "low", "c": "close"}
    slip = broker.slippage
    TIMES = m15["time"].tolist()
    if manage is not None:
        ATR = sig["atr"].to_numpy(float)
        SWING = {1: sig["swing_low"].to_numpy(float), -1: sig["swing_high"].to_numpy(float)}

    def manage_stop(t):
        d = pos["dir"]
        cl = (bid if d == 1 else ask)["close"][t]
        pos["peak_R"] = max(pos.get("peak_R", 0.0), d * (cl - pos["fill"]) / pos["risk"])
        if pos.get("best_close") is None or d * (cl - pos["best_close"]) > 0:
            pos["best_close"] = cl
        new = pos["stop"]
        if manage.be_r > 0 and pos["peak_R"] >= manage.be_r and d * (pos["fill"] - new) > 0:
            new = pos["fill"]
        if manage.trail != "none" and pos["peak_R"] >= manage.trail_start_r and not isna(ATR[t]):
            if manage.trail == "atr":
                cand = pos["best_close"] - d * manage.trail_atr * ATR[t]
            else:
                cand = SWING[d][t] - d * max(manage.tick, manage.buffer_atr * ATR[t])
            if not isna(cand):
                cand = target_round(cand, manage.tick, d)
                if d * (cand - new) > 0:
                    new = cand
        if d * (new - pos["stop"]) > 0 and d * (cl - new) > 0:
            pos["stop"], pos["stop_moved"] = new, True

    trades, pos, pending = [], None, None
    submitted_signal = None
    counts = {"submitted": 0, "cancelled": 0, "filled": 0}
    first = int(np.flatnonzero(in_test)[0]) if in_test.any() else len(m15)
    close_at_next_open = False

    def exit_trade(t, price, reason):
        d = pos["dir"]
        if reason in ("stop", "stop_gap") and pos.get("stop_moved"):
            reason = "managed_" + reason
        R = d * (price - pos["fill"]) / pos["risk"]
        trades.append({**pos, "exit_time": TIMES[t], "exit": price, "reason": reason,
                       "bars_held": t - pos["fill_bar"] + 1, "R": R,
                       "mfe_R": pos["best"] / pos["risk"], "mae_R": min(pos["worst"] / pos["risk"], max(1.0, -R))})

    sig_on = S["signal"]
    for t in range(first, len(m15)):
        # Nothing working and no new signal: the candle changes nothing (the end still stops the run).
        if pos is None and pending is None and not close_at_next_open and not (in_test[t] and sig_on[t]):
            if after_end[t]:
                break
            continue
        closed_this_bar = False
        # ── During candle t: orders submitted at earlier closes work now.
        if close_at_next_open and pos is not None:
            d = pos["dir"]
            px = (bid if d == 1 else ask)["open"][t] - d * slip
            exit_trade(t, px, "range_end")
            pos, closed_this_bar = None, True
            close_at_next_open = False
        if pos is not None or pending is not None:
            d = (pos or pending)["dir"]
            ent = ask if d == 1 else bid      # entry side
            ext = bid if d == 1 else ask      # exit side
            path = _path(mid["open"][t], mid["high"][t], mid["low"][t], mid["close"][t], broker.path, d, pos is not None)
            seg_start = 0
            if pos is None:
                L = pending["entry"]
                if pending["order"] == "market":            # a market order fills at the open, with slippage
                    fill, seg_start = ent["open"][t] + d * slip, 0
                elif d * (ent["open"][t] - L) <= 0:         # opens through the limit: filled at the open
                    fill, seg_start = ent["open"][t], 0
                else:
                    fill = None
                    for i in range(1, 4):
                        px = ent[key[path[i]]][t]
                        if d * (px - L) <= 0:
                            fill, seg_start = L, i - 1
                            break
                if fill is not None:
                    # R is measured against the PLANNED risk (limit, or the signal close for a market
                    # order, to the stop; always > 0), the unit a trader sizes with. A gap fill can make
                    # the actual risk smaller, or nil.
                    planned = d * (pending["entry"] - pending["stop"])
                    fill_risk = d * (fill - pending["stop"])
                    pos = {**pending, "fill": fill, "fill_bar": t, "fill_time": TIMES[t], "risk": planned,
                           "fill_risk": fill_risk, "best": 0.0, "worst": 0.0}
                    pending = None
                    counts["filled"] += 1
                    if fill_risk <= 0:  # filled at or beyond its own stop (a gap): out at once
                        exit_trade(t, ext["open"][t] - d * slip, "stop_gap")
                        pos, closed_this_bar = None, True
            if pos is not None:
                stop, tp = pos["stop"], pos["tp2"]
                if pos["fill_bar"] < t:                      # a candle that opens through an exit fills at its open
                    if d * (ext["open"][t] - stop) <= 0:
                        exit_trade(t, ext["open"][t] - d * slip, "stop_gap")
                        pos, closed_this_bar = None, True
                    elif d * (ext["open"][t] - tp) >= 0:
                        exit_trade(t, ext["open"][t], "target_gap")
                        pos, closed_this_bar = None, True
                if pos is not None:
                    for i in range(max(seg_start, 0) + 1, 4):
                        px = ext[key[path[i]]][t]
                        pos["best"] = max(pos["best"], d * (px - pos["fill"]))
                        pos["worst"] = max(pos["worst"], d * (pos["fill"] - px))
                        if d * (px - stop) <= 0:
                            exit_trade(t, stop - d * slip, "stop")
                            pos, closed_this_bar = None, True
                            break
                        if d * (px - tp) >= 0:
                            exit_trade(t, tp, "target")
                            pos, closed_this_bar = None, True
                            break

        # ── At the close of candle t (strategy.pine:44-78).
        if manage is not None and pos is not None:
            manage_stop(t)
        if pos is not None or closed_this_bar:
            pending = None
        if after_end[t]:
            if pending is not None:
                counts["cancelled"] += 1
            pending = None
            if pos is not None:
                close_at_next_open = True
            if pos is None:
                break
            continue
        valid = (in_test[t] and S["signal"][t] and pending is not None and S["level_id"][t] == pending["level_id"]
                 and S["dir"][t] == pending["dir"])
        if pending is not None and pos is None and not valid:
            pending = None
            counts["cancelled"] += 1
        can_enter = in_test[t] and pos is None and pending is None and submitted_signal != t
        if can_enter and S["signal"][t]:
            submitted_signal = t
            pending = {"signal_bar": t, "signal_time": TIMES[t], "dir": int(S["dir"][t]), "order": S["order"][t],
                       "level_id": int(S["level_id"][t]), "entry": S["entry"][t], "stop": S["stop"][t],
                       "tp1": S["tp1"][t], "tp2": S["tp2"][t], "tp3": S["tp3"][t]}
            counts["submitted"] += 1
    if pos is not None:
        counts["open_at_data_end"] = 1
    df = pd.DataFrame(trades)
    if len(df):
        df["entry_time"] = df["fill_time"]
        df["planned_rr"] = df["dir"] * (df["tp2"] - df["fill"]) / df["risk"]
        df["side"] = df["dir"]
    return df, counts
