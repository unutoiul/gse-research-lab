"""Study S1: confluence filters, the swing-range middle, the luck line, finalist verdicts and a small run."""

import math

import numpy as np
import pandas as pd
import pytest

from gse_research import data, jobs, msnr_search as ms, strategy as st
from gse_research.structure import ST_CAND, ST_FRESH, Level


def test_filter_masks_follow_the_trade_direction():
    sig = pd.DataFrame({"dir": [1, 1, -1, -1, 0], "entry": [99.0, 101.0, 101.0, 99.0, np.nan],
                        "bull_sweep_age": [3, -1, 2, 2, 0], "bear_sweep_age": [-1, 4, 9, 0, 0],
                        "in_london": [True, False, False, False, False], "in_ny": [False, True, False, True, False],
                        "trend_score": [1.0, 1.0, -1.0, 1.0, 0.0]})
    d1 = np.array([2.0, -1.0, -3.0, np.nan, 0.0])
    up = np.array([[1.0, 1.0, -1.0, -1.0, 0.0], [0.5, 1.0, -2.0, -1.0, 0.0]])
    mid = np.full(5, 100.0)
    m = ms.filter_masks(sig, d1, up, mid)
    assert m["d1"].tolist() == [True, False, True, False, False]
    assert m["sweep"].tolist() == [True, False, False, True, False]  # in the trade direction, within 8 candles
    assert m["session"].tolist() == [True, True, False, True, False]
    assert m["zone"].tolist() == [True, False, True, False, False]   # buy below the middle, sell above it
    assert m["mtf"].tolist() == [True, True, True, False, False]


def test_range_middle_uses_only_confirmed_swings():
    m15 = pd.DataFrame({"high": np.sin(np.arange(300) / 7) * 5 + 105, "low": np.sin(np.arange(300) / 7) * 5 + 95})
    full = ms.range_mid(m15, 5)
    part = ms.range_mid(m15.iloc[:200].reset_index(drop=True), 5)
    np.testing.assert_array_equal(part, full[:200])


def test_luck_line_and_finalist_verdicts():
    assert ms.luck_line(10_000) == pytest.approx(math.sqrt(2 * math.log(10_000)))
    good = {"val_net_trades": 150, "val_net_expectancy_R": 0.2, "val_net_profit_factor": 1.4, "val_net_ci_low": 0.02,
            "val_years_positive": 3}
    assert ms.finalist_verdict(good) == "candidate"
    assert ms.finalist_verdict({**good, "val_net_ci_low": -0.01}) == "watch"
    assert ms.finalist_verdict({**good, "val_years_positive": 2}) == "watch"
    assert ms.finalist_verdict({**good, "val_net_expectancy_R": -0.1}) == "rejected"
    assert ms.finalist_verdict({**good, "val_net_trades": 40}) == "inconclusive"
    assert jobs.validate("search_s1", {}) == {}


def test_flip_levels_are_entered_only_in_flip_or_both_mode():
    cand = Level(3, 100.0, 1, ST_CAND, 0)
    fresh = Level(4, 99.0, 1, ST_FRESH, 0, 98.5)
    assert st.touch_pick([cand, fresh], 1, 101.0) is fresh                          # the Pine: fresh only
    assert st.touch_pick([cand, fresh], 1, 101.0, st.ENTRY_STATES["flip"]) is cand
    assert st.touch_pick([cand, fresh], 1, 101.0, st.ENTRY_STATES["both"]) is cand  # the nearer one


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_a_small_group_runs_every_confluence_combination(monkeypatch):
    monkeypatch.setattr(ms, "DESIGN", {**ms.DESIGN, "level_type": ["both"], "h4_mode": ["against"], "stop_atr": [0.0]})
    monkeypatch.setattr(ms, "PERIODS", {"train": ("2023-11-01", "2024-01-01"), "val": ("2024-01-01", "2024-03-01")})
    monkeypatch.setattr(ms, "YEARS", {"train": (2023,), "val": (2024,)})
    hist = data.load("M15", start="2023-06-01", end="2024-03-02")
    monkeypatch.setattr(ms, "_HIST", hist)
    monkeypatch.setattr(ms, "_M15", hist[hist["time"] >= pd.Timestamp("2023-09-01", tz="UTC")].reset_index(drop=True))
    for f in (ms._chart, ms._h4, ms._inputs):
        f.cache_clear()
    rows = pd.DataFrame(ms.evaluate_group("1H", 5, "close_back"))
    for f in (ms._chart, ms._h4, ms._inputs):
        f.cache_clear()
    assert len(rows) == 2 ** len(ms.FILTERS)
    none = rows[~rows[ms.FILTERS].any(axis=1)].iloc[0]
    # A filter only removes trades: every combination trades at most as often as no filter.
    assert (rows["train_trades"] <= none["train_trades"]).all() and (rows["val_trades"] <= none["val_trades"]).all()
    assert none["train_trades"] > 0


def _fake_results(tmp_path):
    """A small S1 result folder written the way run_search writes it (text columns read back as pandas str)."""
    rng = np.random.default_rng(3)
    rows = []
    for design in [dict(zip(ms.DESIGN, v)) for v in
                   [("15m", 10, "fresh", "limit", "with", 0.0), ("1H", 5, "flip", "close_back", "against", 1.5),
                    ("15m", 3, "both", "rejection", "with", 3.0)]]:
        for combo in [(False,) * 5, (True, False, True, False, False), (False, True, False, True, True)]:
            rows.append({**design, **dict(zip(ms.FILTERS, combo)), "train_trades": int(rng.integers(50, 400)),
                         "train_expectancy_R": rng.normal(-0.2, 0.2), "train_sqn": rng.normal(-1, 1),
                         "val_trades": int(rng.integers(50, 500)), "val_expectancy_R": rng.normal(-0.2, 0.2)})
    trials = pd.DataFrame(rows)
    finalists = trials.head(3).assign(val_net_trades=[150, 90, 300], val_net_expectancy_R=[0.05, -0.1, -0.3],
                                      val_net_profit_factor=[1.1, 0.8, 0.6], val_net_ci_low=[-0.05, -0.3, -0.4],
                                      val_years_positive=[2, 1, 0], val_half_expectancy_R=[0.1, 0.0, -0.2],
                                      val_gross_expectancy_R=[0.15, 0.05, -0.1], verdict=["watch", "inconclusive", "rejected"])
    trials.to_csv(tmp_path / "trials.csv", index=False)
    finalists.to_csv(tmp_path / "finalists.csv", index=False)
    prov = {"git": {"commit": "abc1234567", "dirty": False}, "dataset_sha256": "f" * 64, "status": "provisional"}
    (tmp_path / "report.md").write_text(ms.report(pd.read_csv(tmp_path / "trials.csv"),
                                                  pd.read_csv(tmp_path / "finalists.csv"), prov), encoding="utf-8")
    return tmp_path


def test_the_admin_result_builds_from_the_files_and_is_json(tmp_path):
    import json

    run = jobs._s1_result(_fake_results(tmp_path), {}, "results/S1")
    json.dumps(run, allow_nan=False)
    assert run["kind"] == "search_s1" and run["summary"]["verdict"] == "watch"
    params = {r["param"] for r in run["detail"]["optimization"]["importance"]}
    assert {"chart_tf", "entry_mode", "level_type", "d1"} <= params      # text choices are ranked too
    assert "## Finalists on validation" in run["report_md"]
