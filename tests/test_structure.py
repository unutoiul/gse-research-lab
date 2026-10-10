"""Unit tests of the GSE v4.0 port: Pine helpers, series formulas, no look-ahead."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from gse_research import data, structure as st
from gse_research.structure import level_duplicate, level_quality, opened_away, pivots, resolve_bias


# The same cases as gse-website/tradingview/gse_4.0/test-core.mjs.
def test_bias_follows_the_break_at_half_strength_when_swings_oppose_it():
    assert resolve_bias(2, -1, 1) == -0.5 and resolve_bias(2, -1, 1, False) == 0
    assert resolve_bias(-2, 1, -1) == 0.5 and resolve_bias(-2, 1, -1, False) == 0
    for raw in (-2, -1, 1, 2):
        for ema in (-1, 0, 1):
            assert resolve_bias(raw, -int(math.copysign(1, raw)), ema) == -math.copysign(0.5, raw)


def test_bias_is_zero_on_mixed_swings_whatever_the_break_or_ema():
    for d in (-1, 0, 1):
        for ema in (-1, 0, 1):
            for fb in (True, False):
                assert resolve_bias(0, d, ema, fb) == 0


def test_ema_strengthens_or_weakens_but_never_reverses():
    assert resolve_bias(2, 1, 1) == 3 and resolve_bias(-2, -1, -1) == -3
    assert resolve_bias(2, 1, -1) == 1 and resolve_bias(1, 1, -1) == 0 and resolve_bias(-1, -1, 1) == 0
    assert resolve_bias(1, 0, 0) == 1 and resolve_bias(1, 0, -3) == 0


def test_level_quality_weights():
    assert level_quality(True, False, 1) == 1 and level_quality(True, False, 0) == 1
    assert level_quality(True, False, 2) == 0
    assert level_quality(False, True, 0) == 0.8 and level_quality(False, False, 1) == 0


def test_duplicate_levels_merge_only_at_the_same_tick_unless_zones_are_on():
    for state in (0, 1, 3):
        assert level_duplicate(1, state, 100, 1, 100, False, 5, 0.01)
        assert level_duplicate(1, state, 100, 1, 102, True, 5, 0.01)
        assert not level_duplicate(1, state, 100, 1, 102, False, 5, 0.01)
    assert level_duplicate(1, 1, 100, 1, 100.001, False, 5, 0.01)
    assert not level_duplicate(1, 2, 100, 1, 100, True, 5, 0.01)  # a flip candidate absorbs nothing
    assert not level_duplicate(1, 0, 100, -1, 100, True, 5, 0.01)
    assert not level_duplicate(1, 0, 100, 1, 102, True, math.nan, 0.01)


def test_opened_away():
    assert opened_away(-1, 99.5, 100, 0.01) and not opened_away(-1, 100, 100, 0.01) and not opened_away(-1, 99.996, 100, 0.01)
    assert opened_away(1, 100.5, 100, 0.01) and not opened_away(1, 100, 100, 0.01)


@pytest.mark.parametrize("ties, expected", [
    ("strict", []),       # two equal highs: neither is strictly higher than the other
    ("left", [6]),        # the later of the pair (equal to an earlier neighbour)
    ("right", [5]),       # the earlier of the pair
    ("both", [5, 6]),
])
def test_pivot_tie_rules(ties, expected):
    src = np.array([1, 2, 3, 4, 5, 9, 9, 5, 4, 3, 2, 1, 0], float)
    out = pivots(src, 3, 3, True, ties)
    found = [int(i) - 3 for i in np.flatnonzero(~np.isnan(out))]  # pivot candle = confirmation candle - right
    assert found == expected


def test_pivot_is_known_only_after_its_right_bars():
    src = np.array([1, 2, 5, 2, 1, 0, 0], float)
    out = pivots(src, 2, 2, True)
    assert np.isnan(out[:4]).all() and out[4] == 5 and np.isnan(out[5:]).all()
    low = pivots(-src, 2, 2, False)
    assert low[4] == -5


def test_pine_series_formulas():
    x = np.array([1, 2, 3, 4, 5, 6], float)
    rma = st.pine_rma(x, 3)
    assert np.isnan(rma[:2]).all() and rma[2] == 2 and rma[3] == pytest.approx((4 + 2 * 2) / 3)
    ema = st.pine_ema(x, 3)
    assert np.isnan(ema[:2]).all() and ema[2] == 2 and ema[3] == pytest.approx(0.5 * 4 + 0.5 * 2)
    h, l, c = np.array([10, 12.0]), np.array([9, 10.0]), np.array([9.5, 11.0])
    tr_first = st.pine_atr(np.r_[h, h], np.r_[l, l], np.r_[c, c], 1)
    assert tr_first[0] == 1 and tr_first[1] == pytest.approx(max(2, abs(12 - 9.5), abs(10 - 9.5)))


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_truncated_history_gives_identical_earlier_candles():
    """No look-ahead: removing later candles never changes an earlier candle's state."""
    full = data.load("M15", start="2024-01-01", end="2024-04-01")
    out_full, _ = st.run(full)
    for cut in ("2024-02-01 13:15", "2024-03-15 20:45"):
        part = full[full["time"] < pd.Timestamp(cut, tz="UTC")].reset_index(drop=True)
        out_part, _ = st.run(part)
        pd.testing.assert_frame_equal(out_part, out_full.iloc[: len(part)].reset_index(drop=True), check_dtype=False)


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_require_sweep_only_removes_golden_zone_candles():
    m15 = data.load("M15", start="2023-01-01", end="2024-01-01")
    prep = st.prepare(m15)
    c0, _ = st.run(m15, prep=prep)
    v1, _ = st.run(m15, ctx=st.ContextParams(require_sweep=True), prep=prep)
    assert not (v1["long_zone"] & ~c0["long_zone"]).any()
    assert not (v1["short_zone"] & ~c0["short_zone"]).any()
    assert ((v1["long_zone"] == (c0["long_zone"] & c0["bull_bos_had_sweep"])).all())


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_htf_bias_uses_closed_candles_only():
    m15 = data.load("M15", start="2024-01-01", end="2024-02-15")
    htf = st.htf_context(m15)
    cut = m15[m15["time"] < pd.Timestamp("2024-02-01 06:15", tz="UTC")].reset_index(drop=True)
    htf_cut = st.htf_context(cut)
    pd.testing.assert_frame_equal(htf_cut, htf.iloc[: len(cut)].reset_index(drop=True))
    assert htf["h4"].notna().sum() > 0 and htf["h1"].notna().sum() > 0
