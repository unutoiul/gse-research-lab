"""Per-year data quality of the M15 cache.

A gold trading day (18:00 to 17:00 New York) has 92 fifteen-minute candles.
Coverage compares the candles present with that, on the days that traded.
Thin candles (volume of 1 or 2 ticks) and flat candles (no range) mean the
feed had too few prices to show real structure. Spread is the ask-bid gap at
the candle close; cost ratio is the median spread over the median candle range.
"""

from __future__ import annotations

import pandas as pd

from .data import _session_clock

CANDLES_PER_DAY = 92


def year_report(m15: pd.DataFrame) -> pd.DataFrame:
    df = m15.copy()
    df["year"] = df["time"].dt.year
    df["tday"] = _session_clock(df["time"]).dt.floor("D")
    df["range"] = df["high"] - df["low"]
    same_day = df["tday"].eq(df["tday"].shift())
    df["gap"] = same_day & (df["time"].diff() > pd.Timedelta(minutes=30))
    rows = []
    for year, y in df.groupby("year"):
        days = y["tday"].nunique()
        coverage = len(y) / (days * CANDLES_PER_DAY)
        thin = (y["volume"] <= 2).mean()
        flat = (y["range"] == 0).mean()
        spread = y["spread"].median()
        rng = y["range"].median()
        verdict = (
            "good" if coverage >= 0.95 and thin <= 0.05
            else "usable" if coverage >= 0.85 and thin <= 0.20
            else "thin"
        )
        rows.append(
            {
                "year": year,
                "candles": len(y),
                "trading_days": days,
                "coverage": round(coverage, 3),
                "thin_candles": round(thin, 3),
                "flat_candles": round(flat, 3),
                "gaps_in_day": int(y["gap"].sum()),
                "median_spread": round(spread, 2),
                "p90_spread": round(y["spread"].quantile(0.9), 2),
                "median_range": round(rng, 2),
                "cost_ratio": round(spread / rng, 3) if rng else None,
                "median_price": round(y["close"].median(), 1),
                "verdict": verdict,
            }
        )
    return pd.DataFrame(rows).set_index("year")
