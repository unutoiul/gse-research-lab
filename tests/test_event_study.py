"""Study E1: first-passage outcomes from the level price and random control levels."""

import numpy as np
import pandas as pd
import pytest

from gse_research import data, event_study as es


def _chart(rows):
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "time", pd.date_range("2016-03-01", periods=len(df), freq="15min", tz="UTC"))
    return df


def test_outcomes_count_the_touch_candle_against_but_never_for_the_level():
    flat = [(101.0, 101.2, 100.8, 101.0)]
    up = _chart([*flat, (100.5, 100.6, 99.9, 100.4), (100.4, 101.2, 100.3, 101.1)] + flat * 40)
    through = _chart([*flat, (100.5, 100.6, 98.9, 99.0)] + flat * 40)       # touch candle runs 1 ATR through
    atr = np.ones(42)
    ev = pd.DataFrame({"bar": [1], "price": [100.0], "side": [1]})
    win = es.outcomes(up, ev, atr).iloc[0]
    assert win["win"] == 1.0 and win["ret_4"] == 1.0
    assert es.outcomes(through, ev, atr).iloc[0]["win"] == 0.0
    short = pd.DataFrame({"bar": [1], "price": [102.0], "side": [-1]})          # resistance 102: price never gets 1 ATR either way
    near = [(101.7, 101.9, 101.5, 101.7)]
    calm = _chart([*near, (101.5, 102.0, 101.4, 101.5)] + near * 40)
    assert np.isnan(es.outcomes(calm, short, atr).iloc[0]["win"])


def test_random_levels_keep_the_side_and_distance_and_are_first_touched_from_that_side():
    rng = np.random.default_rng(1)
    n = 3000
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    df = _chart(np.c_[close, close + 0.4, close - 0.4, close])
    atr = np.full(n, 0.8)
    ev = pd.DataFrame({"bar": [500], "price": [close[480] - 1.6], "side": [1], "type": ["fresh"], "period": ["train"],
                       "born_bar": [480]})
    ctrl = es.control_events(df, ev, atr, np.random.default_rng(2))
    assert len(ctrl) == es.CONTROLS and (ctrl["side"] == 1).all()
    for c in ctrl.itertuples():
        assert np.isclose(close[c.born_bar] - c.price, 1.6)                      # 2 ATR below price when it formed
        assert (df["low"].to_numpy()[c.born_bar + 1:c.bar] > c.price).all()      # untouched until its first touch
        assert df["low"].iat[c.bar] <= c.price


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_forward_touches_match_the_full_history_once_the_warmup_has_settled():
    from gse_research import forward
    m15 = data.load("M15", start="2022-01-01", end="2022-10-01")
    short = forward.collect(m15, "2022-07-01", "2022-10-01")
    full_m15 = data.load("M15", start="2021-01-01", end="2022-10-01")
    full = forward.collect(full_m15, "2022-07-01", "2022-10-01")
    key = ["chart_tf", "swing_len", "type", "time", "price", "side"]
    a = short[(short["group"] == "real") & (short["chart_tf"] == "15m")][key].reset_index(drop=True)
    b = full[(full["group"] == "real") & (full["chart_tf"] == "15m")][key].reset_index(drop=True)
    assert len(a) > 50
    pd.testing.assert_frame_equal(a, b)              # six months of warmup: the same 15m touches


def test_the_forward_verdict_waits_for_enough_touches():
    from gse_research import forward
    row = pd.Series({"resolved": 120, "win_diff_low": 0.05, "win_real": 0.7, "cost_atr": 0.3})
    assert forward.decide(row)[0] == "running" and forward.decide(None)[0] == "running"
    done = row.copy(); done["resolved"] = 450
    assert forward.decide(done)[0] == "edge"
    assert forward.decide(done.copy().replace({0.7: 0.6}))[0] == "edge, not tradeable"
    no = done.copy(); no["win_diff_low"] = -0.01
    assert forward.decide(no)[0] == "no edge"
