from __future__ import annotations

import pandas as pd
import pytest

NY = "America/New_York"


def session_candles(*trading_days: str) -> pd.DataFrame:
    """Synthetic M15 candles for whole gold trading days (18:00 to 17:00 New York).

    A trading day is named by the date of its 17:00 close, as TradingView names
    daily candles. Prices rise steadily so every candle is distinct.
    """
    frames = []
    for day in trading_days:
        open_ny = pd.Timestamp(day, tz=NY) - pd.Timedelta(hours=6)  # 18:00 the evening before
        frames.append(pd.date_range(open_ny, periods=92, freq="15min").tz_convert("UTC"))
    t = pd.DatetimeIndex(frames[0]).append(frames[1:]) if len(frames) > 1 else frames[0]
    n = len(t)
    mid_open = pd.Series([2000.0 + 0.1 * i for i in range(n)])
    df = pd.DataFrame({
        "time": pd.Series(t).astype("datetime64[ns, UTC]"),
        "open": mid_open,
        "high": mid_open + 0.3,
        "low": mid_open - 0.2,
        "close": mid_open + 0.1,
        "volume": 10,
    })
    for side, shift in (("bid", -0.15), ("ask", 0.15)):
        for k in ("open", "high", "low", "close"):
            df[f"{side}_{k}"] = df[k] + shift
    df["close_time"] = df["time"] + pd.Timedelta(minutes=15)
    return df


@pytest.fixture
def candles():
    return session_candles
