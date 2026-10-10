"""Data-quality checks find each kind of bad candle and stay quiet on clean data."""

from __future__ import annotations

import pandas as pd

from gse_research.quality import issues, missing_slots, year_report

NY = "America/New_York"


def kinds(df: pd.DataFrame) -> set[str]:
    return set(issues(df)["kind"])


def test_clean_data_has_no_issues(candles):
    df = candles("2026-07-14", "2026-07-15")
    assert issues(df).empty
    report = year_report(df)
    assert report.loc[2026, "verdict"] == "good"
    assert report.loc[2026, "errors"] == 0


def test_duplicate_and_misaligned_times(candles):
    df = candles("2026-07-15")
    dup = pd.concat([df, df.iloc[[10]]]).sort_values("time", ignore_index=True)
    assert {"duplicate", "misaligned"} <= kinds(dup)
    off = df.copy()
    off.loc[5, "time"] += pd.Timedelta(minutes=7)
    assert "misaligned" in kinds(off)


def test_bad_prices(candles):
    df = candles("2026-07-15")
    bad = df.copy()
    bad.loc[3, "high"] = bad.loc[3, "close"] - 1  # high below close
    bad.loc[4, "bid_close"] = bad.loc[4, "ask_close"] + 0.5  # crossed quote
    bad.loc[6, "ask_low"] = -1.0
    found = issues(bad)
    assert {"ohlc", "crossed", "nonpositive"} <= set(found["kind"])
    assert (found["severity"] == "error").all()


def test_candles_in_the_break_and_the_weekend(candles):
    df = candles("2026-07-17")  # a Friday
    extra = df.iloc[[0, 0]].copy()
    extra["time"] = [pd.Timestamp("2026-07-16 17:15", tz=NY).tz_convert("UTC"),
                     pd.Timestamp("2026-07-18 10:00", tz=NY).tz_convert("UTC")]
    found = issues(pd.concat([df, extra]).sort_values("time", ignore_index=True))
    assert {"break", "weekend"} <= set(found["kind"])


def test_jump_is_flagged_for_review(candles):
    df = candles("2026-07-15")
    df.loc[60:, ["open", "high", "low", "close"]] += 50.0
    found = issues(df)
    assert "jump" in set(found["kind"])
    assert (found.loc[found["kind"] == "jump", "severity"] == "review").all()


def test_missing_slots_counts_interior_gaps(candles):
    df = candles("2026-07-15")
    holed = df.drop(index=[40, 41, 70]).reset_index(drop=True)
    days = missing_slots(holed)
    assert days["candles"].iloc[0] == 89
    assert days["interior_missing"].iloc[0] == 3


def test_thin_candle_outside_the_session_is_a_print_to_review(candles):
    df = candles("2026-07-17")  # a Friday
    extra = df.iloc[[-1]].copy()
    extra["time"] = pd.Timestamp("2026-07-17 17:00", tz=NY).tz_convert("UTC")
    extra["volume"] = 1
    found = issues(pd.concat([df, extra], ignore_index=True))
    assert found["kind"].tolist() == ["break_print"]
    assert found["severity"].tolist() == ["review"]
