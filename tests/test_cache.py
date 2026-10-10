"""Invariants of the downloaded M15 cache. Skipped when there is no local data.

These check what the pipeline guarantees. What the feed itself got wrong is
reported in results/data_quality/, not asserted here.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from gse_research import data

pytestmark = pytest.mark.skipif(not data.dataset_path("M15").exists(), reason="no local M15 cache")


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return data.load("M15", session_only=False)


@pytest.fixture(scope="module")
def m15() -> pd.DataFrame:
    return data.load("M15")


def test_manifest_matches_the_file():
    entry = json.loads(data.MANIFEST.read_text())[data.dataset_path("M15").name]
    assert entry["sha256"] == data.file_sha256(data.dataset_path("M15"))


def test_schema_and_time_order(raw):
    assert list(raw.columns) == ["time", *data.PRICE_COLUMNS, "volume", "close_time"]
    assert str(raw["time"].dtype) == data.TIME_DTYPE
    assert raw["time"].is_unique
    assert raw["time"].is_monotonic_increasing
    assert ((raw["time"] - raw["time"].dt.floor("15min")) == pd.Timedelta(0)).all()
    assert raw[data.PRICE_COLUMNS].notna().all().all()


def test_default_load_keeps_only_session_candles(raw, m15):
    assert data.in_session(m15["time"]).all()
    assert len(m15) == int(data.in_session(raw["time"]).sum())


def test_higher_timeframes_respect_session_anchors(m15):
    h4 = data.aggregate(m15, "4H")
    length = h4["close_time"] - h4["time"]
    assert length.isin([pd.Timedelta(hours=4), pd.Timedelta(hours=3)]).all()
    assert (h4["candles"] <= 16).all()
    closes_ny = h4["close_time"].dt.tz_convert("America/New_York").dt.strftime("%H:%M")
    assert set(closes_ny) <= {"22:00", "02:00", "06:00", "10:00", "14:00", "17:00"}
    d1 = data.aggregate(m15, "1D")
    assert (d1["close_time"].dt.tz_convert("America/New_York").dt.strftime("%H:%M") == "17:00").all()
