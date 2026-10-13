"""The one-shot locked test: frozen criteria and its refusals."""

import json

import pytest

from gse_research import locked_test as lt


def test_frozen_criteria():
    years = {2023: 0.2, 2024: 0.1, 2025: -0.05, 2026: 0.3}
    good = {"trades": 140, "expectancy_R": 0.12, "profit_factor": 1.3}
    assert lt.judge(good, 0.01, years)["status"] == "pass"
    assert lt.judge(good, -0.02, years)["status"] == "weak"
    assert lt.judge({**good, "profit_factor": 1.1}, 0.01, years)["status"] == "weak"
    assert lt.judge(good, 0.01, {**years, 2024: -0.1})["status"] == "weak"          # only 2 of 4 years
    assert lt.judge({**good, "expectancy_R": -0.01}, -0.2, years)["status"] == "fail"
    assert lt.judge({**good, "trades": 60}, 0.05, years)["status"] == "inconclusive"


def test_refuses_without_approval_and_runs_only_once(tmp_path):
    rule = tmp_path / "rule.json"
    rule.write_text(json.dumps({"name": "T"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="locked"):
        lt.run(rule, allow_test=False)
    (tmp_path / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="already been tested"):
        lt.run(rule, allow_test=True)
