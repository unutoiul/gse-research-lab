"""Candidate setups from the structure port.

R001's candidate is a Golden Zone that turns on at a candle close (off at the
previous close). Each candidate carries what the execution model and the
reports need, all known at that close.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .structure import GZ_NAMES


def session_code(in_asian: pd.Series, in_london: pd.Series, in_ny: pd.Series) -> pd.Series:
    """indicator.pine:222 session codes (the webhook spells the overlap LDN-NY)."""
    return pd.Series(np.select([in_london & in_ny, in_ny, in_london, in_asian], ["LDN-NY", "NY", "LDN", "ASIA"], "OFF"),
                     index=in_asian.index)


def htf_stratum(h4: float, h1: float, side: int) -> str:
    """4H/1H bias relative to the trade side: aligned, partial, neutral, opposed (or unknown)."""
    if np.isnan(h4) or np.isnan(h1):
        return "unknown"
    s4, s1 = np.sign(h4) * side, np.sign(h1) * side
    if s4 < 0 or s1 < 0:
        return "opposed"
    if s4 > 0 and s1 > 0:
        return "aligned"
    if s4 > 0 or s1 > 0:
        return "partial"
    return "neutral"


def golden_zone_candidates(m15: pd.DataFrame, out: pd.DataFrame, htf: pd.DataFrame) -> pd.DataFrame:
    """One row per Golden Zone turning on at a close, per side."""
    rows = []
    session = session_code(out["in_asian"], out["in_london"], out["in_ny"])
    for side, zone, lvl, obstacle, had, src in ((1, "long_zone", "sup", "obstacle_bull", "bull_bos_had_sweep", "bull_bos_sweep_src"),
                                                 (-1, "short_zone", "res", "obstacle_bear", "bear_bos_had_sweep", "bear_bos_sweep_src")):
        on = out[zone] & ~out[zone].shift(fill_value=False)
        for i in np.flatnonzero(on.to_numpy()):
            rows.append({
                "bar": int(i), "time": m15["time"].iat[i], "side": side,
                "close": m15["close"].iat[i], "atr": out["atr"].iat[i],
                "level": out[lvl].iat[i], "level_id": int(out[f"{lvl}_id"].iat[i]),
                "level_state": int(out[f"{lvl}_state"].iat[i]), "level_touches": int(out[f"{lvl}_touches"].iat[i]),
                "level_wick": out[f"{lvl}_wick"].iat[i], "obstacle": out[obstacle].iat[i],
                "bos_had_sweep": bool(out[had].iat[i]), "sweep_source": out[src].iat[i],
                "trend_score": out["trend_score"].iat[i], "score": out["score_bull" if side == 1 else "score_bear"].iat[i],
                "h4": htf["h4"].iat[i], "h1": htf["h1"].iat[i],
                "stratum": htf_stratum(htf["h4"].iat[i], htf["h1"].iat[i], side),
                "session": session.iat[i],
            })
    cols = ["bar", "time", "side", "close", "atr", "level", "level_id", "level_state", "level_touches", "level_wick",
            "obstacle", "bos_had_sweep", "sweep_source", "trend_score", "score", "h4", "h1", "stratum", "session"]
    return pd.DataFrame(rows, columns=cols).sort_values(["bar", "side"], ignore_index=True)


def golden_zone_funnel(out: pd.DataFrame, mask: pd.Series | None = None) -> pd.DataFrame:
    """Candles per side by the FIRST failing Golden Zone condition (audit 4.1 order), and how many qualify."""
    mask = pd.Series(True, index=out.index) if mask is None else mask
    rows = []
    for side, col in (("long", "gz_fail_bull"), ("short", "gz_fail_bear")):
        fail = out.loc[mask, col].to_numpy()
        total = len(fail)
        remaining = total
        first = np.zeros(len(fail), dtype=int)
        for bit in GZ_NAMES:  # ascending bit = audit order
            hit = (fail & bit).astype(bool) & (first == 0)
            first[hit] = bit
        for bit, name in GZ_NAMES.items():
            n = int((first == bit).sum())
            rows.append({"side": side, "stage": name, "rejected": n, "share_of_candles": n / total if total else np.nan,
                         "remaining": remaining - n})
            remaining -= n
        rows.append({"side": side, "stage": "qualified", "rejected": 0, "share_of_candles": remaining / total if total else np.nan,
                     "remaining": remaining})
    return pd.DataFrame(rows)
