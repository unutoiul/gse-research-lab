"""Study G1: the trade simulator's fills and exits, and signals that never look ahead."""

import json

import numpy as np
import pandas as pd
import pytest

from gse_research import data, edge_search as g


def _sim(rows, sig, stop_k=1.0, target_r=2.0, trail_k=0.0, trail_start=0.0, max_bars=0, ex=None, family=False,
         spread=0.0, slip=0.0, risk=None):
    a = np.array(rows, float)
    o, h, l, c = a.T
    n = len(a)
    ex = np.zeros(n, bool) if ex is None else np.array(ex, bool)
    risk = np.full(n, np.nan) if risk is None else np.array(risk, float)
    half = spread / 2
    return g.simulate(np.array(sig, np.int64), ex, ex, risk, o - half, h - half, l - half, c - half,
                      o + half, h + half, l + half, c + half, np.ones(n), 0, n, stop_k, target_r, trail_k, trail_start,
                      max_bars, family, slip)


FLAT = (100.0, 100.4, 99.6, 100.0)


def test_market_entry_at_the_next_open_then_the_target():
    sb, xb, side, r = _sim([FLAT, (100.0, 100.5, 99.5, 100.2), (100.2, 102.3, 100.1, 102.0), FLAT], [1, 0, 0, 0])
    assert list(sb) == [0] and list(xb) == [2] and list(side) == [1] and r[0] == pytest.approx(2.0)


def test_a_candle_reaching_stop_and_target_is_a_stop_and_costs_are_paid():
    sb, xb, side, r = _sim([FLAT, (100.0, 102.5, 98.5, 100.0), FLAT], [1, 0, 0], spread=0.2, slip=0.1)
    # Fill at the ask open 100.1 + 0.1; the stop is 1 ATR below the fill; stop fills 0.1 worse.
    assert r[0] == pytest.approx(-1.1)


def test_a_gap_through_the_stop_fills_at_the_open():
    _, _, _, r = _sim([FLAT, (100.0, 100.3, 99.8, 100.0), (98.0, 98.5, 97.5, 98.0), FLAT], [1, 0, 0, 0])
    assert r[0] == pytest.approx(-2.0)


def test_time_and_family_exits_work_at_the_next_open():
    rows = [FLAT, (100.0, 100.5, 99.5, 100.2), (100.2, 100.6, 99.9, 100.5), (100.7, 100.9, 100.4, 100.8), FLAT]
    _, xb, _, r = _sim(rows, [1, 0, 0, 0, 0], stop_k=0.0, target_r=0.0, max_bars=2)
    assert list(xb) == [3] and r[0] == pytest.approx(0.7)          # two candles held, out at the third open
    _, xb, _, _ = _sim(rows, [1, 0, 0, 0, 0], stop_k=3.0, target_r=0.0, ex=[0, 1, 0, 0, 0], family=True)
    assert list(xb) == [2]


def test_the_atr_trail_follows_the_best_close_and_never_moves_back():
    rows = [FLAT, (100.0, 101.0, 99.9, 101.0), (101.0, 103.0, 100.9, 103.0), (103.0, 103.1, 102.5, 102.6),
            (102.6, 102.7, 101.8, 101.9), FLAT]
    _, xb, _, r = _sim(rows, [1, 0, 0, 0, 0, 0], stop_k=2.0, target_r=0.0, trail_k=1.0)
    assert list(xb) == [4] and r[0] == pytest.approx(1.0)           # trailed to 103 - 1 = 102; candle 4 reaches it


def test_signals_only_start_trades_inside_the_period():
    sig = [1, 0, 1, 0, 1, 0]
    rows = [FLAT] * 6
    a = np.array(rows, float)
    o, h, l, c = a.T
    sb, *_ = g.simulate(np.array(sig, np.int64), np.zeros(6, bool), np.zeros(6, bool), np.full(6, np.nan),
                        o, h, l, c, o, h, l, c, np.ones(6), 2, 4, 1.0, 1.0, 0.0, 0.0, 1, False, 0.0)
    assert list(sb) == [2]


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_family_signals_do_not_look_ahead():
    full_m15 = data.load("M15", "2020-01-01", "2020-07-01")
    cut = pd.Timestamp("2020-05-15", tz="UTC")
    full, part = g.Charts(full_m15), g.Charts(full_m15[full_m15["time"] < cut].reset_index(drop=True))
    for fam, (tfs, params, _) in g.FAMILIES.items():
        for tf in tfs[:2]:
            p = params[-1]
            fa, pa = full.signal(fam, tf, p), part.signal(fam, tf, p)
            n = len(part.chart(tf)["c"]) - 1     # the last candle of the cut data may be a candle still forming
            for x, y in zip(fa, pa):
                if x is None:
                    continue
                np.testing.assert_array_equal(np.asarray(x)[:n], np.asarray(y)[:n], err_msg=f"{fam} {tf} {json.dumps(p)}")


def test_finalists_need_both_periods_positive_and_holdout_verdicts():
    t = pd.DataFrame({"rule": list("abcd"), "train_trades": [60, 60, 40, 60], "val_trades": [80, 80, 80, 80],
                      "train_expectancy_R": [0.1, 0.1, 0.3, -0.1], "val_expectancy_R": [0.1, -0.1, 0.3, 0.2],
                      "train_profit_factor": [1.2, 1.2, 1.5, 0.9], "val_profit_factor": [1.2, 0.9, 1.5, 1.3],
                      "train_sqn": [1.0, 1.0, 2.0, -1], "val_sqn": [1.0, -1.0, 2.0, 1.0]})
    assert list(g.finalists(t)["rule"]) == ["a"]
    good = {"holdout_trades": 80, "holdout_expectancy_R": 0.1, "holdout_profit_factor": 1.3, "holdout_ci_low": 0.01,
            "holdout_years_positive": 3}
    assert g.holdout_verdict(good) == "pass"
    assert g.holdout_verdict({**good, "holdout_ci_low": -0.02}) == "weak"
    assert g.holdout_verdict({**good, "holdout_expectancy_R": -0.01}) == "fail"
    assert g.holdout_verdict({**good, "holdout_trades": 20}) == "inconclusive"
