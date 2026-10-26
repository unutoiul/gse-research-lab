"""Forward test F2: the warm-up is long enough, and the verdict waits for enough trades."""

import pandas as pd
import pytest

from gse_research import data, forward_setups as f2

VARIANTS = [("A_pullback", "touch", "atr5", "r0.5"), ("B_flip", "touch", "atr2", "r0.75")]


@pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")
def test_paper_trades_do_not_depend_on_more_history_than_the_warmup():
    start, end = "2022-06-01", "2022-10-01"
    short = data.load("M15", (pd.Timestamp(start) - pd.Timedelta(days=f2.WARMUP_DAYS)).strftime("%Y-%m-%d"), end)
    long_ = data.load("M15", (pd.Timestamp(start) - pd.Timedelta(days=2 * f2.WARMUP_DAYS)).strftime("%Y-%m-%d"), end)
    a, b = f2.collect(short, VARIANTS, start), f2.collect(long_, VARIANTS, start)
    cols = ["signal_time", "fill_time", "dir", "fill", "stop", "tp2", "exit_time", "exit", "reason", "R"]
    for v in VARIANTS:
        assert len(a[v]["net"]) > 0
        pd.testing.assert_frame_equal(a[v]["net"][cols].reset_index(drop=True), b[v]["net"][cols].reset_index(drop=True))


def test_the_verdict_waits_for_enough_closed_trades():
    s = {"expectancy_R": 0.2, "profit_factor": 1.5}
    assert f2.decide(40, s, 0.1)[0] == "running"
    assert f2.decide(120, s, 0.1)[0] == "pass"
    assert f2.decide(120, s, -0.1)[0] == "weak"
    assert f2.decide(120, {"expectancy_R": -0.1, "profit_factor": 0.8}, -0.3)[0] == "fail"
