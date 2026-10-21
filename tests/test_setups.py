"""Study S4: the entry triggers after a touch, the stop and target plan, and no look-ahead."""

import numpy as np
import pandas as pd
import pytest

from gse_research import data, setups as s4


def _arrays(rows):
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def _run(rows, side=1, price=100.0):
    O, H, L, C = _arrays(rows)
    setup = {"price": price, "side": side, "touch": 0, "fired": set()}
    out = []
    for t in range(len(rows)):
        fired, done = s4.step(setup, t, O, H, L, C)
        out.append((t, fired, done))
        if done:
            break
    return out, setup


def test_a_rejection_candle_on_the_touch_also_counts_as_a_sweep_when_it_pierces():
    out, setup = _run([(100.8, 101.0, 99.7, 100.9)])                   # pierces 100, long lower wick, bullish
    assert set(out[0][1]) == {"rejection", "sweep_reclaim"} and setup["ext"] == 99.7


def test_a_touch_that_holds_without_piercing_is_only_a_rejection():
    out, _ = _run([(100.8, 101.0, 100.0, 100.9)])                      # low exactly at the level
    assert out[0][1] == ["rejection"]


def test_bos_needs_a_close_above_every_high_since_the_touch_after_two_candles():
    rows = [(100.5, 100.9, 100.0, 100.4), (100.4, 100.6, 100.2, 100.5), (100.5, 100.8, 100.3, 100.85),
            (100.85, 101.2, 100.8, 101.1)]
    out, _ = _run(rows)
    fired = {t: f for t, f, _ in out}
    assert fired[2] == [] and fired[3] == ["bos"]                      # 100.85 < 100.9; then 101.1 > 100.9


def test_a_close_through_the_level_ends_the_setup():
    out, _ = _run([(100.5, 100.6, 100.0, 100.3), (100.3, 100.4, 99.5, 99.8), (99.8, 101.5, 99.7, 101.4)])
    assert out[-1][0] == 1 and out[-1][2] is True and out[-1][1] == []


def test_shorts_mirror():
    out, _ = _run([(99.2, 100.3, 99.0, 99.1)], side=-1)               # pierces 100 from below, bearish, long upper wick
    assert set(out[0][1]) == {"rejection", "sweep_reclaim"}


def test_the_floor_keeps_the_stop_at_least_one_atr_away_and_2r_doubles_the_risk():
    row = pd.Series({"side": 1, "entry": 100.0, "inval": 99.9, "atr": 1.0, "raw": None})
    row = row.to_frame().T.astype(object).itertuples(index=False).__next__()
    stop, tp = s4.plan(row, "structural", "2R")
    assert stop == pytest.approx(99.7) and tp == pytest.approx(100.6)  # 99.9 - 0.2 ATR; 2 x 0.3
    stop, tp = s4.plan(row, "structural_floor", "2R")
    assert stop == pytest.approx(99.0) and tp == pytest.approx(102.0)
    assert np.isnan(s4.plan(row, "structural", "tp2")[0])            # no snapshot data: no website target


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_candidates_do_not_look_ahead():
    from gse_research import strategy as st
    hist = data.load("M15", "2021-01-01", "2021-08-01")
    m15 = hist[hist["time"] >= pd.Timestamp("2021-03-01", tz="UTC")].reset_index(drop=True)
    p = st.StrategyParams(swing_len=s4.SWING, flip_rules="4.1")

    def cands(frame, history):
        c, _ = s4.candidates(frame, s4.context(frame, history), st.h1_inputs(frame, p), st.h4_inputs(frame, p))
        return c.drop(columns="raw")

    full = cands(m15, hist)
    cut = pd.Timestamp("2021-06-15", tz="UTC")
    part = cands(m15[m15["time"] < cut].reset_index(drop=True), hist[hist["time"] < cut].reset_index(drop=True))
    n = len(m15[m15["time"] < cut]) - 1
    pd.testing.assert_frame_equal(part[part["bar"] < n].reset_index(drop=True), full[full["bar"] < n].reset_index(drop=True))
    assert set(full["trigger"]) == {"touch", "rejection", "sweep_reclaim", "bos"}
