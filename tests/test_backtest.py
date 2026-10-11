"""RXM-1 execution, metrics and candidate extraction on hand-computed cases."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gse_research import backtest, metrics, signals
from gse_research.backtest import Execution, simulate

SPREAD = 0.2


def candles(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """Mid OHLC rows; bid/ask are mid -/+ half the spread."""
    t = pd.date_range("2026-07-14 12:00", periods=len(rows), freq="15min", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "time", t)
    for side, shift in (("bid", -SPREAD / 2), ("ask", SPREAD / 2)):
        for k in ("open", "high", "low", "close"):
            df[f"{side}_{k}"] = df[k] + shift
    return df


def candidate(side=1, level=100.0, wick=99.5, obstacle=105.0, atr=1.0, bar=0) -> pd.DataFrame:
    return pd.DataFrame([{"bar": bar, "side": side, "close": 100.5, "atr": atr, "level": level, "level_wick": wick,
                          "obstacle": obstacle, "bos_had_sweep": False}])


FLAT = (101.0, 101.3, 100.8, 101.0)


def test_long_target():
    df = candles([(100.5, 100.6, 100.4, 100.5), (101.0, 101.2, 100.9, 101.1), (101.1, 105.1, 101.0, 104.0)] + [FLAT] * 20)
    t = simulate(df, candidate()).iloc[0]
    assert t["stop"] == pytest.approx(99.30) and t["target"] == pytest.approx(104.90)
    assert t["entry"] == pytest.approx(101.1)  # ask at the next candle's open
    assert t["reason"] == "target" and t["exit"] == pytest.approx(104.90)
    assert t["R"] == pytest.approx((104.9 - 101.1) / (101.1 - 99.3))
    assert t["entry_time"] == df["time"].iat[1]


def test_long_stop_and_same_candle_rule():
    stop_bar = (101.0, 101.2, 99.0, 99.5)
    t = simulate(candles([FLAT, FLAT, stop_bar] + [FLAT] * 20), candidate()).iloc[0]
    assert t["reason"] == "stop" and t["R"] == pytest.approx(-1.0)
    both = (101.0, 106.0, 99.0, 101.0)
    t = simulate(candles([FLAT, FLAT, both] + [FLAT] * 20), candidate()).iloc[0]
    assert t["reason"] == "stop_and_target" and t["R"] == pytest.approx(-1.0)


def test_gap_through_the_stop_fills_at_the_open():
    gap = (98.0, 98.5, 97.5, 98.2)
    t = simulate(candles([FLAT, FLAT, gap] + [FLAT] * 20), candidate()).iloc[0]
    assert t["reason"] == "stop_gap" and t["exit"] == pytest.approx(98.0 - SPREAD / 2)
    assert t["R"] < -1


def test_time_exit_after_16_candles():
    t = simulate(candles([FLAT] * 30), candidate()).iloc[0]
    assert t["reason"] == "time" and t["bars_held"] == 16
    assert t["exit_time"] == candles([FLAT] * 30)["time"].iat[16]
    assert t["exit"] == pytest.approx(101.0 - SPREAD / 2)


def test_short_target_uses_the_ask():
    flat = (99.0, 99.2, 98.7, 99.0)
    df = candles([flat, flat, (99.0, 99.1, 94.0, 95.0)] + [flat] * 20)
    t = simulate(df, candidate(side=-1, level=100.0, wick=100.5, obstacle=95.0)).iloc[0]
    assert t["stop"] == pytest.approx(100.70) and t["target"] == pytest.approx(95.10)
    assert t["entry"] == pytest.approx(99.0 - SPREAD / 2)
    assert t["reason"] == "target" and t["R"] == pytest.approx((98.9 - 95.1) / (100.7 - 98.9))


def test_slippage_is_adverse_on_entry_and_stop():
    stop_bar = (101.0, 101.2, 99.0, 99.5)
    t = simulate(candles([FLAT, FLAT, stop_bar] + [FLAT] * 20), candidate(), Execution(slippage=0.1)).iloc[0]
    assert t["entry"] == pytest.approx(101.2) and t["exit"] == pytest.approx(99.2)


def test_signal_candle_range_never_affects_the_fill():
    base = [FLAT, FLAT, (101.1, 105.1, 101.0, 104.0)] + [FLAT] * 20
    wild = [(100.0, 150.0, 50.0, 100.5)] + base[1:]
    a, b = simulate(candles(base), candidate()).iloc[0], simulate(candles(wild), candidate()).iloc[0]
    assert a["R"] == b["R"] and a["reason"] == b["reason"]


def test_trade_still_open_at_data_end_is_excluded():
    t = simulate(candles([FLAT] * 5), candidate()).iloc[0]
    assert t["reason"] == "open_at_data_end" and np.isnan(t.get("R", np.nan))
    assert metrics.summarize(simulate(candles([FLAT] * 5), candidate()))["trades"] == 0


def test_one_open_trade_per_side():
    trades = pd.DataFrame({"side": [1, 1, -1], "entry_time": pd.to_datetime(["2026-01-01 10:00", "2026-01-01 10:30", "2026-01-01 10:30"], utc=True),
                           "exit_time": pd.to_datetime(["2026-01-01 11:00", "2026-01-01 12:00", "2026-01-01 11:00"], utc=True)})
    kept = backtest.one_open_per_side(trades)
    assert kept.index.tolist() == [0, 2]


def test_metrics():
    r = pd.Series([1.0, -1.0, -1.0, 2.0])
    assert metrics.max_drawdown(r) == pytest.approx(2.0)
    t = pd.DataFrame({"R": r, "entry_time": pd.date_range("2026-01-05", periods=4, freq="D", tz="UTC"),
                      "mfe_R": 1.0, "mae_R": 0.5, "planned_rr": 2.0, "bars_held": 4, "reason": "time"})
    s = metrics.summarize(t, weeks=2)
    assert s["trades"] == 4 and s["win_rate"] == 0.5 and s["expectancy_R"] == pytest.approx(0.25)
    assert s["profit_factor"] == pytest.approx(1.5) and s["trades_per_week"] == 2
    boot = metrics.bootstrap_mean_diff(t, t, n=200)
    assert boot["diff"] == 0 and boot["low"] <= 0 <= boot["high"]


def test_candidates_are_off_to_on_transitions_and_funnel_counts_first_failure():
    out = pd.DataFrame({
        "long_zone": [False, True, True, False, True], "short_zone": [False] * 5,
        "in_asian": [False] * 5, "in_london": [True] * 5, "in_ny": [False] * 5,
        "atr": 1.0, "sup": 100.0, "sup_id": 1, "sup_state": 0, "sup_touches": 0, "sup_wick": 99.0,
        "res": np.nan, "res_id": -1, "res_state": -1, "res_touches": 0, "res_wick": np.nan,
        "obstacle_bull": 103.0, "obstacle_bear": np.nan, "bull_bos_had_sweep": False, "bear_bos_had_sweep": False,
        "bull_bos_sweep_src": "", "bear_bos_sweep_src": "", "trend_score": 1.0, "score_bull": 70.0, "score_bear": 20.0,
        "gz_fail_bull": [1 | 4, 0, 0, 2 | 16, 0], "gz_fail_bear": [1] * 5,
    })
    m15 = pd.DataFrame({"time": pd.date_range("2026-07-14", periods=5, freq="15min", tz="UTC"), "close": 100.5})
    htf = pd.DataFrame({"h4": [1.0] * 5, "h1": [0.0] * 5})
    c = signals.golden_zone_candidates(m15, out, htf)
    assert c["bar"].tolist() == [1, 4] and (c["stratum"] == "partial").all() and (c["session"] == "LDN").all()
    f = signals.golden_zone_funnel(out).set_index(["side", "stage"])
    assert f.loc[("long", "direction"), "rejected"] == 1 and f.loc[("long", "location"), "rejected"] == 1
    assert f.loc[("long", "qualified"), "remaining"] == 3
    assert f.loc[("short", "direction"), "rejected"] == 5


def test_with_spread_scales_bid_and_ask_toward_mid():
    from gse_research.timeframes import with_spread
    df = candles([FLAT, FLAT])
    half, mid = with_spread(df, 0.5), with_spread(df, 0.0)
    assert half["ask_open"].iat[0] == pytest.approx(101.0 + SPREAD / 4)
    assert half["bid_low"].iat[0] == pytest.approx(100.8 - SPREAD / 4)
    assert (mid["ask_close"] == mid["close"]).all() and (mid["bid_high"] == mid["high"]).all()
