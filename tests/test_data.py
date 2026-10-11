"""Higher-timeframe construction and alignment: TradingView session anchors, DST, no look-ahead."""

from __future__ import annotations

import pandas as pd
import pytest

from gse_research.data import aggregate, align

NY = "America/New_York"


def utc(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def ny(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz=NY).tz_convert("UTC")


def hours(series: pd.Series) -> list[str]:
    return [f"{x:%H:%M}" for x in series]


def test_4h_summer_day_starts_at_18_ny_and_ends_with_a_3_hour_candle(candles):
    h4 = aggregate(candles("2026-07-15"), "4H")
    assert hours(h4["time"]) == ["22:00", "02:00", "06:00", "10:00", "14:00", "18:00"]
    assert hours(h4["close_time"]) == ["02:00", "06:00", "10:00", "14:00", "18:00", "21:00"]
    assert h4["candles"].tolist() == [16, 16, 16, 16, 16, 12]
    assert h4["close_time"].iloc[-1] == ny("2026-07-15 17:00")


def test_4h_winter_day_is_one_hour_later_in_utc(candles):
    h4 = aggregate(candles("2026-01-14"), "4H")
    assert hours(h4["time"]) == ["23:00", "03:00", "07:00", "11:00", "15:00", "19:00"]
    assert hours(h4["close_time"])[-1] == "22:00"


@pytest.mark.parametrize(
    "days, first_opens",
    [
        # US DST starts Sunday 2026-03-08: Monday's session opens Sunday 18:00 EDT.
        (("2026-03-05", "2026-03-06", "2026-03-09", "2026-03-10"),
         ["2026-03-04 23:00", "2026-03-05 23:00", "2026-03-08 22:00", "2026-03-09 22:00"]),
        # US DST ends Sunday 2026-11-01.
        (("2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03"),
         ["2026-10-28 22:00", "2026-10-29 22:00", "2026-11-01 23:00", "2026-11-02 23:00"]),
    ],
)
def test_dst_weeks_follow_new_york_time(candles, days, first_opens):
    m15 = candles(*days)
    for tf, per_day in (("4H", 6), ("1D", 1)):
        out = aggregate(m15, tf)
        assert len(out) == per_day * len(days)
        assert out["time"].iloc[::per_day].tolist() == [utc(s) for s in first_opens]
        # Every candle still closes at a New York wall time of the session.
        closes_ny = out["close_time"].dt.tz_convert(NY)
        assert set(hours(closes_ny)) <= {"22:00", "02:00", "06:00", "10:00", "14:00", "17:00"}


def test_1h_runs_on_the_clock_hour(candles):
    h1 = aggregate(candles("2026-07-15"), "1H")
    assert len(h1) == 23
    assert (h1["time"].dt.minute == 0).all()
    assert (h1["close_time"] - h1["time"] == pd.Timedelta(hours=1)).all()
    assert h1["close_time"].iloc[-1] == ny("2026-07-15 17:00")


def test_daily_candle_spans_18_to_17_new_york(candles):
    d1 = aggregate(candles("2026-07-13", "2026-07-14"), "1D")
    assert d1["time"].tolist() == [ny("2026-07-12 18:00"), ny("2026-07-13 18:00")]
    assert d1["close_time"].tolist() == [ny("2026-07-13 17:00"), ny("2026-07-14 17:00")]
    assert d1["candles"].tolist() == [92, 92]


def test_weekly_candle_opens_sunday_and_closes_friday(candles):
    w = aggregate(candles(*[f"2026-07-{d}" for d in range(13, 18)]), "1W")
    assert len(w) == 1
    assert w["time"].iloc[0] == ny("2026-07-12 18:00")
    assert w["close_time"].iloc[0] == ny("2026-07-17 17:00")
    assert w["candles"].iloc[0] == 5 * 92


def test_ohlcv_aggregation(candles):
    m15 = candles("2026-07-15")
    h4 = aggregate(m15, "4H")
    first = m15.iloc[:16]
    row = h4.iloc[0]
    assert row["open"] == first["open"].iloc[0]
    assert row["high"] == first["high"].max()
    assert row["low"] == first["low"].min()
    assert row["close"] == first["close"].iloc[-1]
    assert row["volume"] == first["volume"].sum()


@pytest.mark.parametrize("tf", ["1H", "4H", "1D", "1W"])
def test_truncation_does_not_change_completed_candles(candles, tf):
    m15 = candles(*[f"2026-07-{d}" for d in range(13, 18)], "2026-07-20")
    full = aggregate(m15, tf)
    for cutoff in (ny("2026-07-15 11:45"), ny("2026-07-17 17:00"), ny("2026-07-19 18:30")):
        part = aggregate(m15[m15["close_time"] <= cutoff], tf)
        done = part[part["close_time"] <= cutoff].reset_index(drop=True)
        expected = full[full["close_time"] <= cutoff].reset_index(drop=True)
        pd.testing.assert_frame_equal(done, expected)


def test_align_at_close_sees_an_htf_candle_on_the_m15_candle_that_closes_it(candles):
    m15 = candles("2026-07-14", "2026-07-15")
    h4 = aggregate(m15, "4H")
    seen = align(m15, h4, ["close"], at="close")
    # Never a candle that closes after this M15 candle closes.
    assert (seen["htf_close_time"].dropna() <= m15.loc[seen["htf_close_time"].notna(), "close_time"]).all()
    # The M15 candle closing at 17:00 NY sees the 3-hour 4H candle it closes.
    last = m15.index[m15["close_time"] == ny("2026-07-15 17:00")][0]
    assert seen.at[last, "htf_time"] == ny("2026-07-15 14:00")
    # One candle earlier, the previous 4H candle is still the latest closed one.
    assert seen.at[last - 1, "htf_time"] == ny("2026-07-15 10:00")
    # Nothing has closed before the first 4H candle's close.
    assert seen["htf_time"].iloc[:15].isna().all()
    assert seen.at[15, "htf_time"] == ny("2026-07-13 18:00")


def test_align_at_open_gives_the_previous_completed_day(candles):
    m15 = candles("2026-07-14", "2026-07-15", "2026-07-16")
    d1 = aggregate(m15, "1D")
    prev = align(m15, d1, ["high", "low"], at="open")
    assert (prev["htf_close_time"].dropna() <= m15.loc[prev["htf_close_time"].notna(), "time"]).all()
    day2 = m15["time"] >= ny("2026-07-14 18:00")
    day3 = m15["time"] >= ny("2026-07-15 18:00")
    assert prev.loc[~day2, "high"].isna().all()
    # Every candle of the second day, including its last (16:45 NY), sees the first day only.
    assert (prev.loc[day2 & ~day3, "high"] == d1["high"].iloc[0]).all()
    assert (prev.loc[day3, "high"] == d1["high"].iloc[1]).all()


def test_align_never_looks_ahead_on_a_long_series(candles):
    m15 = candles(*[f"2026-03-{d:02d}" for d in (2, 3, 4, 5, 6, 9, 10, 11, 12, 13)])
    for tf in ("1H", "4H", "1D", "1W"):
        htf = aggregate(m15, tf)
        for at, key in (("close", "close_time"), ("open", "time")):
            seen = align(m15, htf, ["close"], at=at)
            ok = seen["htf_close_time"].isna() | (seen["htf_close_time"] <= m15[key])
            assert ok.all(), (tf, at)
            # And it is the latest such candle.
            later = htf["close_time"].searchsorted(m15[key], side="right") - 1
            expected = htf["time"].reindex(later).where(later >= 0).reset_index(drop=True)
            pd.testing.assert_series_equal(seen["htf_time"].reset_index(drop=True), expected, check_names=False)


def test_bid_and_ask_are_aggregated_like_mid(candles):
    m15 = candles("2026-07-15")
    h4 = aggregate(m15, "4H")
    first = m15.iloc[:16]
    for side in ("bid", "ask"):
        assert h4[f"{side}_open"].iloc[0] == first[f"{side}_open"].iloc[0]
        assert h4[f"{side}_high"].iloc[0] == first[f"{side}_high"].max()
        assert h4[f"{side}_low"].iloc[0] == first[f"{side}_low"].min()
        assert h4[f"{side}_close"].iloc[0] == first[f"{side}_close"].iloc[-1]
    assert "bid_open" not in aggregate(m15[["time", "open", "high", "low", "close", "volume"]], "4H")
