"""GSE v4.0 market structure and context, ported from the Pine source.

A candle-by-candle port of `core.pine` (`f_core_update`), `context.pine`
(`f_context_update`) and `mtf.pine` (`f_bias_score`) at gse-website commit
19564ee. Every candle is a confirmed candle (history), so `confirmed` is
always true. The order of operations follows GSE_BASELINE_AUDIT.md 1.1 and
must not change: tests/test_structure_oracle.py compares this port, candle by
candle, with the Pine source translated to JavaScript.

Inputs that TradingView computes outside these functions (ATR, EMAs, pivots,
previous day/week references, sessions) are prepared in `prepare()` with
Pine's own formulas, and only from information available at each candle.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .data import aggregate, align, session_clock

NAN = math.nan
ST_FRESH, ST_TAPPED, ST_CAND, ST_FLIP = 0, 1, 2, 3
EVT_FLIP_TO_SUP, EVT_FLIP_TO_RES, EVT_TAP_RES, EVT_TAP_SUP = 0, 1, 4, 5

# Golden Zone conditions in the audit's rejection order (4.1), as bits.
GZ_DIRECTION, GZ_LOCATION, GZ_BIAS, GZ_BOS, GZ_ROOM, GZ_SWEEP = 1, 2, 4, 8, 16, 32
GZ_NAMES = {GZ_DIRECTION: "direction", GZ_LOCATION: "location", GZ_BIAS: "bias",
            GZ_BOS: "recent_bos", GZ_ROOM: "room", GZ_SWEEP: "sweep"}


def isna(x: float) -> bool:
    return x != x


@dataclass(frozen=True)
class CoreParams:
    """inputs.pine and indicator-defaults.pine defaults."""
    swing_len: int = 10
    zone_count: int = 8
    flip_on: bool = True
    flip_wick: float = 35.0
    cluster_on: bool = False
    cluster_atr: float = 0.5
    flip_max_age: int = 20
    eq_atr: float = 0.15
    sweep_snr_atr: float = 3.0
    break_fallback: bool = True
    # syminfo.mintick of BLACKBULL:XAUUSD, the live GSE chart.
    tick: float = 0.01
    # How ta.pivothigh/pivotlow treat equal values. TradingView's rule is
    # unknown (audit P1) until the parity gate settles it.
    pivot_ties: str = "strict"


@dataclass(frozen=True)
class ContextParams:
    """indicator-inputs.pine and indicator-defaults.pine defaults."""
    space_mult: float = 2.0
    confl_window: int = 15
    sweep_bos_win: int = 6
    conf_cluster: int = 8
    rej_atr: float = 2.0
    require_sweep: bool = False
    w_str: int = 35
    w_loc: int = 30
    w_conf: int = 25
    w_time: int = 10
    gate_cap: int = 60


@dataclass
class Level:
    id: int
    price: float
    role: int
    state: int
    touches: int
    wick: float = NAN
    origin_bar: int = -1
    born_bar: int = -1
    kind: str = ""
    in_contact: bool = False


# ── Pine series functions ───────────────────────────────────────────────

def pine_rma(x: np.ndarray, n: int) -> np.ndarray:
    """ta.rma: SMA of the first n values, then (x + (n - 1) * prev) / n."""
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        prev = float(np.mean(x[:n]))
        out[n - 1] = prev
        for i in range(n, len(x)):
            prev = (x[i] + (n - 1) * prev) / n
            out[i] = prev
    return out


def pine_ema(x: np.ndarray, n: int) -> np.ndarray:
    """ta.ema: SMA of the first n values, then alpha * x + (1 - alpha) * prev."""
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        alpha = 2.0 / (n + 1)
        prev = float(np.mean(x[:n]))
        out[n - 1] = prev
        for i in range(n, len(x)):
            prev = alpha * x[i] + (1 - alpha) * prev
            out[i] = prev
    return out


def pine_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    prev_close = np.concatenate([[np.nan], close[:-1]])
    tr = np.where(np.isnan(prev_close), high - low,
                  np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))))
    return pine_rma(tr, n)


def pine_sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).mean().to_numpy()


def pivots(src: np.ndarray, left: int, right: int, high: bool, ties: str = "strict") -> np.ndarray:
    """ta.pivothigh / ta.pivotlow: src[t - right] on the candle t that confirms it, else NaN.

    ties: "strict" (greater than every neighbour), "left" (equal to an earlier
    neighbour allowed), "right" (equal to a later one allowed), "both".
    """
    n = len(src)
    out = np.full(n, np.nan)
    if n < left + right + 1:
        return out
    s = src if high else -src
    win = sliding_window_view(s, left + right + 1)  # row k covers candles k .. k + left + right
    centre = win[:, left]
    lmax = win[:, :left].max(axis=1)
    rmax = win[:, left + 1:].max(axis=1)
    lok = centre >= lmax if ties in ("left", "both") else centre > lmax
    rok = centre >= rmax if ties in ("right", "both") else centre > rmax
    ok = lok & rok & ~np.isnan(centre)
    out[left + right:] = np.where(ok, src[left: n - right], np.nan)
    return out


def resolve_bias(raw: float, struct_dir: int, ema_points: float, break_fallback: bool = True) -> float:
    """f_resolve_bias (core:227-232)."""
    conflicting = raw == 0 or (struct_dir != 0 and struct_dir * raw < 0)
    combined = raw + ema_points
    same = max(combined, 0.0) if raw > 0 else min(combined, 0.0)
    fallback = struct_dir * 0.5 if (break_fallback and struct_dir != 0 and raw != 0) else 0.0
    return fallback if conflicting else same


def level_quality(is_flip: bool, is_fresh: bool, touches: int) -> float:
    """f_context_level_quality (context:93-94)."""
    return (1.0 if touches <= 1 else 0.0) if is_flip else 0.8 if is_fresh else 0.0


def level_duplicate(existing_role: int, existing_state: int, existing_price: float, role: int, price: float,
                    cluster_on: bool, cluster_distance: float, tick: float) -> bool:
    """f_level_duplicate (core:166-170)."""
    distance = abs(existing_price - price)
    exact = distance <= tick * 0.5
    in_zone = cluster_on and existing_state != ST_CAND and not isna(cluster_distance) and distance <= cluster_distance
    return existing_role == role and existing_state != ST_CAND and (exact or in_zone)


def opened_away(role: int, open_price: float, price: float, tick: float) -> bool:
    """f_opened_away (core:195-196)."""
    return role * (open_price - price) > tick * 0.5


# ── Inputs prepared outside f_core_update ───────────────────────────────

def prepare(m15: pd.DataFrame, core: CoreParams = CoreParams()) -> pd.DataFrame:
    """Series Pine computes with ta.* and request.security, from closed data only."""
    o, h, l, c = (m15[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    L = core.swing_len
    t = m15["time"]
    clock = session_clock(t)
    day = clock.dt.floor("D")
    week = day - pd.to_timedelta(day.dt.dayofweek, unit="D")
    d1 = aggregate(m15, "1D")
    w1 = aggregate(m15, "1W")
    # request.security(D/W, high[1], lookahead_on): the last completed period, seen from its next candle's open.
    pd_ref = align(m15, d1, ["high", "low"], at="open")
    pw_ref = align(m15, w1, ["high", "low"], at="open")

    def local_hour(tz: str) -> pd.Series:
        lt = t.dt.tz_convert(tz)
        return lt.dt.hour + lt.dt.minute / 60.0

    tokyo, london, ny = local_hour("Asia/Tokyo"), local_hour("Europe/London"), local_hour("America/New_York")
    return pd.DataFrame({
        "atr": pine_atr(h, l, c, 14),
        "ema20": pine_ema(c, 20),
        "ema50": pine_ema(c, 50),
        "vol_sma20": pine_sma(m15["volume"].to_numpy(float), 20),
        "ph": pivots(h, L, L, True, core.pivot_ties),
        "pl": pivots(l, L, L, False, core.pivot_ties),
        "a_lvl": pivots(np.maximum(o, c), L, L, True, core.pivot_ties),
        "v_lvl": pivots(np.minimum(o, c), L, L, False, core.pivot_ties),
        "pd_h": pd_ref["high"].to_numpy(float), "pd_l": pd_ref["low"].to_numpy(float),
        "pw_h": pw_ref["high"].to_numpy(float), "pw_l": pw_ref["low"].to_numpy(float),
        "new_day": day.ne(day.shift()).to_numpy(),
        "new_week": week.ne(week.shift()).to_numpy(),
        "in_asian": ((tokyo >= 9) & (tokyo < 17)).to_numpy(),
        "in_london": ((london >= 8) & (london < 17)).to_numpy(),
        "in_ny": ((ny >= 8) & (ny < 17)).to_numpy(),
    }, index=m15.index)


# ── f_core_update + f_context_update ────────────────────────────────────

@dataclass
class _State:
    ph1: float = NAN
    ph2: float = NAN
    pl1: float = NAN
    pl2: float = NAN
    ph1_bar: int = -1
    pl1_bar: int = -1
    struct_dir: int = 0
    used_ph_bar: int | None = None
    used_pl_bar: int | None = None
    levels: list = field(default_factory=list)
    next_id: int = 0
    eq_h_v: list = field(default_factory=list)
    eq_h_b: list = field(default_factory=list)
    eq_l_v: list = field(default_factory=list)
    eq_l_b: list = field(default_factory=list)
    eqh_pool: list = field(default_factory=list)
    eql_pool: list = field(default_factory=list)
    pdh_consumed: bool = False
    pdl_consumed: bool = False
    pwh_consumed: bool = False
    pwl_consumed: bool = False
    last_pd_h: float = NAN
    last_pd_l: float = NAN
    last_pw_h: float = NAN
    last_pw_l: float = NAN
    swing_h_consumed: bool = False
    swing_l_consumed: bool = False
    # context
    bull_sweep_bar1: int | None = None
    bear_sweep_bar1: int | None = None
    bull_sweep_src: str = ""
    bear_sweep_src: str = ""
    last_bull_bos_bar: int | None = None
    last_bear_bos_bar: int | None = None
    bull_bos_had_sweep: bool = False
    bear_bos_had_sweep: bool = False
    bull_bos_sweep_src: str = ""
    bear_bos_sweep_src: str = ""
    last_bull_rej: int | None = None
    last_bear_rej: int | None = None
    last_vspike_bull: int | None = None
    last_vspike_bear: int | None = None


def _count_role(levels: list[Level], role: int) -> int:
    return sum(1 for lv in levels if lv.role == role)


def _trim_role(levels: list[Level], role: int, cap: int) -> None:
    """f_trim_role (core:154-162): drop the oldest born_bar of the role until the cap holds."""
    while _count_role(levels, role) > cap:
        oldest = None
        for i, lv in enumerate(levels):
            if lv.role == role and (oldest is None or lv.born_bar < levels[oldest].born_bar):
                oldest = i
        if oldest is not None:
            levels.pop(oldest)


def _merge_into(levels: list[Level], cluster_on: bool, cluster_atr: float, atr: float, role: int, price: float, tick: float) -> bool:
    """f_merge_into (core:175-191)."""
    target, best = None, NAN
    for i, lv in enumerate(levels):
        if level_duplicate(lv.role, lv.state, lv.price, role, price, cluster_on, cluster_atr * atr, tick):
            d = abs(lv.price - price)
            if isna(best) or d < best:
                best, target = d, i
    if target is not None:
        zone = levels[target]
        if zone.state == ST_FRESH:
            zone.state = ST_TAPPED
            zone.touches += 1
    return target is not None


def _pick_obstacle(direction: int, price: float, best: float, candidate: float) -> float:
    """f_context_pick_obstacle (context:74-76)."""
    valid = not isna(candidate) and direction * (candidate - price) >= 0
    return candidate if valid and (isna(best) or direction * (candidate - best) < 0) else best


def run(m15: pd.DataFrame, core: CoreParams = CoreParams(), ctx: ContextParams = ContextParams(),
        prep: pd.DataFrame | None = None, trace: list | None = None, hook=None) -> tuple[pd.DataFrame, list[dict]]:
    """Run GSE v4.0 over closed M15 candles.

    Returns one row per candle (the indicator's state at that close) and the
    level events (taps and confirmed flips) with their candle index. With
    `trace`, the full level list and equal-high/low pools are appended after
    every candle (for the Pine oracle comparison). `hook(t, levels, eqh_pool,
    eql_pool, pd_h, pd_l, pw_h, pw_l, atr, close)` is called at the end of every
    candle with the live state (read only), e.g. for the strategy's level picks.
    """
    prep = prepare(m15, core) if prep is None else prep
    O, H, Lo, C = (m15[k].tolist() for k in ("open", "high", "low", "close"))
    V = m15["volume"].astype(float).tolist()
    P = {k: prep[k].tolist() for k in prep.columns}
    L, tick = core.swing_len, core.tick
    s = _State()
    rows: dict[str, list] = {k: [] for k in _ROW_KEYS}
    events: list[dict] = []
    w_sum = ctx.w_str + ctx.w_loc + ctx.w_conf + ctx.w_time

    for t in range(len(C)):
        o, h, l, c = O[t], H[t], Lo[t], C[t]
        atr = P["atr"][t]

        # 1-2. Swings (core:251-270)
        ph, pl = P["ph"][t], P["pl"][t]
        if not isna(ph):
            s.ph2, s.ph1, s.ph1_bar, s.swing_h_consumed = s.ph1, ph, t - L, False
        if not isna(pl):
            s.pl2, s.pl1, s.pl1_bar, s.swing_l_consumed = s.pl1, pl, t - L, False
        two_h = not isna(s.ph1) and not isna(s.ph2)
        two_l = not isna(s.pl1) and not isna(s.pl2)
        hh, lh = two_h and s.ph1 > s.ph2, two_h and s.ph1 < s.ph2
        hl, ll = two_l and s.pl1 > s.pl2, two_l and s.pl1 < s.pl2

        # 3. Breaks (core:272-285): all four read struct_dir before it changes.
        ph_unused = not isna(s.ph1) and (s.used_ph_bar is None or s.ph1_bar != s.used_ph_bar)
        pl_unused = not isna(s.pl1) and (s.used_pl_bar is None or s.pl1_bar != s.used_pl_bar)
        bos_bull = s.struct_dir >= 0 and ph_unused and c > s.ph1
        choch_bull = s.struct_dir == -1 and ph_unused and c > s.ph1
        bos_bear = s.struct_dir <= 0 and pl_unused and c < s.pl1
        choch_bear = s.struct_dir == 1 and pl_unused and c < s.pl1
        bull_break_price = s.ph1 if (bos_bull or choch_bull) else NAN
        bear_break_price = s.pl1 if (bos_bear or choch_bear) else NAN
        if bos_bull or choch_bull:
            s.used_ph_bar, s.struct_dir = s.ph1_bar, 1
        if bos_bear or choch_bear:
            s.used_pl_bar, s.struct_dir = s.pl1_bar, -1

        # 4. Bias (core:287-292)
        raw = (1 if hh else 0) + (1 if hl else 0) - (1 if lh else 0) - (1 if ll else 0)
        e20, e50 = P["ema20"][t], P["ema50"][t]
        ema_pts = 1 if (c > e20 and e20 > e50) else -1 if (c < e20 and e20 < e50) else 0
        trend = resolve_bias(raw, s.struct_dir, ema_pts, core.break_fallback)
        swing_conflict = s.struct_dir != 0 and s.struct_dir * raw < 0

        # 5. Level maintenance (core:304-388)
        levels = s.levels
        if levels:
            rng = max(h - l, tick)
            i = 0
            while i < len(levels):
                lv = levels[i]
                remove = False
                intersects = l <= lv.price and h >= lv.price
                new_test = intersects and not lv.in_contact
                if lv.state == ST_CAND:
                    if t - lv.born_bar > core.flip_max_age:
                        remove = True
                    elif lv.role == 1:
                        if c < lv.price:
                            remove = True
                        elif intersects:
                            if new_test:
                                lv.touches += 1
                            lv.wick = min(lv.price if isna(lv.wick) else lv.wick, l)
                            lower_ok = (min(o, c) - l) / rng >= core.flip_wick / 100.0
                            if c > lv.price and (c > o or lower_ok):
                                lv.state, lv.touches = ST_FLIP, 1
                                events.append({"bar": t, "event": EVT_FLIP_TO_SUP, "id": lv.id, "price": lv.price})
                    else:
                        if c > lv.price:
                            remove = True
                        elif intersects:
                            if new_test:
                                lv.touches += 1
                            lv.wick = max(lv.price if isna(lv.wick) else lv.wick, h)
                            upper_ok = (h - max(o, c)) / rng >= core.flip_wick / 100.0
                            if c < lv.price and (c < o or upper_ok):
                                lv.state, lv.touches = ST_FLIP, 1
                                events.append({"bar": t, "event": EVT_FLIP_TO_RES, "id": lv.id, "price": lv.price})
                elif lv.role == -1:
                    if c > lv.price:
                        if core.flip_on and lv.state != ST_FLIP:
                            lv.role, lv.state, lv.born_bar, lv.kind, lv.touches, lv.wick = 1, ST_CAND, t, "Flip", 0, NAN
                        else:
                            remove = True
                    elif intersects:
                        lv.wick = max(lv.price if isna(lv.wick) else lv.wick, h)
                        if new_test:
                            lv.touches += 1
                            if lv.state == ST_FRESH:
                                lv.state = ST_TAPPED
                                events.append({"bar": t, "event": EVT_TAP_RES, "id": lv.id, "price": lv.price})
                else:
                    if c < lv.price:
                        if core.flip_on and lv.state != ST_FLIP:
                            lv.role, lv.state, lv.born_bar, lv.kind, lv.touches, lv.wick = -1, ST_CAND, t, "Flip", 0, NAN
                        else:
                            remove = True
                    elif intersects:
                        lv.wick = min(lv.price if isna(lv.wick) else lv.wick, l)
                        if new_test:
                            lv.touches += 1
                            if lv.state == ST_FRESH:
                                lv.state = ST_TAPPED
                                events.append({"bar": t, "event": EVT_TAP_SUP, "id": lv.id, "price": lv.price})
                if remove:
                    levels.pop(i)
                else:
                    lv.in_contact = intersects
                    i += 1
            _trim_role(levels, 1, core.zone_count)
            _trim_role(levels, -1, core.zone_count)

        # 6. New body pivots, A then V (core:390-403). A merge happens only for a valid pivot.
        for role, price, kind in ((-1, P["a_lvl"][t], "A"), (1, P["v_lvl"][t], "V")):
            if isna(price):
                continue
            touches0, wick0, valid0 = _pivot_history(role, price, L, t, O, H, Lo, C, tick)
            if valid0 and not _merge_into(levels, core.cluster_on, core.cluster_atr, atr, role, price, tick):
                levels.append(Level(s.next_id, price, role, ST_FRESH if touches0 == 0 else ST_TAPPED, touches0,
                                    wick0, t - L, t, kind, l <= price and h >= price))
                s.next_id += 1
                _trim_role(levels, role, core.zone_count)

        # 7. Nearest levels (core:405-440)
        n_sup = n_res = NAN
        sup_lv = res_lv = None
        min_low_d = min_high_d = NAN
        for lv in levels:
            if lv.state == ST_CAND:
                continue
            if lv.role == 1:
                if lv.price <= c and (isna(n_sup) or lv.price > n_sup):
                    n_sup, sup_lv = lv.price, lv
                d = abs(l - lv.price)
                if isna(min_low_d) or d < min_low_d:
                    min_low_d = d
            else:
                if lv.price >= c and (isna(n_res) or lv.price < n_res):
                    n_res, res_lv = lv.price, lv
                d = abs(h - lv.price)
                if isna(min_high_d) or d < min_high_d:
                    min_high_d = d

        # 8. Equal highs/lows (core:442-488)
        tol = atr * core.eq_atr
        i = 0
        while i < len(s.eq_h_v):
            if h > s.eq_h_v[i]:
                s.eq_h_v.pop(i); s.eq_h_b.pop(i)
            else:
                i += 1
        i = 0
        while i < len(s.eq_l_v):
            if l < s.eq_l_v[i]:
                s.eq_l_v.pop(i); s.eq_l_b.pop(i)
            else:
                i += 1
        for is_high, piv in ((True, ph), (False, pl)):
            if isna(piv):
                continue
            vals, bars, pools = (s.eq_h_v, s.eq_h_b, s.eqh_pool) if is_high else (s.eq_l_v, s.eq_l_b, s.eql_pool)
            pool = NAN
            for price in vals:
                if abs(piv - price) <= tol:
                    edge = max(piv, price) if is_high else min(piv, price)
                    pool = edge if isna(pool) else (max(pool, edge) if is_high else min(pool, edge))
            if not isna(pool) and pool not in pools:
                pools.append(pool)
                if len(pools) > 8:
                    pools.pop(0)
            vals.append(piv); bars.append(t - L)
            if len(vals) > 10:
                vals.pop(0); bars.pop(0)

        # 9. Equal high/low pool sweeps (core:490-516)
        eqh_swept = eql_swept = False
        j = 0
        while j < len(s.eqh_pool):
            price = s.eqh_pool[j]
            if h > price:
                if c < price:
                    eqh_swept = True
                s.eqh_pool.pop(j)
            else:
                j += 1
        j = 0
        while j < len(s.eql_pool):
            price = s.eql_pool[j]
            if l < price:
                if c > price:
                    eql_swept = True
                s.eql_pool.pop(j)
            else:
                j += 1

        # 10. Previous day/week (core:518-554)
        pd_h, pd_l, pw_h, pw_l = P["pd_h"][t], P["pd_l"][t], P["pw_h"][t], P["pw_l"][t]
        if P["new_day"][t] or isna(s.last_pd_h):
            s.pdh_consumed = False
        if P["new_day"][t] or isna(s.last_pd_l):
            s.pdl_consumed = False
        if P["new_week"][t] or isna(s.last_pw_h):
            s.pwh_consumed = False
        if P["new_week"][t] or isna(s.last_pw_l):
            s.pwl_consumed = False
        s.last_pd_h, s.last_pd_l, s.last_pw_h, s.last_pw_l = pd_h, pd_l, pw_h, pw_l
        pdh_swept = not isna(pd_h) and not s.pdh_consumed and h > pd_h and c < pd_h and c < o
        pdl_swept = not isna(pd_l) and not s.pdl_consumed and l < pd_l and c > pd_l and c > o
        pwh_swept = not isna(pw_h) and not s.pwh_consumed and h > pw_h and c < pw_h and c < o
        pwl_swept = not isna(pw_l) and not s.pwl_consumed and l < pw_l and c > pw_l and c > o
        if not isna(pd_h) and h > pd_h:
            s.pdh_consumed = True
        if not isna(pd_l) and l < pd_l:
            s.pdl_consumed = True
        if not isna(pw_h) and h > pw_h:
            s.pwh_consumed = True
        if not isna(pw_l) and l < pw_l:
            s.pwl_consumed = True

        # 11. Swing sweeps and qualification (core:556-569)
        sw_bull = not s.swing_l_consumed and not isna(s.pl1) and l < s.pl1 and c > s.pl1 and c > o
        sw_bear = not s.swing_h_consumed and not isna(s.ph1) and h > s.ph1 and c < s.ph1 and c < o
        if not isna(s.ph1) and h > s.ph1:
            s.swing_h_consumed = True
        if not isna(s.pl1) and l < s.pl1:
            s.swing_l_consumed = True
        bull_sweep = sw_bull or eql_swept or pdl_swept or pwl_swept
        bear_sweep = sw_bear or eqh_swept or pdh_swept or pwh_swept
        bull_src = " ".join(n for n, f in (("swing_low", sw_bull), ("eql", eql_swept), ("pdl", pdl_swept), ("pwl", pwl_swept)) if f)
        bear_src = " ".join(n for n, f in (("swing_high", sw_bear), ("eqh", eqh_swept), ("pdh", pdh_swept), ("pwh", pwh_swept)) if f)
        bull_sweep_q = bull_sweep and not isna(min_low_d) and min_low_d <= core.sweep_snr_atr * atr
        bear_sweep_q = bear_sweep and not isna(min_high_d) and min_high_d <= core.sweep_snr_atr * atr

        # ── Context (context:97-208)
        bias_ok_bull, bias_ok_bear = trend > 0, trend < 0
        obs_bull = obs_bear = NAN
        for lv in levels:
            if lv.role == -1 and lv.state != ST_CAND:
                obs_bull = _pick_obstacle(1, c, obs_bull, lv.price)
        for px in s.eqh_pool:
            obs_bull = _pick_obstacle(1, c, obs_bull, px)
        obs_bull = _pick_obstacle(1, c, obs_bull, pd_h)
        obs_bull = _pick_obstacle(1, c, obs_bull, pw_h)
        for lv in levels:
            if lv.role == 1 and lv.state != ST_CAND:
                obs_bear = _pick_obstacle(-1, c, obs_bear, lv.price)
        for px in s.eql_pool:
            obs_bear = _pick_obstacle(-1, c, obs_bear, px)
        obs_bear = _pick_obstacle(-1, c, obs_bear, pd_l)
        obs_bear = _pick_obstacle(-1, c, obs_bear, pw_l)
        atr_ok = not isna(atr) and atr > 0
        space_ok_bull = not isna(obs_bull) and atr_ok and (obs_bull - c) >= ctx.space_mult * atr
        space_ok_bear = not isna(obs_bear) and atr_ok and (c - obs_bear) >= ctx.space_mult * atr

        if bull_sweep_q:
            s.bull_sweep_bar1, s.bull_sweep_src = t, bull_src
        if bear_sweep_q:
            s.bear_sweep_bar1, s.bear_sweep_src = t, bear_src
        since_bull_sweep = None if s.bull_sweep_bar1 is None else t - s.bull_sweep_bar1
        since_bear_sweep = None if s.bear_sweep_bar1 is None else t - s.bear_sweep_bar1
        sweep_ok_bull = since_bull_sweep is not None and since_bull_sweep <= ctx.sweep_bos_win
        sweep_ok_bear = since_bear_sweep is not None and since_bear_sweep <= ctx.sweep_bos_win

        if bos_bull:
            s.last_bull_bos_bar = t
        if bos_bear or choch_bear:
            s.last_bull_bos_bar = None
        if bos_bear:
            s.last_bear_bos_bar = t
        if bos_bull or choch_bull:
            s.last_bear_bos_bar = None
        struct_ok_bull = s.last_bull_bos_bar is not None and t - s.last_bull_bos_bar <= ctx.confl_window
        struct_ok_bear = s.last_bear_bos_bar is not None and t - s.last_bear_bos_bar <= ctx.confl_window

        if bos_bull:
            s.bull_bos_had_sweep = sweep_ok_bull
            s.bull_bos_sweep_src = s.bull_sweep_src if sweep_ok_bull else ""
        if bos_bear or choch_bear:
            s.bull_bos_had_sweep, s.bull_bos_sweep_src = False, ""
        if bos_bear:
            s.bear_bos_had_sweep = sweep_ok_bear
            s.bear_bos_sweep_src = s.bear_sweep_src if sweep_ok_bear else ""
        if bos_bull or choch_bull:
            s.bear_bos_had_sweep, s.bear_bos_sweep_src = False, ""

        at_sup = not isna(n_sup) and (c - n_sup) <= atr
        at_res = not isna(n_res) and (n_res - c) <= atr
        sweep_gate_bull = not ctx.require_sweep or s.bull_bos_had_sweep
        sweep_gate_bear = not ctx.require_sweep or s.bear_bos_had_sweep
        long_zone = s.struct_dir == 1 and at_sup and bias_ok_bull and struct_ok_bull and space_ok_bull and sweep_gate_bull
        short_zone = s.struct_dir == -1 and at_res and bias_ok_bear and struct_ok_bear and space_ok_bear and sweep_gate_bear
        conflict = swing_conflict and not long_zone and not short_zone
        fail_bull = ((GZ_DIRECTION if s.struct_dir != 1 else 0) | (GZ_LOCATION if not at_sup else 0)
                     | (GZ_BIAS if not bias_ok_bull else 0) | (GZ_BOS if not struct_ok_bull else 0)
                     | (GZ_ROOM if not space_ok_bull else 0) | (GZ_SWEEP if not sweep_gate_bull else 0))
        fail_bear = ((GZ_DIRECTION if s.struct_dir != -1 else 0) | (GZ_LOCATION if not at_res else 0)
                     | (GZ_BIAS if not bias_ok_bear else 0) | (GZ_BOS if not struct_ok_bear else 0)
                     | (GZ_ROOM if not space_ok_bear else 0) | (GZ_SWEEP if not sweep_gate_bear else 0))

        sup_q = 0.0 if sup_lv is None else level_quality(sup_lv.state == ST_FLIP, sup_lv.state == ST_FRESH, sup_lv.touches)
        res_q = 0.0 if res_lv is None else level_quality(res_lv.state == ST_FLIP, res_lv.state == ST_FRESH, res_lv.touches)

        rng_full = h - l
        bull_rej_raw = c > o and (min(o, c) - l) >= rng_full * 0.5
        bear_rej_raw = c < o and (h - max(o, c)) >= rng_full * 0.5
        rej_near_bull = not isna(min_low_d) and min_low_d <= ctx.rej_atr * atr
        rej_near_bear = not isna(min_high_d) and min_high_d <= ctx.rej_atr * atr
        if bull_rej_raw and (rej_near_bull or bull_sweep):
            s.last_bull_rej = t
        if bear_rej_raw and (rej_near_bear or bear_sweep):
            s.last_bear_rej = t
        rej_ok_bull = s.last_bull_rej is not None and t - s.last_bull_rej <= ctx.conf_cluster
        rej_ok_bear = s.last_bear_rej is not None and t - s.last_bear_rej <= ctx.conf_cluster
        sweep_ok_bull_c = since_bull_sweep is not None and since_bull_sweep <= ctx.conf_cluster
        sweep_ok_bear_c = since_bear_sweep is not None and since_bear_sweep <= ctx.conf_cluster

        vol, vsma = V[t], P["vol_sma20"][t]
        vol_on = not isna(vol) and vol > 0 and not isna(vsma) and vsma > 0
        if vol_on and c > o and vol > vsma * 1.2:
            s.last_vspike_bull = t
        if vol_on and c < o and vol > vsma * 1.2:
            s.last_vspike_bear = t
        vol_ok_bull = vol_on and s.last_vspike_bull is not None and t - s.last_vspike_bull <= ctx.conf_cluster
        vol_ok_bear = vol_on and s.last_vspike_bear is not None and t - s.last_vspike_bear <= ctx.conf_cluster
        killzone_ok = P["in_london"][t] or P["in_ny"][t]

        str_bull = int(bias_ok_bull) + int(struct_ok_bull) + int(hh or hl)
        str_bear = int(bias_ok_bear) + int(struct_ok_bear) + int(lh or ll)
        loc_bull = (1.0 if at_sup else 0.0) + sup_q + (1.0 if space_ok_bull else 0.0)
        loc_bear = (1.0 if at_res else 0.0) + res_q + (1.0 if space_ok_bear else 0.0)
        conf_bull = int(sweep_ok_bull_c) + int(rej_ok_bull) + int(vol_ok_bull)
        conf_bear = int(sweep_ok_bear_c) + int(rej_ok_bear) + int(vol_ok_bear)
        conf_den = 3.0 if vol_on else 2.0
        time_n = 1 if killzone_ok else 0
        raw_bull = (str_bull / 3.0 * ctx.w_str + loc_bull / 3.0 * ctx.w_loc + conf_bull / conf_den * ctx.w_conf + time_n * ctx.w_time) / w_sum * 100
        raw_bear = (str_bear / 3.0 * ctx.w_str + loc_bear / 3.0 * ctx.w_loc + conf_bear / conf_den * ctx.w_conf + time_n * ctx.w_time) / w_sum * 100
        req_sweep_bull = s.bull_bos_had_sweep if struct_ok_bull else sweep_ok_bull
        req_sweep_bear = s.bear_bos_had_sweep if struct_ok_bear else sweep_ok_bear
        gate_bull = str_bull == 0 or (ctx.require_sweep and not req_sweep_bull) or isna(n_sup)
        gate_bear = str_bear == 0 or (ctx.require_sweep and not req_sweep_bear) or isna(n_res)
        score_bull = min(raw_bull, ctx.gate_cap) if gate_bull else raw_bull
        score_bear = min(raw_bear, ctx.gate_cap) if gate_bear else raw_bear

        sd = s.struct_dir
        story = (0 if conflict else 1 if long_zone else 2 if short_zone else 9 if sd == 0
                 else 3 if sd == 1 and at_sup else 4 if sd == 1 and at_res else 5 if sd == 1
                 else 6 if sd == -1 and at_res else 7 if sd == -1 and at_sup else 8)

        if hook is not None:
            hook(t, levels, s.eqh_pool, s.eql_pool, pd_h, pd_l, pw_h, pw_l, atr, c)
        if trace is not None:
            trace.append(([(lv.id, lv.price, lv.role, lv.state, lv.touches, lv.wick, lv.born_bar, lv.in_contact)
                           for lv in levels], list(s.eqh_pool), list(s.eql_pool)))

        for k, v in (
            ("atr", atr), ("struct_dir", sd), ("hh", hh), ("lh", lh), ("hl", hl), ("ll", ll),
            ("bos_bull", bos_bull), ("bos_bear", bos_bear), ("choch_bull", choch_bull), ("choch_bear", choch_bear),
            ("bull_break_price", bull_break_price), ("bear_break_price", bear_break_price),
            ("trend_score", trend), ("swing_conflict", swing_conflict),
            ("n_levels", len(levels)),
            ("sup", n_sup), ("sup_id", -1 if sup_lv is None else sup_lv.id),
            ("sup_state", -1 if sup_lv is None else sup_lv.state), ("sup_touches", 0 if sup_lv is None else sup_lv.touches),
            ("sup_wick", NAN if sup_lv is None else sup_lv.wick),
            ("res", n_res), ("res_id", -1 if res_lv is None else res_lv.id),
            ("res_state", -1 if res_lv is None else res_lv.state), ("res_touches", 0 if res_lv is None else res_lv.touches),
            ("res_wick", NAN if res_lv is None else res_lv.wick),
            ("min_low_dist_sup", min_low_d), ("min_high_dist_res", min_high_d),
            ("pd_h", pd_h), ("pd_l", pd_l), ("pw_h", pw_h), ("pw_l", pw_l),
            ("bull_sweep", bull_sweep), ("bear_sweep", bear_sweep), ("bull_sweep_q", bull_sweep_q), ("bear_sweep_q", bear_sweep_q),
            ("bull_sweep_src", bull_src), ("bear_sweep_src", bear_src),
            ("obstacle_bull", obs_bull), ("obstacle_bear", obs_bear),
            ("space_ok_bull", space_ok_bull), ("space_ok_bear", space_ok_bear),
            ("bull_sweep_age", -1 if since_bull_sweep is None else since_bull_sweep),
            ("bear_sweep_age", -1 if since_bear_sweep is None else since_bear_sweep),
            ("bull_bos_age", -1 if s.last_bull_bos_bar is None else t - s.last_bull_bos_bar),
            ("bear_bos_age", -1 if s.last_bear_bos_bar is None else t - s.last_bear_bos_bar),
            ("struct_ok_bull", struct_ok_bull), ("struct_ok_bear", struct_ok_bear),
            ("bull_bos_had_sweep", s.bull_bos_had_sweep), ("bear_bos_had_sweep", s.bear_bos_had_sweep),
            ("bull_bos_sweep_src", s.bull_bos_sweep_src), ("bear_bos_sweep_src", s.bear_bos_sweep_src),
            ("at_sup", at_sup), ("at_res", at_res), ("long_zone", long_zone), ("short_zone", short_zone),
            ("gz_fail_bull", fail_bull), ("gz_fail_bear", fail_bear),
            ("rej_ok_bull", rej_ok_bull), ("rej_ok_bear", rej_ok_bear), ("vol_ok_bull", vol_ok_bull), ("vol_ok_bear", vol_ok_bear),
            ("score_bull", score_bull), ("score_bear", score_bear), ("gate_bull", gate_bull), ("gate_bear", gate_bear),
            ("story", story),
            ("in_asian", P["in_asian"][t]), ("in_london", P["in_london"][t]), ("in_ny", P["in_ny"][t]),
        ):
            rows[k].append(v)

    out = pd.DataFrame(rows, index=m15.index)
    return out, events


_ROW_KEYS = [
    "atr", "struct_dir", "hh", "lh", "hl", "ll", "bos_bull", "bos_bear", "choch_bull", "choch_bear",
    "bull_break_price", "bear_break_price", "trend_score", "swing_conflict", "n_levels",
    "sup", "sup_id", "sup_state", "sup_touches", "sup_wick", "res", "res_id", "res_state", "res_touches", "res_wick",
    "min_low_dist_sup", "min_high_dist_res", "pd_h", "pd_l", "pw_h", "pw_l",
    "bull_sweep", "bear_sweep", "bull_sweep_q", "bear_sweep_q", "bull_sweep_src", "bear_sweep_src",
    "obstacle_bull", "obstacle_bear", "space_ok_bull", "space_ok_bear",
    "bull_sweep_age", "bear_sweep_age", "bull_bos_age", "bear_bos_age",
    "struct_ok_bull", "struct_ok_bear", "bull_bos_had_sweep", "bear_bos_had_sweep",
    "bull_bos_sweep_src", "bear_bos_sweep_src",
    "at_sup", "at_res", "long_zone", "short_zone", "gz_fail_bull", "gz_fail_bear",
    "rej_ok_bull", "rej_ok_bear", "vol_ok_bull", "vol_ok_bear",
    "score_bull", "score_bear", "gate_bull", "gate_bear", "story", "in_asian", "in_london", "in_ny",
]


def _pivot_history(role: int, price: float, length: int, t: int, O, H, Lo, C, tick: float) -> tuple[int, float, bool]:
    """f_pivot_history (core:200-211), on candles t - length .. t."""
    touches = 0
    wick = Lo[t - length] if role == 1 else H[t - length]
    valid = True
    for j in range(length):
        k = t - j
        if role * (C[k] - price) < 0:
            valid = False
        if Lo[k] <= price and H[k] >= price:
            wick = min(wick, Lo[k]) if role == 1 else max(wick, H[k])
            if j == length - 1:
                counted = opened_away(role, O[k], price, tick)
            else:
                counted = not (Lo[k - 1] <= price and H[k - 1] >= price)
            if counted:
                touches += 1
    return touches, wick, valid


# ── f_bias_score on higher timeframes (mtf.pine:8-44) ───────────────────

def bias_scores(candles: pd.DataFrame, core: CoreParams = CoreParams()) -> np.ndarray:
    """The chart bias rules run on another timeframe's candles; one score per candle."""
    h, l, c = (candles[k].to_numpy(float) for k in ("high", "low", "close"))
    L = core.swing_len
    PH, PL = pivots(h, L, L, True, core.pivot_ties), pivots(l, L, L, False, core.pivot_ties)
    E20, E50 = pine_ema(c, 20), pine_ema(c, 50)
    ph1 = ph2 = pl1 = pl2 = NAN
    ph1_bar = pl1_bar = -1
    used_ph = used_pl = None
    sd = 0
    out = np.full(len(c), np.nan)
    for t in range(len(c)):
        if not isna(PH[t]):
            ph2, ph1, ph1_bar = ph1, PH[t], t - L
        if not isna(PL[t]):
            pl2, pl1, pl1_bar = pl1, PL[t], t - L
        two_h, two_l = not isna(ph1) and not isna(ph2), not isna(pl1) and not isna(pl2)
        raw = (1 if two_h and ph1 > ph2 else 0) + (1 if two_l and pl1 > pl2 else 0) \
            - (1 if two_h and ph1 < ph2 else 0) - (1 if two_l and pl1 < pl2 else 0)
        ph_unused = not isna(ph1) and (used_ph is None or ph1_bar != used_ph)
        pl_unused = not isna(pl1) and (used_pl is None or pl1_bar != used_pl)
        if ph_unused and c[t] > ph1:
            used_ph, sd = ph1_bar, 1
        if pl_unused and c[t] < pl1:
            used_pl, sd = pl1_bar, -1
        e20, e50 = E20[t], E50[t]
        ema_pts = 1 if (c[t] > e20 and e20 > e50) else -1 if (c[t] < e20 and e20 < e50) else 0
        out[t] = resolve_bias(raw, sd, ema_pts, core.break_fallback)
    return out


def htf_context(m15: pd.DataFrame, core: CoreParams = CoreParams()) -> pd.DataFrame:
    """4H and 1H bias scores as the 15m chart sees them (closed candles only, mtf.pine:51-67)."""
    out = {}
    for tf, name in (("4H", "h4"), ("1H", "h1")):
        htf = aggregate(m15, tf)
        htf = htf.assign(score=bias_scores(htf, core))
        out[name] = align(m15, htf, ["score"], at="close")["score"].to_numpy(float)
    return pd.DataFrame(out, index=m15.index)


def mtf_state(h4: float, h1: float, m15: float) -> float:
    """f_mtf_state (mtf:75-79): +1 / -1 when all three agree, 0 otherwise, NaN if unknown."""
    if isna(h4) or isna(h1) or isna(m15):
        return NAN
    return 1.0 if (h4 > 0 and h1 > 0 and m15 > 0) else -1.0 if (h4 < 0 and h1 < 0 and m15 < 0) else 0.0


def params_dict(core: CoreParams, ctx: ContextParams) -> dict:
    return {"core": asdict(core), "context": asdict(ctx)}
