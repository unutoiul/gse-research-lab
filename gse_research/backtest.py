"""Research execution model RXM-1 (R001_PLAN.md). Labelled research model, not GSE behaviour.

GSE v4.0 defines no entry or exit. RXM-1, the same for every arm:
- Entry: the next candle's open after the signal close. Longs buy at the ask,
  shorts sell at the bid, plus adverse slippage.
- Stop: the anchoring level's wick -/+ max(tick, 0.20 x ATR), rounded outward
  (the website's invalidation buffer). Longs are stopped on the bid, shorts on the ask.
- Target: the first opposing obstacle at the signal -/+ max(tick, 0.10 x ATR),
  rounded toward entry (the website's target clearance). A limit: no slippage.
- A candle opening beyond the stop or target exits at that open.
- A candle reaching both stop and target counts as a stop (order inside a candle is unknown).
- Time limit: `max_bars` candles including the entry candle, then exit at that close.
Every fill uses OANDA's bid/ask candles, so the spread is paid on entry and exit.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Execution:
    name: str = "RXM-1"
    stop_buffer_atr: float = 0.20
    target_clearance_atr: float = 0.10
    max_bars: int = 16
    slippage: float = 0.0  # price units, adverse, on market entries, stops and time exits
    tick: float = 0.01


def _round(price: float, tick: float, down: bool) -> float:
    q = price / tick
    return round((math.floor(q + 1e-9) if down else math.ceil(q - 1e-9)) * tick, 10)


def simulate(m15: pd.DataFrame, candidates: pd.DataFrame, ex: Execution = Execution()) -> pd.DataFrame:
    """One row per candidate with entry, stop, target, exit, R, MFE/MAE (in R) and the exit reason."""
    bo, bh, bl, bc = (m15[f"bid_{k}"].to_numpy(float) for k in ("open", "high", "low", "close"))
    ao, ah, al, ac = (m15[f"ask_{k}"].to_numpy(float) for k in ("open", "high", "low", "close"))
    times = m15["time"]
    n = len(m15)
    out = []
    for cand in candidates.itertuples(index=False):
        d, i = cand.side, cand.bar
        rec = cand._asdict()
        e = i + 1
        if e >= n or np.isnan(cand.atr) or np.isnan(cand.obstacle):
            out.append({**rec, "reason": "no_entry"})
            continue
        wick = cand.level if np.isnan(cand.level_wick) else cand.level_wick
        edge = min(cand.level, wick) if d == 1 else max(cand.level, wick)
        stop = _round(edge - d * max(ex.tick, ex.stop_buffer_atr * cand.atr), ex.tick, down=d == 1)
        target = _round(cand.obstacle - d * max(ex.tick, ex.target_clearance_atr * cand.atr), ex.tick, down=d == 1)
        entry = ao[e] + ex.slippage if d == 1 else bo[e] - ex.slippage
        risk = d * (entry - stop)
        rec.update(entry_time=times.iat[e], entry=entry, stop=stop, target=target, risk=risk,
                   gap_hours=(times.iat[e] - times.iat[i]).total_seconds() / 3600 - 0.25,
                   spread_R=(ao[e] - bo[e]) / risk if risk > 0 else np.nan)
        if risk <= 0 or d * (target - entry) <= 0:
            out.append({**rec, "reason": "invalid_geometry"})
            continue
        # Exit side: longs sell at the bid, shorts buy at the ask.
        xo, xh, xl, xc = (bo, bh, bl, bc) if d == 1 else (ao, ah, al, ac)
        best = worst = 0.0
        reason, exit_px, k = None, np.nan, e
        last = min(e + ex.max_bars - 1, n - 1)
        for k in range(e, last + 1):
            # A candle (the entry candle included) that opens beyond the stop or the target fills at its open.
            if d * (xo[k] - stop) <= 0:
                reason, exit_px = "stop_gap", xo[k] - d * ex.slippage
                break
            if d * (xo[k] - target) >= 0:
                reason, exit_px = "target_gap", xo[k]
                break
            fav, adv = (xh[k], xl[k]) if d == 1 else (xl[k], xh[k])
            best = max(best, d * (fav - entry))
            worst = max(worst, d * (entry - adv))
            hit_stop = d * (adv - stop) <= 0
            hit_target = d * (fav - target) >= 0
            if hit_stop:
                reason, exit_px = ("stop_and_target" if hit_target else "stop"), stop - d * ex.slippage
                break
            if hit_target:
                reason, exit_px = "target", target
                break
        else:
            if last - e + 1 < ex.max_bars:
                out.append({**rec, "reason": "open_at_data_end"})
                continue
            reason, exit_px, k = "time", xc[last] - d * ex.slippage, last
        R = d * (exit_px - entry) / risk
        # Adverse excursion past a stop is not experienced (the trade is out), except through a gap.
        out.append({**rec, "exit_time": times.iat[k], "exit": exit_px, "reason": reason, "bars_held": k - e + 1,
                    "R": R, "planned_rr": d * (target - entry) / risk,
                    "mfe_R": best / risk, "mae_R": min(worst / risk, max(1.0, -R))})
    return pd.DataFrame(out)


def one_open_per_side(trades: pd.DataFrame) -> pd.DataFrame:
    """Keep a trade only if no earlier kept trade on the same side is still open at its entry."""
    keep = []
    busy_until = {1: None, -1: None}
    for row in trades.sort_values("entry_time").itertuples():
        until = busy_until[row.side]
        if until is None or row.entry_time >= until:
            keep.append(row.Index)
            busy_until[row.side] = row.exit_time
    return trades.loc[sorted(keep)]


def execution_dict(ex: Execution) -> dict:
    return asdict(ex)
