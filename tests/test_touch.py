"""Fresh/flipped level touches: v4.1 flip entries, either-side entries, inducement and stop management."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gse_research import data, strategy as st
from gse_research.structure import ST_FLIP, ST_FRESH, ST_TAPPED, Level

from test_strategy import FLAT, _frame, _sig

needs_data = pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")


def _minors(rows, lows=True):
    """Minors from (confirm, origin, price, taken, swept, extreme) rows."""
    m = st.Minors(*[list(c) for c in zip(*rows)])
    order = sorted((tk, i) for i, (tk, sw) in enumerate(zip(m.taken, m.swept)) if sw)
    m.sweep_bar, m.sweep_idx = [tk for tk, _ in order], [i for _, i in order]
    return m


def test_inducement_present_cleared_swept_and_none():
    # A long at support 100; the level formed at candle 10.
    m = _minors([(15, 13, 102.0, 20, True, 101.0)])
    assert st.inducement(m, 1, 100.0, 10, 18, 18) == (1, -1)    # untaken: present
    assert st.inducement(m, 1, 100.0, 10, 20, 20) == (2, 0)     # taken and closed back: cleared, swept now
    assert st.inducement(m, 1, 100.0, 10, 20, 19) == (1, -1)    # the touch candle itself took it: not cleared
    assert st.inducement(m, 1, 100.0, 10, 30, 30) == (2, 10)
    assert st.inducement(m, 1, 100.0, 10, 41, 41) == (2, -1)    # the sweep is older than IND_MAX_AGE
    assert st.inducement(m, 1, 100.0, 14, 20, 20) == (0, -1)    # formed before the level: not eligible
    assert st.inducement(m, 1, 102.5, 10, 20, 20) == (0, -1)    # not between the level and price
    deep = _minors([(15, 13, 102.0, 20, True, 99.5)])          # the sweep candle reached the level itself
    assert st.inducement(deep, 1, 100.0, 10, 22, 22) == (2, -1)
    short = _minors([(15, 13, 98.0, 20, True, 99.0)], lows=False)  # a short at resistance 100: highs below it
    assert st.inducement(short, -1, 100.0, 10, 22, 22) == (2, 2)


def test_minor_swings_find_the_candle_that_takes_each_swing():
    lows = [5, 4, 3, 4, 5, 6, 5, 4.5, 2.5, 6]
    df = pd.DataFrame({"low": lows, "high": [x + 1 for x in lows], "close": [x + 0.5 for x in lows]})
    df.loc[8, "close"] = 3.2   # the candle that takes the swing low at 3 closes back above it
    m = st.minor_swings(df, 2, True)
    assert m.confirm == [4] and m.origin == [2] and m.price == [3.0]
    assert m.taken == [8] and m.swept == [True] and m.extreme == [2.5]
    assert m.sweep_bar == [8]


def test_a_flipped_level_is_entered_once_after_its_confirming_retest():
    confirmed = Level(1, 100.0, 1, ST_FLIP, 1)
    retested = Level(2, 100.5, 1, ST_FLIP, 2)
    fresh = Level(3, 99.0, 1, ST_FRESH, 0)
    flipped = st.ENTRY_STATES["flipped"]
    assert st.touch_pick([confirmed, retested, fresh], 1, 102.0, flipped) is confirmed
    assert st.touch_pick([retested, fresh], 1, 102.0, flipped) is None
    assert st.touch_pick([confirmed, fresh], 1, 102.0) is fresh
    assert not st.first_touch(Level(4, 99.0, 1, ST_TAPPED, 1))


def test_breakeven_moves_the_stop_at_a_close_and_works_from_the_next_candle():
    # Long limit 100, stop 99, no target. Candle 2 closes at 101.5 (bid 101.4: 1.4 R); candle 3 falls to 99.5.
    rows = [FLAT, (101.0, 101.2, 99.8, 100.4), (100.4, 101.8, 100.3, 101.5), (101.5, 101.6, 99.5, 99.7)] + [FLAT] * 3
    df = _frame(rows)
    sig = _sig(len(df), until=2, tp2=np.nan).assign(atr=1.0, swing_low=np.nan, swing_high=np.nan)
    broker = st.Broker(slippage=0.0)
    trades, _ = st.simulate(df, sig, "2026-03-01", "2026-04-01", broker, st.Manage(be_r=1.0))
    t = trades.iloc[0]
    assert t["reason"] == "managed_stop" and t["exit"] == 100.0 and t["R"] == pytest.approx(0.0)
    plain, counts = st.simulate(df, sig, "2026-03-01", "2026-04-01", broker)
    assert plain.empty and counts["open_at_data_end"] == 1      # unmanaged: the stop at 99 is never reached


def test_atr_and_swing_trails_only_move_toward_profit():
    rows = [FLAT, (101.0, 101.2, 99.8, 100.4), (100.4, 102.8, 100.3, 102.5), (102.5, 102.6, 101.8, 102.0),
            (102.0, 102.1, 100.0, 100.2)] + [FLAT] * 2
    df = _frame(rows)
    sig = _sig(len(df), until=2, tp2=np.nan).assign(atr=0.5, swing_low=101.0, swing_high=np.nan)
    broker = st.Broker(slippage=0.0)
    atr, _ = st.simulate(df, sig, "2026-03-01", "2026-04-01", broker, st.Manage(trail="atr", trail_atr=2.0))
    # Best close 102.4 (bid) at candle 2: the stop trails to 101.4 and stays there when candle 3 closes lower.
    assert atr.iloc[0]["reason"] == "managed_stop" and atr.iloc[0]["exit"] == pytest.approx(101.4)
    swing, _ = st.simulate(df, sig, "2026-03-01", "2026-04-01", broker, st.Manage(trail="swing"))
    # Beyond the latest minor swing low 101.0, less max(tick, 0.2 x 0.5) = 100.9.
    assert swing.iloc[0]["reason"] == "managed_stop" and swing.iloc[0]["exit"] == pytest.approx(100.9)


@needs_data
@pytest.mark.parametrize("tf", ["15m", "4H"])
def test_flipped_either_side_signals_with_inducement_do_not_look_ahead(tf):
    m15 = data.load("M15", start="2023-01-01" if tf == "4H" else "2023-10-01", end="2024-03-01")
    chart = m15 if tf == "15m" else data.aggregate(m15, tf)
    p = st.StrategyParams(level_type="flipped", h4_mode="off", flip_rules="4.1", htf_check=False, stop_atr=1.5,
                          target_r=1.0, swing_len=3)
    full = st.signals(chart, p, ind_lens=(2, 3))
    cut = chart["time"].iloc[int(len(chart) * 0.8)]
    part_chart = chart[chart["time"] < cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(st.signals(part_chart, p, ind_lens=(2, 3)), full.iloc[: len(part_chart)].reset_index(drop=True))
    on = full[full["signal"]]
    assert len(on) > 0 and set(on["dir"]) == {1, -1}            # either side without an H4 direction
    assert set(on["ind3_state"]) <= {0, 1, 2} and (on["ind3_state"] > 0).any()



def test_inducement_settings_select_the_recorded_states():
    from gse_research import touch_search as ts
    sig = pd.DataFrame({"ind3_state": [0, 1, 2, 2], "ind3_sweep_age": [-1, -1, 4, 12]})
    assert ts.inducement_mask(sig, "off").all()
    assert ts.inducement_mask(sig, "none_3").tolist() == [True, False, False, False]
    assert ts.inducement_mask(sig, "present_3").tolist() == [False, True, False, False]
    assert ts.inducement_mask(sig, "cleared_3").tolist() == [False, False, True, True]
    assert ts.inducement_mask(sig, "swept_3_5").tolist() == [False, False, True, False]
    assert ts.inducement_mask(sig, "swept_3_20").tolist() == [False, False, True, True]
    assert len(ts.INDUCEMENT) == 19 and len(set(ts.INDUCEMENT)) == 19


@pytest.fixture
def s3_window(monkeypatch):
    """Six months of candles in place of 2015-2023, so a group runs quickly."""
    from gse_research import touch_search as ts
    monkeypatch.setattr(ts, "PERIODS", {"train": ("2023-11-01", "2024-01-01"), "val": ("2024-01-01", "2024-03-01")})
    monkeypatch.setattr(ts.ms, "YEARS", {"train": (2023,), "val": (2024,)})
    monkeypatch.setattr(ts, "_M15", data.load("M15", start="2023-09-01", end="2024-03-02"))
    for f in (ts._chart, ts._h4):
        f.cache_clear()
    yield ts
    for f in (ts._chart, ts._h4):
        f.cache_clear()


@needs_data
def test_a_small_s3_group_runs_every_exit_and_filter(s3_window, monkeypatch):
    ts = s3_window
    rows = pd.DataFrame(ts.evaluate_design({"chart_tf": "1H", "swing_len": 5, "level_type": "fresh",
                                            "entry_mode": "limit", "h4_mode": "off"}))
    assert len(rows) == len(ts.STOPS) * len(ts.EXITS) * len(ts.INDUCEMENT) * 2
    plain = rows[(rows["inducement"] == "off") & ~rows["session"]]
    assert (plain["train_trades"] > 0).all()
    # A filter only removes trades from the same exit.
    merged = rows.merge(plain, on=["stop_atr", "exit"], suffixes=("", "_plain"))
    assert (merged["train_trades"] <= merged["train_trades_plain"]).all()
    effect = ts.inducement_effect(rows, min_trades=1)
    assert set(effect.index) == set(ts.INDUCEMENT) - {"off"}


def test_shards_cover_every_design_once():
    from gse_research import touch_search as ts
    all_designs = ts.designs()
    parts = [d for i in range(18) for d in all_designs[i::18]]
    assert len(all_designs) == 108 and len(parts) == 108
    assert sorted(map(str, parts)) == sorted(map(str, all_designs))
    assert {d["chart_tf"] for d in all_designs[0::18]} == {"15m", "1H", "4H"}   # each shard mixes charts
