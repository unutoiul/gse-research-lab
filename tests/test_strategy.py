"""GSE Strategy v4.0 port: decision functions against the Pine source, broker cases, no look-ahead."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gse_research import data, strategy as st
from gse_research.structure import Level

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = Path(os.environ.get("GSE_WEBSITE", ROOT.parent / "gse-website"))
needs_pine = [pytest.mark.skipif(not (WEBSITE / "tradingview" / "gse_4.0" / "src" / "strategy-targets.pine").exists(), reason="gse-website not found"),
              pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")]


def _cases(seed: int = 3, n: int = 3000) -> dict:
    rng = np.random.default_rng(seed)
    targets = []
    for _ in range(n):
        d = int(rng.choice([1, -1]))
        entry = round(float(rng.uniform(1500, 4000)), 3)
        atr = float(rng.choice([0.4, 1.0, 2.5, 6.0, rng.uniform(0.3, 8.0)]))
        wick = round(entry - d * float(rng.uniform(0, 1.5)) * atr, 3)
        adds = []
        for _ in range(int(rng.integers(0, 14))):
            if adds and rng.random() < 0.15:  # exact-price ties and near clusters
                price = adds[int(rng.integers(len(adds)))][0] + (0 if rng.random() < 0.5 else d * float(rng.uniform(0, 0.06)) * atr)
            else:
                price = entry + d * float(rng.uniform(-2, 14)) * atr
            adds.append([round(price, 2), int(rng.choice([35, 45, 50, 55, 65, 70, 80, 85])), bool(rng.random() < 0.4),
                         int(rng.choice([0, 1, 2, 3, 4, 10, 11, 12, 20, 21, 22]))])
        targets.append({"dir": d, "entry": entry, "wick": wick, "atr": atr, "tick": 0.01, "adds": adds})
    touch = []
    for _ in range(n):
        close = float(rng.uniform(1990, 2010))
        levels = [[i, round(float(rng.uniform(1985, 2015)), 2), int(rng.choice([1, -1])), int(rng.choice([0, 0, 1, 2, 3])),
                   int(rng.choice([0, 0, 1, 2])), bool(rng.random() < 0.2)] for i in range(int(rng.integers(0, 12)))]
        if levels and rng.random() < 0.2:  # equidistant levels: the earlier one must win
            levels.append([99, round(2 * close - levels[0][1], 2), levels[0][2], 0, 0, False])
        touch.append({"levels": levels, "h4_dir": int(rng.choice([1, -1, 0])), "close": round(close, 2)})
    direction = [[int(p), bool(b), bool(e)] for p in (-1, 0, 1) for b in (False, True) for e in (False, True)]
    return {"targets": targets, "touch": touch, "direction": direction}


def _same(a, b) -> bool:
    if a is None or (isinstance(a, float) and math.isnan(a)):
        return b is None
    return b is not None and abs(a - b) <= 1e-9


@needs_pine[0]
@needs_pine[1]
def test_decision_functions_match_the_pine_source(tmp_path):
    """3,000 random cases each for the target engine and the level pick."""
    cases = _cases()
    src, out = tmp_path / "cases.json", tmp_path / "out.json"
    src.write_text(json.dumps(cases))
    subprocess.run(["node", str(ROOT / "tests" / "oracle" / "target_oracle.mjs"), str(WEBSITE), str(src), str(out)],
                   check=True, capture_output=True, text=True)
    pine = json.loads(out.read_text())
    reasons = set()
    for i, c in enumerate(cases["targets"]):
        raw: list = []
        for price, strength, major, key in c["adds"]:
            st.target_add(raw, c["dir"], c["entry"], price, strength, major, key)
        assert [list(r) for r in raw] == pine["targets"][i]["raw"], f"case {i}: evidence order"
        plan = st.structure_targets(raw, c["dir"], c["entry"], c["wick"], c["atr"], c["tick"])
        for k in ("stop", "tp1", "tp2", "tp3"):
            assert _same(plan[k], pine["targets"][i][k]), f"case {i}: {k} {plan[k]} vs Pine {pine['targets'][i][k]}"
        assert plan["reason"] == pine["targets"][i]["reason"], f"case {i}: reason"
        reasons.add(plan["reason"])
    assert {"", "no_opposing_structure", "insufficient_room", "target_too_distant"} <= reasons  # every branch exercised
    for i, c in enumerate(cases["touch"]):
        levels = [Level(id=a, price=p, role=r, state=s, touches=n, in_contact=ic) for a, p, r, s, n, ic in c["levels"]]
        best = st.touch_pick(levels, c["h4_dir"], c["close"])
        assert (None if best is None else best.id) == pine["touch"][i], f"touch case {i}"
    for (prev, bull, bear), want in zip(cases["direction"], pine["direction"]):
        assert st.fresh_h4_direction(prev, bull, bear) == want


def test_fresh_h4_follows_the_last_break_and_each_swing_breaks_once():
    # Swing high 10 at candle 3 (lookback 2), confirmed at 5; close 11 at 6 breaks it once.
    h = [5, 6, 8, 10, 8, 7, 11, 11.5, 9, 6, 5, 4, 3]
    l = [4, 5, 7, 9, 7, 6, 8, 10, 8, 5, 4, 2, 1]
    c = [4.5, 5.5, 7.5, 9.5, 7.5, 6.5, 11, 11, 8.5, 5.5, 4.5, 2.5, 1.5]
    out = st.fresh_h4(pd.DataFrame({"high": h, "low": l, "close": c}), 2)
    assert list(out[:6]) == [0] * 6 and out[6] == 1
    assert out[7] == 1  # already used: no new break, direction holds


def _frame(rows):
    """Mid OHLC with a 0.2 spread; one candle per 15 minutes."""
    t = pd.date_range("2026-03-02 00:00", periods=len(rows), freq="15min", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "time", t)
    df["close_time"] = df["time"] + pd.Timedelta(minutes=15)
    for side, sh in (("bid", -0.1), ("ask", 0.1)):
        for k in ("open", "high", "low", "close"):
            df[f"{side}_{k}"] = df[k] + sh
    return df


def _sig(n, at=0, d=1, entry=100.0, stop=99.0, tp2=103.0, level_id=7, until=None):
    s = pd.DataFrame({"signal": False, "dir": d, "level_id": None, "entry": np.nan, "stop": np.nan,
                      "tp1": np.nan, "tp2": np.nan, "tp3": np.nan, "reason": "no_fresh_level"}, index=range(n))
    for t in range(at, n if until is None else until):
        s.loc[t, ["signal", "level_id", "entry", "stop", "tp2", "reason"]] = [True, level_id, entry, stop, tp2, "signal"]
    return s


FLAT = (101.0, 101.4, 100.6, 101.0)


def test_limit_fills_next_candle_then_target():
    df = _frame([FLAT, (101.0, 101.2, 99.8, 100.4), (100.4, 103.3, 100.3, 103.0)] + [FLAT] * 3)
    trades, counts = st.simulate(df, _sig(len(df), until=2), "2026-03-01", "2026-04-01", st.Broker(slippage=0.0))
    t = trades.iloc[0]
    assert counts["submitted"] == 1 and counts["filled"] == 1
    assert t["fill"] == 100.0 and t["fill_bar"] == 1           # ask low 99.9 <= 100 on the next candle
    assert t["reason"] == "target" and t["exit"] == 103.0      # bid high 103.2 >= 103
    assert t["R"] == pytest.approx(3.0)


def test_conservative_path_stops_on_the_fill_candle_and_tradingview_path_may_not():
    # Fill candle: opens 100.5, high 102.9, low 98.9. Conservative: high before the fill, then the low hits the stop.
    rows = [FLAT, (100.5, 102.9, 98.9, 102.0)] + [FLAT] * 3
    cons, _ = st.simulate(_frame(rows), _sig(5, until=1), "2026-03-01", "2026-04-01", st.Broker(slippage=0.0))
    assert cons.iloc[0]["reason"] == "stop" and cons.iloc[0]["R"] == pytest.approx(-1.0)
    # TradingView: the low is nearer the open (1.6 vs 2.4), so low first: fill, then stop as well.
    tv, _ = st.simulate(_frame(rows), _sig(5, until=1), "2026-03-01", "2026-04-01", st.Broker(path="tradingview", slippage=0.0))
    assert tv.iloc[0]["reason"] == "stop"
    # A candle reaching both on a later candle: conservative takes the stop.
    rows2 = [FLAT, (100.5, 100.6, 99.8, 100.2), (100.2, 103.5, 98.5, 101.0)] + [FLAT] * 3
    cons2, _ = st.simulate(_frame(rows2), _sig(6, until=1), "2026-03-01", "2026-04-01", st.Broker(slippage=0.0))
    assert cons2.iloc[0]["reason"] == "stop"
    tv2, _ = st.simulate(_frame(rows2), _sig(6, until=1), "2026-03-01", "2026-04-01", st.Broker(path="tradingview", slippage=0.0))
    assert tv2.iloc[0]["reason"] == "stop"  # open 100.2 is nearer the low (1.7) than the high (3.3)


def test_pending_order_is_cancelled_when_the_signal_goes_away():
    df = _frame([FLAT] * 6)
    trades, counts = st.simulate(df, _sig(6, until=2), "2026-03-01", "2026-04-01")
    assert trades.empty and counts == {"submitted": 1, "cancelled": 1, "filled": 0}


def test_gap_through_the_stop_after_the_fill_exits_at_the_open():
    rows = [FLAT, (100.5, 100.6, 99.8, 100.2), (98.0, 98.4, 97.6, 98.1)] + [FLAT] * 2
    trades, _ = st.simulate(_frame(rows), _sig(5, until=1), "2026-03-01", "2026-04-01", st.Broker(slippage=0.1))
    t = trades.iloc[0]
    assert t["reason"] == "stop_gap" and t["exit"] == pytest.approx(98.0 - 0.1 - 0.1)  # bid open minus slippage
    assert t["R"] < -1


def test_short_side_mirrors():
    rows = [FLAT, (101.0, 101.2, 100.6, 101.0), (101.0, 101.1, 96.5, 97.0)] + [FLAT] * 2
    s = _sig(5, d=-1, entry=101.1, stop=102.0, tp2=97.0, until=1)
    trades, _ = st.simulate(_frame(rows), s, "2026-03-01", "2026-04-01", st.Broker(slippage=0.0))
    t = trades.iloc[0]
    assert t["fill"] == 101.1 and t["reason"] == "target" and t["exit"] == 97.0  # bid high 101.1 fills; ask low 96.6 hits 97


def test_range_end_closes_at_the_next_open():
    rows = [FLAT, (100.5, 100.6, 99.8, 100.2)] + [FLAT] * 4
    end = str(_frame(rows)["close_time"].iat[2])
    trades, _ = st.simulate(_frame(rows), _sig(6, until=1), "2026-03-01", end, st.Broker(slippage=0.0))
    t = trades.iloc[0]
    assert t["reason"] == "range_end" and t["exit_time"] == _frame(rows)["time"].iat[3]


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_signals_do_not_look_ahead():
    m15 = data.load("M15", start="2024-01-01", end="2024-03-01")
    full = st.signals(m15)
    part_m15 = m15[m15["time"] < pd.Timestamp("2024-02-10 07:30", tz="UTC")].reset_index(drop=True)
    part = st.signals(part_m15)
    pd.testing.assert_frame_equal(part, full.iloc[: len(part)].reset_index(drop=True))
    assert full["signal"].sum() > 0


def test_a_gap_fill_at_the_stop_is_a_kept_loss_not_a_dropped_trade():
    # The candle after submission opens exactly at the stop (99.0 + spread), below the 100 limit.
    rows = [FLAT, (98.9, 99.0, 98.5, 98.8)] + [FLAT] * 3
    trades, counts = st.simulate(_frame(rows), _sig(5, until=1), "2026-03-01", "2026-04-01", st.Broker(slippage=0.0))
    assert counts["filled"] == 1 and len(trades) == 1
    t = trades.iloc[0]
    # Bought at the 99.0 ask open (better than the 100 limit), sold at the 98.8 bid: -0.2 on a planned risk of 1.0.
    assert t["reason"] == "stop_gap" and t["fill"] == pytest.approx(99.0) and t["R"] == pytest.approx(-0.2)
    assert t["risk"] == pytest.approx(1.0) and t["fill_risk"] == pytest.approx(0.0)


def test_a_fixed_dollar_stop_replaces_the_structural_stop_and_sets_the_risk():
    # Long from 100 with the wick at 99: structural stop 99 - 0.2 ATR; a fixed $20 stop sits at 80.
    raw: list = []
    st.target_add(raw, 1, 100.0, 150.0, 60, True, 1)
    structural = st.structure_targets(raw, 1, 100.0, 99.0, 5.0, 0.01, max_atr=20)
    fixed = st.structure_targets(raw, 1, 100.0, 99.0, 5.0, 0.01, max_atr=20, stop_distance=20.0)
    assert structural["stop"] == pytest.approx(98.0) and fixed["stop"] == pytest.approx(80.0)
    assert fixed["tp2"] == structural["tp2"] and fixed["reason"] == ""
    # The target must still be min_r away from the wider risk: 1.5 x $20 = $30.
    raw_near: list = []
    st.target_add(raw_near, 1, 100.0, 120.0, 60, True, 1)
    assert st.structure_targets(raw_near, 1, 100.0, 99.0, 5.0, 0.01, max_atr=20, stop_distance=20.0)["reason"] == "insufficient_room"
    # Short: the stop is above the entry.
    raw_short: list = []
    st.target_add(raw_short, -1, 100.0, 50.0, 60, True, 1)
    assert st.structure_targets(raw_short, -1, 100.0, 101.0, 5.0, 0.01, max_atr=20, stop_distance=20.0)["stop"] == pytest.approx(120.0)


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_against_mode_trades_the_opposite_side_of_the_h4_direction():
    m15 = data.load("M15", start="2024-01-01", end="2024-03-01")
    with_h4 = st.signals(m15)
    # A $20 stop needs targets at least $30 away: the 8 ATR cap would reject almost every one on 15m.
    against = st.signals(m15, st.StrategyParams(h4_mode="against", stop_usd=20.0, max_atr=20.0))
    assert (with_h4["h4_dir"] == against["h4_dir"]).all()
    assert (with_h4["dir"] == with_h4["h4_dir"]).all() and (against["dir"] == -against["h4_dir"]).all()
    sig = against[against["signal"]]
    assert len(sig) > 0
    # Longs buy support below the close, shorts sell resistance above it; the stop is $20 away.
    assert np.allclose(sig["dir"] * (sig["entry"] - sig["stop"]), 20.0, atol=0.011)
    close = m15.loc[sig.index, "close"]
    assert (sig["dir"] * (close - sig["entry"]) > 0).all()


def test_an_atr_stop_scales_with_the_atr_and_a_dollar_stop_wins_if_both_are_set():
    assert st.StrategyParams(stop_atr=2.5).stop_distance(4.0) == pytest.approx(10.0)
    assert st.StrategyParams(stop_usd=20.0).stop_distance(4.0) == 20.0
    assert st.StrategyParams().stop_distance(4.0) == 0.0


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_1d_filter_keeps_only_trades_whose_direction_matches_the_mode():
    m15 = data.load("M15", start="2023-09-01", end="2024-03-01")
    p = st.StrategyParams(h4_mode="against", stop_atr=2.6)
    d1 = st.d1_inputs(m15, p)
    assert not np.isnan(d1[-1000:]).any()
    base = st.signals(m15, p)
    for mode, want in (("with", 1), ("against", -1)):
        sig = st.signals(m15, st.StrategyParams(h4_mode="against", stop_atr=2.6, d1_mode=mode), d1=d1)
        live = sig[sig["signal"]]
        assert len(live) > 0 and (np.sign(live["d1"].astype(float)) == want * live["dir"]).all()
        # The filter only removes candles: every signal it keeps is a signal without it.
        assert base.loc[live.index, "signal"].all()
        assert (sig["reason"] == "d1_context").any()
    assert (base["reason"] != "d1_context").all() and base["d1"].isna().all()


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_1h_chart_signals_do_not_look_ahead_and_fill_on_1h_candles():
    h1 = data.aggregate(data.load("M15", start="2023-09-01", end="2024-03-01"), "1H")
    p = st.StrategyParams(h4_mode="against", stop_atr=1.3)
    full = st.signals(h1, p)
    part_h1 = h1[h1["time"] < pd.Timestamp("2024-02-10 07:00", tz="UTC")].reset_index(drop=True)
    pd.testing.assert_frame_equal(st.signals(part_h1, p), full.iloc[: len(part_h1)].reset_index(drop=True))
    assert full["signal"].sum() > 0
    trades, counts = st.simulate(h1, full, "2023-11-01", "2024-03-01")
    assert counts["filled"] > 0 and trades["fill_time"].dt.minute.eq(0).all()



def test_reaction_pick_follows_the_indicator_rejection_rule():
    sup = Level(1, 100.0, 1, st.ST_FRESH, 0, 99.5)
    res = Level(2, 110.0, -1, st.ST_FRESH, 0, 110.5)
    fresh = {1, 2}
    # Bullish candle that dipped to 99.8 through the support and closed 101: lower wick 1.0 of 1.4 (71%).
    assert st.reaction_pick([sup, res], 1, fresh, 100.8, 101.2, 99.8, 101.0) is sup
    assert st.reaction_pick([sup, res], 1, set(), 100.8, 101.2, 99.8, 101.0) is None      # not fresh before
    assert st.reaction_pick([sup, res], 1, fresh, 101.0, 101.2, 99.8, 100.8) is None      # bearish candle
    assert st.reaction_pick([sup, res], 1, fresh, 100.2, 101.2, 99.8, 101.0) is None      # wick 0.4 of 1.4
    assert st.reaction_pick([sup, res], 1, fresh, 100.8, 101.2, 100.1, 101.0) is None     # never reached it
    # Bearish rejection of the resistance mirrors it.
    assert st.reaction_pick([sup, res], -1, fresh, 109.2, 110.3, 108.9, 109.0) is res
    # Close back: any candle that touched it and closed on its side, whatever its colour or wick.
    assert st.reaction_pick([sup, res], 1, fresh, 101.0, 101.2, 99.8, 100.8, strict=False) is sup
    assert st.reaction_pick([sup, res], 1, fresh, 100.5, 100.6, 99.4, 99.9, strict=False) is None  # closed below


def test_a_market_order_fills_at_the_next_open_with_slippage():
    df = _frame([FLAT, (101.0, 104.3, 100.9, 104.0)] + [FLAT] * 3)
    sig = _sig(len(df), entry=101.0, stop=100.0, tp2=104.0, until=1)
    sig["order"] = "market"
    trades, counts = st.simulate(df, sig, "2026-03-01", "2026-04-01", st.Broker(slippage=0.05))
    t = trades.iloc[0]
    assert counts["filled"] == 1 and t["fill_bar"] == 1
    assert t["fill"] == pytest.approx(101.15)                  # ask open 101.1 + 0.05 slippage
    assert t["reason"] == "target" and t["exit"] == 104.0
    assert t["R"] == pytest.approx((104.0 - 101.15) / 1.0)     # planned risk: signal close 101 to stop 100


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
@pytest.mark.parametrize("mode", ["rejection", "close_back"])
def test_confirmed_entries_are_first_touches_entered_at_the_next_open(mode):
    m15 = data.load("M15", start="2023-09-01", end="2024-03-01")
    sig = st.signals(m15, st.StrategyParams(h4_mode="against", entry_mode=mode))
    live = sig[sig["signal"]]
    assert len(live) > 0 and (sig["order"] == "market").all()
    c = m15.loc[live.index]
    d = live["dir"].astype(int)
    assert (live["entry"] == c["close"]).all()
    # The stop sits beyond the rejection wick, so beyond the candle's extreme on the trade side.
    assert (d * (np.where(d == 1, c["low"], c["high"]) - live["stop"]) > 0).all()
    # A level is entered on its first touch only.
    assert not live["level_id"].duplicated().any()
    trades, counts = st.simulate(m15, sig, "2023-11-01", "2024-03-01")
    assert counts["filled"] == counts["submitted"] > 0
    assert (trades["fill_time"] > trades["signal_time"]).all()
    # Filled at the next candle's ask (long) or bid (short) open, plus the 0.10 slippage.
    assert np.allclose(trades["fill"] - trades["dir"] * 0.10, (
        m15.set_index("time").loc[trades["fill_time"], ["ask_open", "bid_open"]]
        .to_numpy()[np.arange(len(trades)), (trades["dir"] == -1).astype(int).to_numpy()]), atol=1e-9)
