"""Job parameters (mirrored by the website admin API) and JSON cleaning."""

import math

import numpy as np
import pandas as pd
import pytest

from gse_research import jobs


def test_defaults_and_valid_parameters():
    assert jobs.validate("strategy_backtest", {}) == {"swing_len": 10, "h4_swing_len": 10, "period": "train", "costs": "net",
                                                      "path": "conservative", "stop_buffer_atr": 0.2, "min_r": 1.5, "max_atr": 8.0}
    assert jobs.validate("strategy_backtest", {"stop_buffer_atr": 1, "min_r": 1.0})["stop_buffer_atr"] == 1.0
    assert jobs.validate("strategy_backtest", {"swing_len": 7, "period": "validate", "costs": "half"})["swing_len"] == 7
    assert jobs.validate("r001", {"period": "validate"}) == {"period": "validate"}
    assert jobs.validate("search_o1", {"trials": 50}) == {"trials": 50}
    assert jobs.validate("data_update", {}) == {} and jobs.validate("search_o2", None) == {}


@pytest.mark.parametrize("kind, params", [
    ("r001", {"period": "test"}),                 # the locked test period is never accepted
    ("strategy_backtest", {"period": "test"}),
    ("strategy_backtest", {"swing_len": 2}),
    ("strategy_backtest", {"swing_len": 51}),
    ("strategy_backtest", {"swing_len": 10.5}),
    ("strategy_backtest", {"swing_len": True}),
    ("strategy_backtest", {"costs": "free"}),
    ("strategy_backtest", {"start": "2023-01-01"}),  # unknown keys are refused
    ("search_o1", {"trials": 5000}),
    ("strategy_backtest", {"stop_buffer_atr": 0.0}),
    ("strategy_backtest", {"max_atr": "8"}),
    ("strategy_backtest", {"min_r": True}),
    ("search_o3", {"anything": 1}),
    ("delete_everything", {}),
])
def test_invalid_parameters_are_refused(kind, params):
    with pytest.raises(ValueError):
        jobs.validate(kind, params)


def test_clean_makes_json_safe_values():
    out = jobs.clean({"a": np.float64(1.5), "b": math.nan, "c": np.int64(3), "d": [math.inf, pd.Timestamp("2026-01-01", tz="UTC")],
                      "e": np.bool_(True), "f": None, "g": "x"})
    assert out == {"a": 1.5, "b": None, "c": 3, "d": [None, "2026-01-01T00:00:00+00:00"], "e": True, "f": None, "g": "x"}


def test_equity_is_cumulative_and_downsampled():
    t = pd.DataFrame({"R": [1.0, -1.0] * 1000, "exit_time": pd.date_range("2026-01-01", periods=2000, freq="h", tz="UTC"),
                      "entry_time": pd.date_range("2026-01-01", periods=2000, freq="h", tz="UTC")})
    pts = jobs.equity(t, max_points=100)
    assert len(pts) <= 101 and pts[-1][1] == 0.0 and pts[0][1] == 1.0


def test_db_retries_a_dropped_connection_then_gives_up(monkeypatch):
    import psycopg
    from gse_research import worker

    calls = {"n": 0}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def connect():
        calls["n"] += 1
        if calls["n"] < 3:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return Conn()

    monkeypatch.setattr(worker, "_connect", connect)
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)
    assert worker.db(lambda c: "ok") == "ok" and calls["n"] == 3
    calls["n"] = -100
    with pytest.raises(psycopg.OperationalError):
        worker.db(lambda c: "never", retries=2)


def test_abandon_job_only_fails_a_job_still_queued_or_running(monkeypatch):
    from gse_research import worker

    seen = []

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            seen.append((sql, params))
            return type("Cursor", (), {"rowcount": 1 if "still" in params[0] else 0})()

    monkeypatch.setattr(worker, "_connect", Conn)
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/lab")
    assert worker.abandon_job("job-1", "still running when the run stopped") is True
    assert worker.abandon_job("job-2", "already done") is False
    sql, params = seen[0]
    assert "status in ('queued', 'running')" in sql and "status = 'failed'" in sql
    assert params == ("still running when the run stopped", "github:owner/lab/42", "job-1")
